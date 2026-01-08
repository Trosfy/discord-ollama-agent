"""Custom web search and fetch tools using DuckDuckGo and BeautifulSoup with RAG."""
import sys
sys.path.insert(0, '/shared')

from typing import Dict, List
import random
import asyncio
from ddgs import DDGS
import httpx
from bs4 import BeautifulSoup
from strands import tool
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')

# User-Agent pool for WAF bypass (6 realistic browser fingerprints)
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# Session pool for connection reuse by domain
_session_pool: Dict[str, httpx.AsyncClient] = {}

# Maximum tokens per fetch (aligns with VECTOR_TOP_K=7: 7 chunks × 1000 tokens = 7000)
MAX_FETCH_TOKENS = 7000


def _select_chunks_within_budget(chunks: List, max_tokens: int) -> tuple:
    """
    Select chunks that fit within token budget.

    Args:
        chunks: List of chunk dictionaries with 'token_count' key
        max_tokens: Maximum tokens allowed

    Returns:
        Tuple of (selected_chunks, total_tokens)
    """
    selected = []
    total_tokens = 0

    for chunk in chunks:
        chunk_tokens = chunk.get('token_count', 500)  # Fallback estimate
        if total_tokens + chunk_tokens <= max_tokens:
            selected.append(chunk)
            total_tokens += chunk_tokens
        else:
            break  # Budget exceeded

    return selected, total_tokens


def _get_realistic_headers() -> Dict[str, str]:
    """Generate realistic browser headers with random User-Agent.

    Returns:
        Dictionary of HTTP headers mimicking real browser
    """
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }


async def _get_or_create_session(domain: str) -> httpx.AsyncClient:
    """Get or create HTTP/2 session for domain (connection pooling).

    Args:
        domain: Domain name for session pooling

    Returns:
        httpx.AsyncClient session
    """
    if domain not in _session_pool:
        _session_pool[domain] = httpx.AsyncClient(
            http2=True,  # Enable HTTP/2
            follow_redirects=True,
            timeout=httpx.Timeout(30.0)
        )
        logger.debug(f"🔌 Created new HTTP/2 session for domain: {domain}")
    return _session_pool[domain]


async def _fetch_with_retry(url: str, max_retries: int = 3) -> httpx.Response:
    """Fetch URL with exponential backoff retry.

    Args:
        url: URL to fetch
        max_retries: Maximum number of retry attempts

    Returns:
        httpx.Response object

    Raises:
        httpx.HTTPError: If all retries fail
    """
    from urllib.parse import urlparse

    domain = urlparse(url).netloc
    session = await _get_or_create_session(domain)
    headers = _get_realistic_headers()

    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"🌐 Fetching {url} (attempt {attempt}/{max_retries})")
            response = await session.get(url, headers=headers)
            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as e:
            if e.response.status_code in [429, 503]:  # Rate limit or service unavailable
                if attempt < max_retries:
                    backoff = 2 ** attempt  # Exponential backoff: 2, 4, 8 seconds
                    logger.warning(
                        f"⚠️ HTTP {e.response.status_code} for {url}, "
                        f"retrying in {backoff}s... (attempt {attempt}/{max_retries})"
                    )
                    await asyncio.sleep(backoff)
                    continue
            raise

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt < max_retries:
                backoff = 2 ** attempt
                logger.warning(
                    f"⚠️ {type(e).__name__} for {url}, "
                    f"retrying in {backoff}s... (attempt {attempt}/{max_retries})"
                )
                await asyncio.sleep(backoff)
                continue
            raise


@tool(
    name="web_search",
    description="Search the web using DuckDuckGo. Returns titles, URLs, and snippets."
)
def web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search the web for current information.

    Args:
        query: Search query string (e.g., "Traveloka promotions December 2024")
        max_results: Maximum number of results to return (default: 5, max: 10)

    Returns:
        List of search results, each containing:
        - position: Result ranking (1-based)
        - title: Page title
        - url: Page URL
        - snippet: Preview text from the page
    """
    logger.info(f"🔍 Tool: web_search | Query: '{query}' | Max results: {max_results}")

    try:
        # DuckDuckGo search with context manager
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=min(max_results, 10)))

        # Format results
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append({
                "position": i,
                "title": result.get("title", ""),
                "url": result.get("href", ""),
                "snippet": result.get("body", "")
            })

        logger.info(f"✅ Tool: web_search | Found {len(formatted)} results for '{query}'")
        return formatted
    except Exception as e:
        logger.error(f"❌ Tool: web_search | Error: {str(e)}")
        return [{"error": f"Search failed: {str(e)}"}]


@tool(
    name="fetch_webpage",
    description="Fetch webpage content with RAG-enhanced retrieval. Returns top-K relevant chunks from cache or web fetch."
)
async def fetch_webpage(url: str, use_cache: bool = True, max_retries: int = 3) -> Dict:
    """
    Fetch webpage with RAG: Check cache → If cached, return top-K chunks, else fetch + chunk + embed + store.

    Args:
        url: Full URL of the webpage to fetch
        use_cache: Whether to check cache first (default: True)
        max_retries: Maximum retry attempts for web fetch (default: 3)

    Returns:
        Dictionary containing:
        - url: The fetched URL
        - title: Page title
        - cached: Boolean indicating if result from cache
        - chunks: List of top-K chunk dictionaries with keys:
            - chunk_id: Unique chunk identifier
            - text: Chunk text content
            - chunk_index: Position in document
            - token_count: Number of tokens
        - total_chunks: Total number of chunks stored
        - embedding_model: Model used for embeddings
    """
    logger.info(f"🌐 Tool: fetch_webpage | URL: {url} | use_cache={use_cache}")

    # Import services (lazy import to avoid circular dependencies)
    from app.services.chunking_service import LangChainChunkingService
    from app.services.embedding_service import OllamaEmbeddingService
    from app.implementations.vector_storage import DynamoDBVectorStorage
    from app.config import settings

    # Initialize services
    chunking_service = LangChainChunkingService()
    embedding_service = OllamaEmbeddingService()
    vector_storage = DynamoDBVectorStorage()

    try:
        # STEP 1: Check cache if enabled
        if use_cache:
            logger.debug(f"🔍 Checking cache for {url}...")
            cached_chunks = await vector_storage.get_chunks_by_url(url)

            if cached_chunks:
                # Cache hit! Return chunks within token budget
                chunks_list = [
                    {
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.chunk_text,
                        "chunk_index": chunk.chunk_index,
                        "token_count": chunk.token_count
                    }
                    for chunk in cached_chunks
                ]
                top_chunks_list, total_tokens = _select_chunks_within_budget(chunks_list, MAX_FETCH_TOKENS)

                logger.info(
                    f"✅ Cache HIT for {url} | Returning {len(top_chunks_list)}/{len(cached_chunks)} chunks ({total_tokens} tokens)"
                )

                return {
                    "url": url,
                    "title": cached_chunks[0].source_url.split('/')[2] if cached_chunks else url,
                    "cached": True,
                    "chunks": top_chunks_list,
                    "total_chunks": len(cached_chunks),
                    "embedding_model": settings.EMBEDDING_MODEL
                }

            logger.debug(f"❌ Cache MISS for {url} | Fetching from web...")

        # STEP 2: Fetch from web with WAF bypass and retry
        response = await _fetch_with_retry(url, max_retries)

        # STEP 3: Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove noise elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()

        # Extract title
        title = soup.title.string if soup.title else url.split('/')[2]

        # Extract text
        text = soup.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned_text = '\n'.join(lines)

        if not cleaned_text or len(cleaned_text) < 100:
            logger.warning(f"⚠️ Extracted text too short for {url} ({len(cleaned_text)} chars)")
            return {
                "error": f"Insufficient content extracted from {url} ({len(cleaned_text)} chars)"
            }

        logger.info(
            f"✅ Fetched '{title}' from {url} ({len(cleaned_text)} chars)"
        )

        # STEP 4: Chunk text using LangChain
        text_chunks = await chunking_service.chunk_text(cleaned_text, url)

        logger.info(f"📄 Chunked into {len(text_chunks)} chunks")

        # STEP 5: Generate embeddings for chunks
        chunk_texts = [chunk.text for chunk in text_chunks]
        embeddings = await embedding_service.embed_batch(chunk_texts)

        logger.info(f"🧠 Generated {len(embeddings)} embeddings")

        # STEP 6: Store chunks with embeddings and TTL
        chunks_to_store = [
            {
                "chunk_id": text_chunks[i].chunk_id,
                "chunk_text": text_chunks[i].text,
                "embedding_vector": embeddings[i].vector,
                "chunk_index": text_chunks[i].chunk_index,
                "token_count": text_chunks[i].token_count
            }
            for i in range(len(text_chunks))
        ]

        stored_count = await vector_storage.store_chunks(
            url,
            chunks_to_store,
            ttl_hours=settings.VECTOR_CACHE_TTL_HOURS
        )

        logger.info(
            f"💾 Stored {stored_count} chunks with "
            f"TTL={settings.VECTOR_CACHE_TTL_HOURS}h"
        )

        # STEP 7: Return chunks within token budget
        chunks_list = [
            {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "chunk_index": chunk.chunk_index,
                "token_count": chunk.token_count
            }
            for chunk in text_chunks
        ]
        top_chunks_list, total_tokens = _select_chunks_within_budget(chunks_list, MAX_FETCH_TOKENS)

        logger.info(
            f"📄 Returning {len(top_chunks_list)}/{len(text_chunks)} chunks ({total_tokens} tokens)"
        )

        return {
            "url": url,
            "title": title,
            "cached": False,
            "chunks": top_chunks_list,
            "total_chunks": len(text_chunks),
            "embedding_model": settings.EMBEDDING_MODEL
        }

    except httpx.TimeoutException:
        logger.error(f"❌ Timeout fetching {url} after {max_retries} retries")
        return {"error": f"Timeout fetching {url} (>{max_retries * 30}s)"}
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ HTTP {e.response.status_code}: {url}")
        return {"error": f"HTTP {e.response.status_code} error: {url}"}
    except Exception as e:
        logger.error(f"❌ Tool: fetch_webpage | Error: {str(e)}", exc_info=True)
        return {"error": f"Failed to fetch {url}: {str(e)}"}
