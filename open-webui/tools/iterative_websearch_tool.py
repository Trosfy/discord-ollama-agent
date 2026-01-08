"""
title: Iterative Web Research (Advanced)
author: community, enhanced by claude
version: 2.1.0
required_open_webui_version: 0.3.30
requirements: beautifulsoup4, requests, numpy, langchain-text-splitters

Advanced web research tool that:
- Fetches and analyzes full web page content
- Uses embeddings for semantic relevance
- MMR ranking for diverse sources
- Returns most relevant chunks from multiple pages

Usage: Call run(query) or research(query) - NOT internal methods!

Requirements:
- Ollama with embedding model (e.g., qwen3-embedding:4b)
- Optional: SearXNG (can use public instance or DuckDuckGo fallback)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import textwrap
import urllib.parse
from collections import defaultdict
from typing import Dict, List, Tuple
import random
import time

import numpy as np
import requests
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup

# Try to import web loader, fallback to simple requests if not available
try:
    from open_webui.retrieval.web.utils import get_web_loader
    HAS_WEB_LOADER = True
except ImportError:
    HAS_WEB_LOADER = False
    logging.warning("open_webui.retrieval not available, using simple fetcher")

# Logging setup
logger = logging.getLogger("iterative_websearch")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


class Tools:
    """Optimized iterative web-research helper for Open WebUI."""

    class Valves(BaseModel):
        class Config:
            arbitrary_types_allowed = True

        # Search backend
        use_searxng: bool = Field(
            default=True,
            description="Use SearXNG (local instance). If false, uses DuckDuckGo",
        )
        searxng_url: str = Field(
            default="http://searxng:8080",
            description="SearXNG URL (local instance via docker-compose)",
        )

        # Embedding endpoint (Ollama-compatible)
        embedding_api_url: str = Field(
            default="http://host.docker.internal:11434/api/embeddings",
            description="Ollama embedding endpoint",
        )
        embedding_model_name: str = Field(
            default="qwen3-embedding:4b",
            description="Embedding model (must be pulled in Ollama)",
        )

        # Search settings
        max_results: int = Field(
            default=8,
            description="Max URLs to fetch per search",
        )

        # Fetching settings (Anti-WAF)
        requests_per_second: float = Field(
            default=2.0,
            description="Rate limit for page fetching"
        )
        verify_ssl: bool = Field(
            default=True,
            description="Verify SSL certificates"
        )
        fetch_timeout: int = Field(
            default=15,
            description="Timeout per page fetch (seconds)",
        )
        retry_attempts: int = Field(
            default=2,
            description="Number of retry attempts for failed fetches (reduced from 3 for faster completion)",
        )
        retry_delay: float = Field(
            default=1.5,
            description="Base delay between retries (seconds)",
        )
        use_random_delays: bool = Field(
            default=True,
            description="Add random delays to appear more human",
        )

        # Text processing
        chunk_size: int = Field(
            default=1000,
            description="Characters per chunk"
        )
        chunk_overlap: int = Field(
            default=100,
            description="Character overlap between chunks"
        )

        # Embedding settings
        batch_size: int = Field(
            default=10,
            description="Chunks per embedding batch"
        )
        max_embed_chars: int = Field(
            default=8000,
            description="Max characters to embed per chunk"
        )

        # Ranking parameters
        similarity_threshold: float = Field(
            default=0.3,
            description="Minimum similarity to include chunk (0-1)",
        )
        top_k: int = Field(
            default=5,
            description="Number of top chunks to return"
        )
        mmr_lambda: float = Field(
            default=0.6,
            description="MMR diversity parameter (0=diverse, 1=relevant)",
        )
        domain_penalty: float = Field(
            default=0.5,
            description="Penalty for multiple chunks from same domain",
        )

        # Output format
        include_metadata: bool = Field(
            default=True,
            description="Include search metadata in response",
        )
        include_sources: bool = Field(
            default=True,
            description="Include source URLs in response",
        )

        # Debug
        debug: bool = Field(
            default=False,
            description="Enable debug logging"
        )

    def __init__(self, **kw):
        self.valves = self.Valves(**kw)
        self._embed_dim: int | None = None
        self.session = requests.Session()
        # Enable connection pooling and keep-alive
        self.session.mount('http://', requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20))
        self.session.mount('https://', requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20))

        if self.valves.debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

    def _get_random_headers(self) -> dict:
        """Generate realistic, rotating headers to avoid WAF detection"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
        ]

        accept_languages = [
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "en-US,en;q=0.9,th;q=0.8",
            "en-US,en;q=0.9,es;q=0.8",
        ]

        return {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": random.choice(accept_languages),
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "Referer": "https://www.google.com/",
        }

    def __call__(self, query: str) -> str:
        """Main entry point for the tool"""
        return self.research(query)

    def run(self, query: str = None, topn: int = None, max_results: int = None, **kwargs) -> str:
        """
        Flexible research interface that accepts multiple parameter names.

        :param query: Research query string
        :param topn: Number of top results (ignored - configured in valves)
        :param max_results: Alias for topn (ignored - configured in valves)
        :param kwargs: Additional parameters (top_n, recency_days, source, etc.) - all ignored

        Note: This tool uses embeddings and returns top_k chunks based on
        similarity threshold settings in valves, not the topn parameter.
        """
        # Handle query from kwargs if not provided
        if query is None:
            query = kwargs.get('query', '')

        # Ignore all other parameters (top_n, recency_days, source, etc.)
        # This tool uses valves configuration for all settings

        return self.research(query)

    def research(self, query: str) -> str:
        """Perform iterative web research on a query"""
        try:
            # Stage 1: SEARCH
            logger.info("🔍 [SEARCH] query='%s'", query)
            urls = self._search(query)

            if not urls:
                return self._format_output(
                    "❌ No search results found. Try rephrasing your query.",
                    [],
                    []
                )

            logger.info("✓ [SEARCH] found %d URLs (using %d)", len(urls), min(len(urls), self.valves.max_results))
            urls = urls[: self.valves.max_results]

            # Stage 2: FETCH & PARSE
            logger.info("📥 [FETCH] downloading pages...")
            pages = self._fetch_pages(urls)

            if not pages:
                return self._format_output(
                    "❌ Failed to fetch any pages. They may be blocking scrapers.",
                    [],
                    urls
                )

            logger.info("✓ [FETCH] got %d pages", len(pages))

            # Stage 3: CHUNK
            logger.info("✂️ [CHUNK] splitting text...")
            chunks, chunk_domains, chunk_urls = self._chunk_pages(pages)

            if not chunks:
                return self._format_output(
                    "❌ No content could be extracted from pages.",
                    [],
                    urls
                )

            logger.info("✓ [CHUNK] created %d chunks", len(chunks))

            # Stage 4: EMBED
            logger.info("🧮 [EMBED] computing embeddings...")
            query_embedding = self._get_embedding(query)

            if not query_embedding:
                return self._format_output(
                    "❌ Failed to compute query embedding. Check Ollama connection.",
                    [],
                    urls
                )

            chunk_embeddings = self._embed_chunks(chunks)

            # Filter by similarity threshold
            relevant = []
            for i, emb in enumerate(chunk_embeddings):
                if emb:
                    sim = self._cosine_similarity(query_embedding, emb)
                    if sim >= self.valves.similarity_threshold:
                        relevant.append((chunks[i], chunk_domains[i], chunk_urls[i], emb, sim))

            if not relevant:
                return self._format_output(
                    f"❌ No chunks exceeded similarity threshold ({self.valves.similarity_threshold}).\n"
                    "Try lowering the similarity_threshold in settings.",
                    [],
                    urls
                )

            logger.info("✓ [EMBED] %d/%d chunks above threshold", len(relevant), len(chunks))

            # Stage 5: RANK with MMR
            logger.info("📊 [RANK] selecting top chunks with MMR...")
            selected = self._mmr_select(
                query_embedding,
                relevant,
                k=self.valves.top_k
            )

            logger.info("✓ [RANK] selected %d chunks from %d domains",
                       len(selected),
                       len(set(d for _, d, _, _, _ in selected)))

            # Format output
            answer = self._format_results(selected, urls)
            return answer

        except Exception as e:
            logger.error("❌ Research failed: %s", e, exc_info=True)
            return f"❌ Error during research: {str(e)}"

    def _search(self, query: str) -> List[str]:
        """Search using SearXNG or DuckDuckGo fallback"""
        if self.valves.use_searxng:
            return self._search_searxng(query)
        else:
            return self._search_duckduckgo(query)

    def _search_searxng(self, query: str) -> List[str]:
        """Search using SearXNG"""
        try:
            r = requests.get(
                f"{self.valves.searxng_url}/search",
                params={"q": query, "format": "json"},
                timeout=15,
            )
            r.raise_for_status()
            return [res.get("url", "") for res in r.json().get("results", []) if res.get("url")]
        except Exception as e:
            logger.error("SearXNG search failed: %s", e)
            logger.info("Falling back to DuckDuckGo...")
            return self._search_duckduckgo(query)

    def _search_duckduckgo(self, query: str) -> List[str]:
        """Search using DuckDuckGo HTML"""
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            results = soup.find_all("a", class_="result__a")

            urls = []
            for result in results:
                href = result.get("href")
                if href and href.startswith("http"):
                    urls.append(href)

            return urls

        except Exception as e:
            logger.error("DuckDuckGo search failed: %s", e)
            return []

    def _fetch_pages(self, urls: List[str]) -> List[Tuple[str, str, str]]:
        """Fetch and parse web pages with anti-WAF protection. Returns (content, domain, url)"""
        pages = []

        for url in urls:
            # Add human-like delay
            if self.valves.use_random_delays:
                delay = (1.0 / self.valves.requests_per_second) + random.uniform(0, 1.5)
                time.sleep(delay)
            else:
                time.sleep(1.0 / self.valves.requests_per_second)

            # Try with retries
            for attempt in range(self.valves.retry_attempts):
                try:
                    # Exponential backoff on retries
                    if attempt > 0:
                        retry_wait = self.valves.retry_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.debug("⟳ Retry %d/%d for %s (waiting %.1fs)",
                                   attempt + 1, self.valves.retry_attempts, url, retry_wait)
                        time.sleep(retry_wait)

                    # Get fresh headers for each request
                    headers = self._get_random_headers()

                    response = self.session.get(
                        url,
                        headers=headers,
                        timeout=self.valves.fetch_timeout,
                        verify=self.valves.verify_ssl,
                        allow_redirects=True
                    )

                    # Check for rate limiting
                    if response.status_code == 429:
                        logger.warning("⚠ Rate limited (429) on %s, attempt %d/%d",
                                     url, attempt + 1, self.valves.retry_attempts)
                        if attempt < self.valves.retry_attempts - 1:
                            time.sleep(self.valves.retry_delay * 3)  # Longer wait for 429
                            continue
                        else:
                            raise Exception("Rate limited after all retries")

                    # Check for bot detection
                    if response.status_code == 403:
                        logger.warning("⚠ Forbidden (403) on %s - possible bot detection", url)
                        if attempt < self.valves.retry_attempts - 1:
                            continue
                        else:
                            raise Exception("Access forbidden - likely bot detection")

                    response.raise_for_status()

                    # Parse content
                    soup = BeautifulSoup(response.text, "html.parser")

                    # Remove unwanted elements
                    for element in soup(["script", "style", "nav", "footer", "header", "aside", "form", "button"]):
                        element.decompose()

                    # Get text
                    text = soup.get_text(separator="\n", strip=True)

                    # Clean up whitespace
                    lines = [line.strip() for line in text.splitlines() if line.strip()]
                    text = "\n".join(lines)

                    # Validate content length
                    if len(text) > 100:  # Minimum content length
                        domain = urllib.parse.urlparse(url).netloc
                        pages.append((text, domain, url))
                        logger.debug("✓ Fetched %s (%d chars) on attempt %d",
                                   domain, len(text), attempt + 1)
                        break  # Success, exit retry loop
                    else:
                        logger.debug("✗ Skipped %s (too short: %d chars)", url, len(text))
                        break  # Don't retry if content is just too short

                except requests.exceptions.Timeout:
                    logger.debug("⏱ Timeout on %s (attempt %d/%d)",
                               url, attempt + 1, self.valves.retry_attempts)
                    if attempt == self.valves.retry_attempts - 1:
                        logger.debug("✗ Failed %s after %d timeouts", url, self.valves.retry_attempts)

                except requests.exceptions.RequestException as e:
                    logger.debug("✗ Request error on %s (attempt %d/%d): %s",
                               url, attempt + 1, self.valves.retry_attempts, str(e))
                    if attempt == self.valves.retry_attempts - 1:
                        logger.debug("✗ Failed %s after %d attempts", url, self.valves.retry_attempts)

                except Exception as e:
                    logger.debug("✗ Unexpected error on %s: %s", url, str(e))
                    break  # Don't retry on unexpected errors

        return pages

    def _chunk_pages(self, pages: List[Tuple[str, str, str]]) -> Tuple[List[str], List[str], List[str]]:
        """Split pages into chunks. Returns (chunks, domains, urls)"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.valves.chunk_size,
            chunk_overlap=self.valves.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        chunks = []
        chunk_domains = []
        chunk_urls = []

        for text, domain, url in pages:
            page_chunks = splitter.split_text(text)
            chunks.extend(page_chunks)
            chunk_domains.extend([domain] * len(page_chunks))
            chunk_urls.extend([url] * len(page_chunks))

        return chunks, chunk_domains, chunk_urls

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text using Ollama"""
        try:
            text = text[: self.valves.max_embed_chars]

            response = requests.post(
                self.valves.embedding_api_url,
                json={
                    "model": self.valves.embedding_model_name,
                    "prompt": text
                },
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            embedding = data.get("embedding", [])

            if self._embed_dim is None and embedding:
                self._embed_dim = len(embedding)
                logger.debug("Embedding dimension: %d", self._embed_dim)

            return embedding

        except Exception as e:
            logger.error("Embedding failed: %s", e)
            return []

    def _embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        """Embed multiple chunks in batches"""
        embeddings = []

        for i in range(0, len(chunks), self.valves.batch_size):
            batch = chunks[i : i + self.valves.batch_size]

            for chunk in batch:
                emb = self._get_embedding(chunk)
                embeddings.append(emb)
                time.sleep(0.1)  # Small delay between requests

        return embeddings

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors"""
        if not a or not b or len(a) != len(b):
            return 0.0

        va = np.array(a, dtype=np.float32)
        vb = np.array(b, dtype=np.float32)

        norm_a = np.linalg.norm(va)
        norm_b = np.linalg.norm(vb)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(va, vb) / (norm_a * norm_b))

    def _mmr_select(
        self,
        query_emb: List[float],
        relevant: List[Tuple[str, str, str, List[float], float]],
        k: int
    ) -> List[Tuple[str, str, str, List[float], float]]:
        """Select top-k chunks using Maximal Marginal Relevance"""
        if len(relevant) <= k:
            return relevant

        selected = []
        remaining = list(range(len(relevant)))
        domain_counts = defaultdict(int)

        # Sort by similarity initially
        sorted_indices = sorted(remaining, key=lambda i: relevant[i][4], reverse=True)

        for _ in range(k):
            if not remaining:
                break

            best_idx = None
            best_score = -float('inf')

            for idx in remaining:
                chunk, domain, url, emb, sim = relevant[idx]

                if not selected:
                    # First selection: just pick highest similarity
                    score = sim
                else:
                    # MMR: balance relevance and novelty
                    max_sim_to_selected = max(
                        self._cosine_similarity(emb, relevant[sel_idx][3])
                        for sel_idx in [s[0] for s in selected]
                    )

                    score = (
                        self.valves.mmr_lambda * sim
                        - (1 - self.valves.mmr_lambda) * max_sim_to_selected
                    )

                    # Apply domain penalty
                    score /= (1 + self.valves.domain_penalty * domain_counts[domain])

                if score > best_score:
                    best_score = score
                    best_idx = idx

            if best_idx is not None:
                selected.append((best_idx, relevant[best_idx]))
                remaining.remove(best_idx)
                domain_counts[relevant[best_idx][1]] += 1

        return [item[1] for item in selected]

    def _format_results(
        self,
        selected: List[Tuple[str, str, str, List[float], float]],
        all_urls: List[str]
    ) -> str:
        """Format selected chunks into final output"""
        # Build content
        sections = []
        seen_urls = set()

        for i, (chunk, domain, url, _, sim) in enumerate(selected, 1):
            # Clean chunk
            chunk = chunk.strip()
            if len(chunk) > 500:
                chunk = chunk[:500] + "..."

            section = f"**[{i}] {domain}** (relevance: {sim:.2f})\n{chunk}"

            if self.valves.include_sources and url not in seen_urls:
                section += f"\n🔗 {url}"
                seen_urls.add(url)

            sections.append(section)

        content = "\n\n---\n\n".join(sections)

        # Add metadata if enabled
        if self.valves.include_metadata:
            domains = [d for _, d, _, _, _ in selected]
            unique_domains = len(set(domains))

            metadata = {
                "chunks_analyzed": len(selected),
                "unique_domains": unique_domains,
                "pages_fetched": len(seen_urls),
                "urls_searched": len(all_urls)
            }

            header = f"📊 **Research Summary**: {metadata['chunks_analyzed']} relevant chunks from {metadata['unique_domains']} domains\n\n"
            content = header + content

        return content

    def _format_output(self, message: str, domains: List[str], urls: List[str]) -> str:
        """Format error or empty output"""
        return message


# For standalone testing
if __name__ == "__main__":
    tool = Tools()
    result = tool.research("What is quantum computing?")
    print(result)
