"""Recall tool implementation.

Allows agents to retrieve learned information about the user
from DynamoDB ephemeral memory. Can query by category or
get all memories.

Memory categories:
- expertise: User skills and knowledge areas
- preference: User preferences and style
- project: Project-specific context
- fact: Factual information about the user
"""
import json
import logging
from typing import Any, Dict, List

from app.core.context import ExecutionContext
from app.core.container import Container
from app.core.interfaces.tool import ToolResult
from app.core.interfaces.services import IUserMemory

logger = logging.getLogger(__name__)

# Valid memory categories
VALID_CATEGORIES = {"expertise", "preference", "project", "fact"}


class RecallTool:
    """
    Tool for retrieving learned information about the user.

    Retrieves memories from DynamoDB that were stored using the
    remember tool. Can filter by category and minimum confidence.
    """

    name = "recall"
    description = """Retrieve learned information about the user from memory.
Use this when you need to:
- Check what you know about the user's skills
- Recall user preferences
- Get project-specific context
- Review learned facts

You can query all memories or filter by category.
Higher confidence memories are more reliable.

Categories:
- expertise: Skills and knowledge
- preference: Preferences and style
- project: Project context
- fact: General facts

Set min_confidence higher (0.7+) for important decisions."""

    parameters = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["expertise", "preference", "project", "fact"],
                "description": "Filter by category (optional, omit to get all)"
            },
            "key": {
                "type": "string",
                "description": "Get a specific memory by key (optional)"
            },
            "min_confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.0,
                "description": "Minimum confidence threshold (default: 0, returns all)"
            }
        },
        "required": []
    }

    def __init__(
        self,
        context: ExecutionContext,
        container: Container,
        memory_service: IUserMemory = None,
    ):
        """
        Initialize the recall tool.

        Args:
            context: Execution context.
            container: DI container for service resolution.
            memory_service: Optional memory service instance.
        """
        self._context = context
        self._container = container
        self._memory_service = memory_service

    async def _get_memory_service(self) -> IUserMemory:
        """Get or resolve memory service."""
        if self._memory_service:
            return self._memory_service

        # Try to resolve from container
        memory_service = self._container.try_resolve(IUserMemory)
        if memory_service:
            self._memory_service = memory_service
            return memory_service

        return None

    async def execute(
        self,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Retrieve memory items.

        Args:
            params: Tool parameters (category, key, min_confidence).
            context: Execution context.

        Returns:
            ToolResult with memories.
        """
        category = params.get("category")
        key = params.get("key")
        min_confidence = params.get("min_confidence", 0.0)

        # Validate category if provided
        if category and category not in VALID_CATEGORIES:
            return ToolResult(
                content=json.dumps({
                    "error": f"Invalid category '{category}'. Must be one of: {list(VALID_CATEGORIES)}",
                    "memories": []
                }),
                success=False,
                error=f"Invalid category: {category}"
            )

        # Get user_id from context
        user_id = context.user_profile.user_id if context.user_profile else "default"

        memory_service = await self._get_memory_service()
        if not memory_service:
            return ToolResult(
                content=json.dumps({
                    "error": "Memory service not available",
                    "memories": [],
                    "hint": "User memory is not configured"
                }),
                success=False,
                error="Memory service not available"
            )

        try:
            # Get specific memory by key
            if category and key:
                memory = await memory_service.get(user_id, category, key)
                if memory:
                    memories = [self._format_memory(memory)]
                else:
                    memories = []
            # Query by category
            elif category:
                raw_memories = await memory_service.query(user_id, category)
                memories = [
                    self._format_memory(m) for m in raw_memories
                    if m.get("confidence", 0) >= min_confidence
                ]
            # Get all memories
            else:
                raw_memories = await memory_service.get_all(user_id)
                memories = [
                    self._format_memory(m) for m in raw_memories
                    if m.get("confidence", 0) >= min_confidence
                ]

            # Sort by confidence (highest first)
            memories.sort(key=lambda x: x.get("confidence", 0), reverse=True)

            # Group by category for easier consumption
            grouped = {}
            for mem in memories:
                cat = mem.get("category", "unknown")
                if cat not in grouped:
                    grouped[cat] = []
                grouped[cat].append(mem)

            logger.info(
                f"Recalled {len(memories)} memories for user {user_id} "
                f"(category: {category or 'all'}, min_confidence: {min_confidence})"
            )

            return ToolResult(
                content=json.dumps({
                    "count": len(memories),
                    "filter": {
                        "category": category,
                        "key": key,
                        "min_confidence": min_confidence,
                    },
                    "memories": memories,
                    "by_category": grouped,
                }),
                success=True,
            )

        except Exception as e:
            logger.error(f"Recall tool error: {e}")
            return ToolResult(
                content=json.dumps({
                    "error": str(e),
                    "memories": []
                }),
                success=False,
                error=str(e)
            )

    def _format_memory(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """Format a memory item for output."""
        return {
            "category": memory.get("category", ""),
            "key": memory.get("key", ""),
            "value": memory.get("value", ""),
            "confidence": float(memory.get("confidence", 0)),
            "source": memory.get("source", "learned"),
            "learned_by": memory.get("learned_by"),
            "updated_at": memory.get("updated_at"),
        }

    def to_schema(self) -> Dict[str, Any]:
        """Return tool schema for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


def create_recall_tool(
    context: ExecutionContext,
    container: Container,
) -> RecallTool:
    """
    Factory function to create recall tool.

    Args:
        context: Execution context.
        container: DI container for service resolution.

    Returns:
        Configured RecallTool instance.
    """
    memory_service = container.try_resolve(IUserMemory)

    return RecallTool(
        context=context,
        container=container,
        memory_service=memory_service,
    )
