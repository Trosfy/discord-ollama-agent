"""Web search tool implementation.

Searches the web using SearXNG (self-hosted metasearch engine).
Falls back to DuckDuckGo instant answer API only if SearXNG returns no results.
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import aiohttp

from app.core.context import ExecutionContext
from app.core.container import Container
from app.core.interfaces.tool import ToolResult

logger = logging.getLogger(__name__)

# Default SearXNG instance (local)
DEFAULT_SEARXNG_HOST = "http://localhost:8080"

# DuckDuckGo instant answer API (fallback)
DUCKDUCKGO_API = "https://api.duckduckgo.com/"


class WebSearchTool:
    """
    Tool for searching the web using SearXNG.

    SearXNG is a privacy-focused metasearch engine that aggregates
    results from multiple search engines with a clean JSON API.
    """

    name = "web_search"
    description = """Search the web for information.
Use this when you need to:
- Find current information not in the knowledge base
- Research topics, news, or documentation
- Look up technical information or tutorials
- Find answers to questions requiring external knowledge

Returns search results with titles, URLs, and snippets."""

    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query"
            },
            "num_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5, max: 10)",
                "default": 5
            },
            "categories": {
                "type": "string",
                "description": "Search category (general, images, news, science, it)",
                "default": "general"
            },
        },
        "required": ["query"]
    }

    def __init__(
        self,
        context: ExecutionContext,
        container: Container,
        searxng_host: str = None,
    ):
        """
        Initialize the web search tool.

        Args:
            context: Execution context.
            container: DI container for service resolution.
            searxng_host: SearXNG instance URL.
        """
        self._context = context
        self._container = container
        self._searxng_host = searxng_host or DEFAULT_SEARXNG_HOST
        self._session: Optional[aiohttp.ClientSession] = None
        logger.info(f"WebSearchTool initialized with SearXNG host: {self._searxng_host}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "TroiseAI/1.0 (Local Agent)",
                    "Accept": "application/json",
                }
            )
        return self._session

    async def _search_searxng(
        self,
        query: str,
        num_results: int = 5,
        categories: str = "general",
    ) -> List[Dict[str, str]]:
        """
        Search using SearXNG JSON API.

        Args:
            query: Search query.
            num_results: Maximum results to return.
            categories: Search category.

        Returns:
            List of search results.
        """
        session = await self._get_session()

        params = {
            "q": query,
            "format": "json",
            "categories": categories,
            "safesearch": "0",
        }

        try:
            async with session.get(
                f"{self._searxng_host}/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    logger.warning(f"SearXNG returned status {response.status}")
                    return []

                data = await response.json()

                # SearXNG returns results in 'results' array
                raw_results = data.get("results", [])

                results = []
                for r in raw_results[:num_results]:
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", ""),
                        "engine": r.get("engine", ""),
                    })

                return results

        except asyncio.TimeoutError:
            logger.error("SearXNG search timed out after 30 seconds")
            return []
        except aiohttp.ClientError as e:
            logger.error(f"SearXNG search error: {e}")
            return []

    async def _search_instant_answer(self, query: str) -> Optional[Dict[str, str]]:
        """
        Get DuckDuckGo instant answer if available.

        Args:
            query: Search query.

        Returns:
            Instant answer dict or None.
        """
        session = await self._get_session()

        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }

        try:
            async with session.get(
                DUCKDUCKGO_API,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    return None

                data = await response.json()

                # Check for abstract/answer
                if data.get("Abstract"):
                    return {
                        "type": "instant_answer",
                        "title": data.get("Heading", query),
                        "text": data.get("Abstract"),
                        "source": data.get("AbstractSource", ""),
                        "url": data.get("AbstractURL", ""),
                    }

                if data.get("Answer"):
                    return {
                        "type": "instant_answer",
                        "title": query,
                        "text": data.get("Answer"),
                        "source": "DuckDuckGo",
                        "url": "",
                    }

                return None

        except asyncio.TimeoutError:
            logger.warning("DuckDuckGo instant answer timed out")
            return None
        except (aiohttp.ClientError, json.JSONDecodeError) as e:
            logger.warning(f"DuckDuckGo instant answer error: {e}")
            return None

    async def execute(
        self,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Search the web.

        Args:
            params: Tool parameters (query, num_results, categories).
            context: Execution context.

        Returns:
            ToolResult with search results as JSON.
        """
        query = params.get("query", "").strip()
        num_results = min(params.get("num_results", 5), 10)
        categories = params.get("categories", "general")

        if not query:
            return ToolResult(
                content=json.dumps({
                    "error": "Query is required",
                    "results": []
                }),
                success=False,
                error="Query is required"
            )

        try:
            # Try SearXNG first (primary search engine)
            search_results = await self._search_searxng(
                query=query,
                num_results=num_results,
                categories=categories,
            )

            # Only fall back to DuckDuckGo if SearXNG returned no results
            instant_answer = None
            if not search_results:
                logger.info("SearXNG returned no results, trying DuckDuckGo fallback")
                instant_answer = await self._search_instant_answer(query)

            if not search_results and not instant_answer:
                return ToolResult(
                    content=json.dumps({
                        "query": query,
                        "count": 0,
                        "results": [],
                        "instant_answer": None,
                        "message": "No results found"
                    }),
                    success=True,
                )

            logger.info(f"Web search for '{query}' returned {len(search_results)} results")

            return ToolResult(
                content=json.dumps({
                    "query": query,
                    "count": len(search_results),
                    "results": search_results,
                    "instant_answer": instant_answer,
                }),
                success=True,
            )

        except asyncio.TimeoutError:
            error_msg = "Web search timed out"
            logger.error(error_msg)
            return ToolResult(
                content=json.dumps({
                    "error": error_msg,
                    "results": []
                }),
                success=False,
                error=error_msg
            )
        except Exception as e:
            error_msg = str(e) or f"Unexpected error: {type(e).__name__}"
            logger.error(f"Web search error: {error_msg}")
            return ToolResult(
                content=json.dumps({
                    "error": error_msg,
                    "results": []
                }),
                success=False,
                error=error_msg
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


def create_web_search_tool(
    context: ExecutionContext,
    container: Container,
) -> WebSearchTool:
    """
    Factory function to create web_search tool.

    Args:
        context: Execution context.
        container: DI container for service resolution.

    Returns:
        Configured WebSearchTool instance.
    """
    import os

    # Get SearXNG host from environment or config
    searxng_host = os.environ.get("SEARXNG_HOST")

    if not searxng_host:
        # Fall back to config if available
        from app.core.config import Config
        config = container.try_resolve(Config)
        if config and hasattr(config, 'searxng') and config.searxng:
            searxng_host = config.searxng.get("host")

    return WebSearchTool(
        context=context,
        container=container,
        searxng_host=searxng_host,
    )
