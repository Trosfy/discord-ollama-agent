"""Brain search tool implementation.

Searches the user's knowledge base (Obsidian vault) using
semantic search via embeddings. Returns relevant notes
that agents can use to inform their responses.
"""
import json
import logging
from typing import Any, Dict, List

from app.core.context import ExecutionContext
from app.core.container import Container
from app.core.interfaces.tool import ToolResult
from app.core.interfaces.services import IBrainService

logger = logging.getLogger(__name__)


class BrainSearchTool:
    """
    Tool for searching the user's knowledge base.

    Uses IBrainService to perform semantic search across
    the user's Obsidian notes. Returns summaries of relevant
    notes that agents can use for context.
    """

    name = "brain_search"
    description = """Search the user's knowledge base (Obsidian notes) for relevant information.
Use this when you need to:
- Find information the user has previously written down
- Look up project documentation or notes
- Recall past decisions or context
- Find code snippets or technical notes

Returns matching notes with relevance scores. Use fetch_note to get full content."""

    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query. Use natural language to describe what you're looking for."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5)",
                "default": 5
            },
        },
        "required": ["query"]
    }

    def __init__(
        self,
        context: ExecutionContext,
        container: Container,
        brain_service: IBrainService = None,
    ):
        """
        Initialize the brain search tool.

        Args:
            context: Execution context.
            container: DI container for service resolution.
            brain_service: Optional brain service instance.
        """
        self._context = context
        self._container = container
        self._brain_service = brain_service

    async def _get_brain_service(self) -> IBrainService:
        """Get or resolve brain service."""
        if self._brain_service:
            return self._brain_service

        # Try to resolve from container
        brain_service = self._container.try_resolve(IBrainService)
        if brain_service:
            self._brain_service = brain_service
            return brain_service

        # No brain service available
        return None

    async def execute(
        self,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Search the knowledge base.

        Args:
            params: Tool parameters (query, limit).
            context: Execution context.

        Returns:
            ToolResult with search results as JSON.
        """
        query = params.get("query", "")
        limit = params.get("limit", 5)

        if not query:
            return ToolResult(
                content=json.dumps({"error": "Query is required", "results": []}),
                success=False,
                error="Query is required"
            )

        brain_service = await self._get_brain_service()
        if not brain_service:
            return ToolResult(
                content=json.dumps({
                    "error": "Brain service not available",
                    "results": [],
                    "hint": "Knowledge base search is not configured"
                }),
                success=False,
                error="Brain service not available"
            )

        try:
            # Perform search
            results = await brain_service.search(query=query, limit=limit)

            # Format results for agent consumption
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "path": result.get("path", ""),
                    "title": result.get("title", "Untitled"),
                    "score": result.get("score", 0.0),
                    "snippet": result.get("snippet", "")[:500],  # Truncate snippets
                    "tags": result.get("tags", []),
                })

            logger.info(f"Brain search for '{query}' returned {len(formatted_results)} results")

            return ToolResult(
                content=json.dumps({
                    "query": query,
                    "count": len(formatted_results),
                    "results": formatted_results,
                }),
                success=True,
            )

        except Exception as e:
            logger.error(f"Brain search error: {e}")
            return ToolResult(
                content=json.dumps({
                    "error": str(e),
                    "results": []
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


def create_brain_search_tool(
    context: ExecutionContext,
    container: Container,
) -> BrainSearchTool:
    """
    Factory function to create brain_search tool.

    Args:
        context: Execution context.
        container: DI container for service resolution.

    Returns:
        Configured BrainSearchTool instance.
    """
    # Try to get brain service from container
    brain_service = container.try_resolve(IBrainService)

    return BrainSearchTool(
        context=context,
        container=container,
        brain_service=brain_service,
    )
