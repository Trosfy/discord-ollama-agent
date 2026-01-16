"""WebSocket message building interfaces."""
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol

if TYPE_CHECKING:
    from ..context import ExecutionContext


class IWebSocketMessageBuilder(Protocol):
    """Protocol for building interface-aware WebSocket messages.

    Implementations add interface-specific metadata (Discord channel_id,
    Web session tokens, etc.) to base messages.

    This follows the Interface Segregation Principle - each builder
    only adds metadata relevant to its interface.
    """

    @property
    def interface_name(self) -> str:
        """Interface this builder handles (discord, web, cli, api)."""
        ...

    def build_message(
        self,
        base_message: Dict[str, Any],
        context: "ExecutionContext",
    ) -> Dict[str, Any]:
        """Build message with interface-specific metadata.

        Args:
            base_message: Core message fields (type, content, etc.)
            context: Execution context with interface metadata.

        Returns:
            Complete message with interface-appropriate fields added.
        """
        ...

    def build_stream_chunk(
        self,
        content: str,
        context: "ExecutionContext",
    ) -> Dict[str, Any]:
        """Build streaming chunk message.

        Args:
            content: Text content for this chunk.
            context: Execution context.

        Returns:
            Stream message with interface metadata.
        """
        ...

    def build_stream_end(
        self,
        context: "ExecutionContext",
    ) -> Dict[str, Any]:
        """Build stream completion message.

        Args:
            context: Execution context.

        Returns:
            Stream end message with interface metadata.
        """
        ...

    def build_question(
        self,
        question: str,
        options: Optional[List[str]],
        request_id: str,
        context: "ExecutionContext",
    ) -> Dict[str, Any]:
        """Build agent question message.

        Args:
            question: The question to ask the user.
            options: Optional list of suggested answers.
            request_id: Unique request ID for tracking response.
            context: Execution context.

        Returns:
            Question message with interface metadata.
        """
        ...
