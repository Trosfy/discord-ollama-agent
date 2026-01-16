"""Web fetch tool with RAG (Retrieval-Augmented Generation) pipeline.

Fetches web pages, chunks content, generates embeddings, and caches
results in DynamoDB for efficient retrieval.

Pipeline:
1. Check cache (get_chunks_by_url)
2. Fetch HTML with configurable settings
3. Parse & clean with BeautifulSoup
4. Chunk text (ChunkingService)
5. Generate embeddings (EmbeddingService)
6. Store chunks (WebChunksAdapter with TTL)
7. Return top chunks within token budget
"""
import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types from DynamoDB."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            # Convert to int if whole number, else float
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)

import aiohttp
from bs4 import BeautifulSoup

from app.core.context import ExecutionContext
from app.core.container import Container
from app.core.config import Config, RAGConfig
from app.core.interfaces.tool import ToolResult
from app.adapters.dynamodb import DynamoDBClient, TroiseWebChunksAdapter
from app.services import LangChainChunkingService, EmbeddingService

logger = logging.getLogger(__name__)


class WebFetchTool:
    """
    Tool for fetching and extracting content from web pages using RAG.

    Uses BeautifulSoup for content extraction with configurable tag removal.
    Caches chunks with embeddings in DynamoDB with domain-specific TTLs.

    Features:
    - Intelligent caching with configurable TTL
    - Token-based chunking for consistent retrieval
    - Configurable HTML parsing (remove tags, extract title)
    - Token budget management for response size
    """

    name = "web_fetch"
    description = """Fetch and read the content of a web page.
Use this when you need to:
- Read the full content of a web page found via search
- Extract information from a specific URL
- Get detailed content from documentation or articles

Returns the main readable content of the page, chunked and processed for context."""

    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch"
            },
            "force_refresh": {
                "type": "boolean",
                "description": "Force refresh even if cached (default: false)",
                "default": False
            },
            "max_chunks": {
                "type": "integer",
                "description": "Maximum number of chunks to return (default: from config)",
                "default": None
            },
        },
        "required": ["url"]
    }

    def __init__(
        self,
        context: ExecutionContext,
        container: Container,
        config: Optional[RAGConfig] = None,
        chunking_service: Optional[LangChainChunkingService] = None,
        embedding_service: Optional[EmbeddingService] = None,
        web_chunks_adapter: Optional[TroiseWebChunksAdapter] = None,
    ):
        """
        Initialize the web fetch tool.

        Args:
            context: Execution context.
            container: DI container for service resolution.
            config: RAG configuration (resolved from container if None).
            chunking_service: Chunking service (resolved from container if None).
            embedding_service: Embedding service (resolved from container if None).
            web_chunks_adapter: Web chunks adapter (resolved from container if None).
        """
        self._context = context
        self._container = container
        self._session: Optional[aiohttp.ClientSession] = None

        # Resolve config
        if config is None:
            app_config = container.resolve(Config)
            self._config = app_config.rag
        else:
            self._config = config

        # Resolve services (lazy - will be done on first use)
        self._chunking_service = chunking_service
        self._embedding_service = embedding_service
        self._web_chunks_adapter = web_chunks_adapter

    def _get_chunking_service(self) -> LangChainChunkingService:
        """Get or create chunking service."""
        if self._chunking_service is None:
            from app.services import create_chunking_service
            self._chunking_service = create_chunking_service(self._config)
        return self._chunking_service

    def _get_embedding_service(self) -> EmbeddingService:
        """Get or create embedding service."""
        if self._embedding_service is None:
            self._embedding_service = self._container.resolve(EmbeddingService)
        return self._embedding_service

    def _get_web_chunks_adapter(self) -> TroiseWebChunksAdapter:
        """Get or create web chunks adapter."""
        if self._web_chunks_adapter is None:
            client = self._container.resolve(DynamoDBClient)
            self._web_chunks_adapter = TroiseWebChunksAdapter(client, self._config)
        return self._web_chunks_adapter

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with configured settings."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._config.fetch.timeout_seconds),
                headers={
                    "User-Agent": self._config.fetch.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                }
            )
        return self._session

    def _validate_url(self, url: str) -> bool:
        """Validate URL is well-formed and uses http/https."""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    async def _fetch_html(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from URL.

        Args:
            url: URL to fetch.

        Returns:
            HTML content or None on error.
        """
        session = await self._get_session()

        try:
            async with session.get(
                url,
                max_redirects=self._config.fetch.max_redirects,
                allow_redirects=True,
            ) as response:
                # Check status
                if response.status != 200:
                    logger.warning(f"Fetch {url} returned status {response.status}")
                    return None

                # Check content type
                content_type = response.headers.get("Content-Type", "")
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    logger.warning(f"Non-HTML content type: {content_type}")
                    return None

                # Check content length
                content_length = response.content_length
                if content_length and content_length > self._config.fetch.max_content_bytes:
                    logger.warning(
                        f"Content too large: {content_length} > {self._config.fetch.max_content_bytes}"
                    )
                    return None

                html = await response.text()
                return html

        except aiohttp.ClientError as e:
            logger.error(f"Fetch error for {url}: {e}")
            return None

    def _parse_html(self, html: str) -> tuple[str, Optional[str]]:
        """
        Parse HTML and extract clean text using BeautifulSoup.

        Args:
            html: Raw HTML content.

        Returns:
            Tuple of (clean_text, title).
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Extract title if configured
        title = None
        if self._config.parsing.extract_title and soup.title:
            title = soup.title.string

        # Remove configured tags
        for tag_name in self._config.parsing.remove_tags:
            for element in soup.find_all(tag_name):
                element.decompose()

        # Get text with line breaks
        text = soup.get_text(separator='\n', strip=True)

        return text, title

    def _select_chunks_within_budget(
        self,
        chunks: List[Dict[str, Any]],
        max_tokens: int,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Select chunks that fit within token budget.

        Args:
            chunks: List of chunk dicts with 'token_count' key.
            max_tokens: Maximum total tokens.

        Returns:
            Tuple of (selected_chunks, total_tokens).
        """
        selected = []
        total = 0

        for chunk in chunks:
            token_count = chunk.get('token_count', 0)
            if total + token_count <= max_tokens:
                selected.append(chunk)
                total += token_count
            else:
                break

        return selected, total

    async def execute(
        self,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Fetch and extract content from a URL using RAG pipeline.

        Pipeline:
        1. Check cache
        2. Fetch HTML
        3. Parse with BeautifulSoup
        4. Chunk text
        5. Generate embeddings
        6. Store in cache
        7. Return within token budget

        Args:
            params: Tool parameters (url, force_refresh, max_chunks).
            context: Execution context.

        Returns:
            ToolResult with extracted content as JSON.
        """
        url = params.get("url", "").strip()
        force_refresh = params.get("force_refresh", False)
        max_chunks = params.get("max_chunks")

        if not url:
            return ToolResult(
                content=json.dumps({"error": "URL is required"}),
                success=False,
                error="URL is required"
            )

        if not self._validate_url(url):
            return ToolResult(
                content=json.dumps({"error": "Invalid URL format. Must be http:// or https://"}),
                success=False,
                error="Invalid URL format"
            )

        try:
            adapter = self._get_web_chunks_adapter()

            # ===== Step 1: Check cache =====
            if not force_refresh:
                cached_chunks = await adapter.get_chunks_by_url(url)
                if cached_chunks:
                    logger.info(f"Cache hit for {url}: {len(cached_chunks)} chunks")

                    # Convert to dicts for response
                    chunks_data = [
                        {
                            "chunk_index": c.chunk_index,
                            "text": c.chunk_text,
                            "token_count": c.token_count,
                        }
                        for c in cached_chunks
                    ]

                    # Select within budget
                    max_tokens = self._config.max_fetch_tokens
                    selected, total_tokens = self._select_chunks_within_budget(
                        chunks_data, max_tokens
                    )

                    # Get metadata
                    meta = await adapter.get_meta(url)

                    return ToolResult(
                        content=json.dumps({
                            "url": url,
                            "title": meta.title if meta else None,
                            "chunks": selected,
                            "total_chunks": len(cached_chunks),
                            "returned_chunks": len(selected),
                            "total_tokens": total_tokens,
                            "cached": True,
                        }, cls=DecimalEncoder),
                        success=True,
                    )

            # ===== Step 2: Fetch HTML =====
            html = await self._fetch_html(url)
            if not html:
                return ToolResult(
                    content=json.dumps({
                        "error": "Failed to fetch page content",
                        "url": url,
                    }),
                    success=False,
                    error="Failed to fetch page"
                )

            # ===== Step 3: Parse with BeautifulSoup =====
            text, title = self._parse_html(html)

            if not text or len(text.strip()) < 50:
                return ToolResult(
                    content=json.dumps({
                        "error": "No readable content found on page",
                        "url": url,
                    }),
                    success=False,
                    error="No readable content"
                )

            logger.info(f"Parsed {url}: {len(text)} chars, title='{title}'")

            # ===== Step 4: Chunk text =====
            chunking_service = self._get_chunking_service()
            text_chunks = await chunking_service.chunk_text(text, url)

            logger.info(f"Chunked into {len(text_chunks)} chunks")

            # ===== Step 5: Generate embeddings =====
            embedding_service = self._get_embedding_service()
            embeddings = []

            for chunk in text_chunks:
                embedding = await embedding_service.embed(chunk.text)
                embeddings.append(embedding)

            logger.info(f"Generated {len(embeddings)} embeddings")

            # ===== Step 6: Store in cache =====
            chunks_for_storage = [
                {
                    "chunk_id": c.chunk_id,
                    "chunk_text": c.text,
                    "chunk_index": c.chunk_index,
                    "token_count": c.token_count,
                    "start_char": c.start_char,
                    "end_char": c.end_char,
                }
                for c in text_chunks
            ]

            stored_count = await adapter.store_chunks(
                url=url,
                title=title or url,
                chunks=chunks_for_storage,
                embeddings=embeddings,
            )

            logger.info(f"Stored {stored_count} chunks for {url}")

            # ===== Step 7: Return within token budget =====
            chunks_data = [
                {
                    "chunk_index": c.chunk_index,
                    "text": c.text,
                    "token_count": c.token_count,
                }
                for c in text_chunks
            ]

            # Apply max_chunks limit if specified
            if max_chunks is not None:
                chunks_data = chunks_data[:max_chunks]

            max_tokens = self._config.max_fetch_tokens
            selected, total_tokens = self._select_chunks_within_budget(
                chunks_data, max_tokens
            )

            return ToolResult(
                content=json.dumps({
                    "url": url,
                    "title": title,
                    "chunks": selected,
                    "total_chunks": len(text_chunks),
                    "returned_chunks": len(selected),
                    "total_tokens": total_tokens,
                    "cached": False,
                }, cls=DecimalEncoder),
                success=True,
            )

        except Exception as e:
            logger.error(f"Web fetch error: {e}", exc_info=True)
            return ToolResult(
                content=json.dumps({
                    "error": str(e),
                    "url": url,
                }),
                success=False,
                error=str(e)
            )

    def to_schema(self) -> Dict[str, Any]:
        """Return tool schema for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


def create_web_fetch_tool(
    context: ExecutionContext,
    container: Container,
) -> WebFetchTool:
    """
    Factory function to create web_fetch tool.

    Args:
        context: Execution context.
        container: DI container for service resolution.

    Returns:
        Configured WebFetchTool instance.
    """
    return WebFetchTool(
        context=context,
        container=container,
    )
