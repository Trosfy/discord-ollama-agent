"""Remember tool implementation.

Allows agents to store learned information about the user
in DynamoDB ephemeral memory. High-confidence items can be
promoted to ai-learned.yaml for permanent storage.

Memory categories:
- expertise: User skills and knowledge areas
- preference: User preferences and style
- project: Project-specific context
- fact: Factual information about the user
"""
import json
import logging
from typing import Any, Dict

from app.core.context import ExecutionContext
from app.core.container import Container
from app.core.interfaces.tool import ToolResult
from app.core.interfaces.services import IUserMemory

logger = logging.getLogger(__name__)

# Valid memory categories
VALID_CATEGORIES = {"expertise", "preference", "project", "fact"}


class RememberTool:
    """
    Tool for storing learned information about the user.

    Stores memories in DynamoDB with confidence scores.
    High-confidence items (>0.9) can be promoted to permanent
    storage in ai-learned.yaml.

    Memories have:
    - category: Type of information (expertise, preference, etc.)
    - key: Unique identifier within category
    - value: The learned information
    - confidence: How sure we are (0.0-1.0)
    - evidence: Why we believe this
    """

    name = "remember"
    description = """Store learned information about the user for future reference.
Use this when you:
- Learn something about the user's skills or expertise
- Discover user preferences (communication style, formatting, etc.)
- Gather project-specific context
- Learn factual information about the user

Information is stored with a confidence score. Higher confidence
items may be promoted to permanent memory.

Categories:
- expertise: Skills and knowledge (e.g., "python", "kubernetes")
- preference: Preferences and style (e.g., "prefers_concise_answers")
- project: Project context (e.g., project names, tech stacks)
- fact: General facts (e.g., "works_at_startup", "timezone_utc")"""

    parameters = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["expertise", "preference", "project", "fact"],
                "description": "Category of information being remembered"
            },
            "key": {
                "type": "string",
                "description": "Unique identifier for this memory (e.g., 'python', 'prefers_concise')"
            },
            "value": {
                "type": "string",
                "description": "The information to remember (be specific and descriptive)"
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.5,
                "description": "How confident you are (0.0-1.0). Use 0.3-0.5 for inferred, 0.6-0.8 for observed, 0.9+ for explicitly stated"
            },
            "evidence": {
                "type": "string",
                "description": "Why you believe this (optional but recommended for high confidence)"
            }
        },
        "required": ["category", "key", "value"]
    }

    def __init__(
        self,
        context: ExecutionContext,
        container: Container,
        memory_service: IUserMemory = None,
    ):
        """
        Initialize the remember tool.

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
        Store a memory item.

        Args:
            params: Tool parameters (category, key, value, confidence, evidence).
            context: Execution context.

        Returns:
            ToolResult with storage confirmation.
        """
        category = params.get("category", "")
        key = params.get("key", "")
        value = params.get("value", "")
        confidence = params.get("confidence", 0.5)
        evidence = params.get("evidence", "")

        # Validate required fields
        if not category or not key or not value:
            return ToolResult(
                content=json.dumps({
                    "error": "category, key, and value are required",
                    "stored": False
                }),
                success=False,
                error="Missing required fields"
            )

        # Validate category
        if category not in VALID_CATEGORIES:
            return ToolResult(
                content=json.dumps({
                    "error": f"Invalid category '{category}'. Must be one of: {list(VALID_CATEGORIES)}",
                    "stored": False
                }),
                success=False,
                error=f"Invalid category: {category}"
            )

        # Validate confidence
        if not 0.0 <= confidence <= 1.0:
            return ToolResult(
                content=json.dumps({
                    "error": "Confidence must be between 0.0 and 1.0",
                    "stored": False
                }),
                success=False,
                error="Invalid confidence value"
            )

        # Get user_id from context
        user_id = context.user_profile.user_id if context.user_profile else "default"

        # Get agent name for tracking who learned this
        agent_name = context.agent_name or "unknown"

        memory_service = await self._get_memory_service()
        if not memory_service:
            return ToolResult(
                content=json.dumps({
                    "error": "Memory service not available",
                    "stored": False,
                    "hint": "User memory is not configured"
                }),
                success=False,
                error="Memory service not available"
            )

        try:
            # Store the memory
            await memory_service.put(
                user_id=user_id,
                category=category,
                key=key,
                value=value,
                confidence=confidence,
                source="learned",
                learned_by=agent_name,
            )

            # Check if this might be promoted to permanent storage
            promotion_hint = ""
            if confidence >= 0.9:
                promotion_hint = "High confidence memory may be promoted to permanent storage."
            elif confidence >= 0.7:
                promotion_hint = "Memory stored. Increase confidence with more evidence to promote."

            logger.info(
                f"Stored memory {category}/{key} for user {user_id} "
                f"(confidence: {confidence}, agent: {agent_name})"
            )

            return ToolResult(
                content=json.dumps({
                    "stored": True,
                    "category": category,
                    "key": key,
                    "confidence": confidence,
                    "message": f"Remembered: {value}",
                    "hint": promotion_hint,
                }),
                success=True,
            )

        except Exception as e:
            logger.error(f"Remember tool error: {e}")
            return ToolResult(
                content=json.dumps({
                    "error": str(e),
                    "stored": False
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


def create_remember_tool(
    context: ExecutionContext,
    container: Container,
) -> RememberTool:
    """
    Factory function to create remember tool.

    Args:
        context: Execution context.
        container: DI container for service resolution.

    Returns:
        Configured RememberTool instance.
    """
    memory_service = container.try_resolve(IUserMemory)

    return RememberTool(
        context=context,
        container=container,
        memory_service=memory_service,
    )
