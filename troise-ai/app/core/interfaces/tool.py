"""ITool interface - callable tools for agents."""
from typing import Protocol, Dict, Any, TYPE_CHECKING, runtime_checkable
from dataclasses import dataclass

if TYPE_CHECKING:
    from ..context import ExecutionContext


@runtime_checkable
class ICloseable(Protocol):
    """
    Protocol for resources that need cleanup.

    Tools with network sessions, file handles, or other resources
    should implement this protocol for proper cleanup after execution.
    """

    async def close(self) -> None:
        """Release resources."""
        ...


@dataclass
class ToolResult:
    """Result from tool execution."""
    content: str
    success: bool = True
    error: str = None


class ITool(Protocol):
    """
    Tool that agents can call during execution.

    Tools are:
    - Focused (single responsibility)
    - JSON-serializable results
    - Error-tolerant (return errors as JSON, don't raise)
    """
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema

    async def execute(
        self,
        params: Dict[str, Any],
        context: "ExecutionContext"
    ) -> ToolResult:
        """
        Execute the tool with given parameters.

        Args:
            params: Tool parameters matching the JSON schema
            context: Execution context

        Returns:
            ToolResult with content and success status
        """
        ...

    def to_schema(self) -> Dict[str, Any]:
        """
        Return tool schema for LLM function calling.

        Returns:
            Dict with name, description, and parameters schema
        """
        ...
