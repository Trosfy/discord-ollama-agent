"""Ask user tool implementation.

Allows agents to pause execution and request input from the user.
Uses the WebSocket connection for real-time communication.
"""
import logging
from typing import Any, Dict, List, Optional

from app.core.context import ExecutionContext
from app.core.container import Container
from app.core.interfaces.tool import ToolResult

logger = logging.getLogger(__name__)


class AskUserTool:
    """
    Tool that allows agents to ask users questions.

    Uses the WebSocket connection in context to send questions
    and wait for responses. Handles timeouts gracefully.
    """

    name = "ask_user"
    description = """Ask the user a question and wait for their response.
Use this when you need:
- Clarification on ambiguous requests
- User preferences or choices
- Confirmation before taking an action
- Additional information to complete a task

The user will see your question and can respond with free text or select from options if provided."""

    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to ask the user. Be clear and specific."
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of suggested responses. User can also provide free text."
            },
            "timeout": {
                "type": "integer",
                "description": "How long to wait for response in seconds (default: 300)",
                "default": 300
            }
        },
        "required": ["question"]
    }

    def __init__(self, context: ExecutionContext, container: Container):
        """
        Initialize the ask user tool.

        Args:
            context: Execution context with WebSocket connection.
            container: DI container (unused but required by factory pattern).
        """
        self._context = context
        self._container = container

    async def execute(
        self,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Ask the user a question and wait for response.

        Args:
            params: Tool parameters (question, options, timeout).
            context: Execution context.

        Returns:
            ToolResult with user's response.
        """
        question = params.get("question", "")
        options = params.get("options")
        timeout = params.get("timeout", 300)

        if not question:
            return ToolResult(
                content="",
                success=False,
                error="Question is required"
            )

        try:
            # Request input from user via context
            response = await context.request_user_input(
                question=question,
                options=options,
                timeout=timeout,
            )

            logger.info(f"User responded to question: {question[:50]}...")

            return ToolResult(
                content=response,
                success=True,
            )

        except TimeoutError:
            logger.warning(f"Timeout waiting for user response to: {question[:50]}...")
            return ToolResult(
                content="",
                success=False,
                error=f"User did not respond within {timeout} seconds"
            )

        except Exception as e:
            logger.error(f"Error asking user: {e}")
            return ToolResult(
                content="",
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


def create_ask_user_tool(
    context: ExecutionContext,
    container: Container,
) -> AskUserTool:
    """
    Factory function to create ask_user tool.

    Args:
        context: Execution context with WebSocket connection.
        container: DI container.

    Returns:
        Configured AskUserTool instance.
    """
    return AskUserTool(context=context, container=container)
