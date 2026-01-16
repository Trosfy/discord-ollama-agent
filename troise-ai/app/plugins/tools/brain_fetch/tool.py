"""Brain fetch tool implementation.

Fetches full content of a note from the user's knowledge base (Obsidian vault).
Used after brain_search to get complete note content.
"""
import json
import logging
from typing import Any, Dict

from app.core.context import ExecutionContext
from app.core.container import Container
from app.core.interfaces.tool import ToolResult
from app.core.interfaces.services import IBrainService

logger = logging.getLogger(__name__)


class BrainFetchTool:
    """
    Tool for fetching full note content from the knowledge base.

    Uses IBrainService to retrieve complete content of a note
    identified by its path. Typically used after brain_search
    to get the full text of a relevant note.
    """

    name = "brain_fetch"
    description = """Fetch the full content of a note from the user's knowledge base.
Use this after brain_search when you need the complete content of a specific note.

Returns the full markdown content, frontmatter metadata, and note path.
Only fetch notes you actually need - don't fetch everything from search results."""

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the note (from brain_search results)"
            },
        },
        "required": ["path"]
    }

    def __init__(
        self,
        context: ExecutionContext,
        container: Container,
        brain_service: IBrainService = None,
    ):
        """
        Initialize the brain fetch tool.

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

        return None

    async def execute(
        self,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Fetch full note content.

        Args:
            params: Tool parameters (path).
            context: Execution context.

        Returns:
            ToolResult with note content as JSON.
        """
        path = params.get("path", "")

        if not path:
            return ToolResult(
                content=json.dumps({"error": "Path is required"}),
                success=False,
                error="Path is required"
            )

        brain_service = await self._get_brain_service()
        if not brain_service:
            return ToolResult(
                content=json.dumps({
                    "error": "Brain service not available",
                    "hint": "Knowledge base is not configured"
                }),
                success=False,
                error="Brain service not available"
            )

        try:
            # Fetch full note content
            note = await brain_service.fetch(path=path)

            if not note:
                return ToolResult(
                    content=json.dumps({
                        "error": f"Note not found: {path}",
                        "path": path,
                    }),
                    success=False,
                    error=f"Note not found: {path}"
                )

            logger.info(f"Fetched note: {path}")

            return ToolResult(
                content=json.dumps({
                    "path": note.get("path", path),
                    "title": note.get("title", "Untitled"),
                    "content": note.get("content", ""),
                    "frontmatter": note.get("frontmatter", {}),
                    "tags": note.get("tags", []),
                    "modified": note.get("modified", None),
                }),
                success=True,
            )

        except Exception as e:
            logger.error(f"Brain fetch error: {e}")
            return ToolResult(
                content=json.dumps({
                    "error": str(e),
                    "path": path
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


def create_brain_fetch_tool(
    context: ExecutionContext,
    container: Container,
) -> BrainFetchTool:
    """
    Factory function to create brain_fetch tool.

    Args:
        context: Execution context.
        container: DI container for service resolution.

    Returns:
        Configured BrainFetchTool instance.
    """
    brain_service = container.try_resolve(IBrainService)

    return BrainFetchTool(
        context=context,
        container=container,
        brain_service=brain_service,
    )
