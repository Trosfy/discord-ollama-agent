"""Base WebSocket message builder with common functionality."""
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from app.core.context import ExecutionContext


class BaseMessageBuilder:
    """Base message builder with interface-agnostic fields.

    Provides common message building functionality that all
    interface-specific builders inherit from.

    Implements:
    - Adding interface identifier to all messages
    - Adding request_id for tracking
    - Common message type builders (stream, question, etc.)
    """

    @property
    def interface_name(self) -> str:
        """Interface this builder handles."""
        return "base"

    def _add_common_fields(
        self,
        msg: Dict[str, Any],
        context: "ExecutionContext",
    ) -> Dict[str, Any]:
        """Add fields common to all interfaces.

        Args:
            msg: Message dict to augment.
            context: Execution context with metadata.

        Returns:
            Message with common fields added.
        """
        msg["interface"] = context.interface
        if context.request_id:
            msg["request_id"] = context.request_id
        return msg

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
            Complete message with common fields added.
        """
        return self._add_common_fields({**base_message}, context)

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
        return self.build_message({"type": "stream", "content": content}, context)

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
        return self.build_message({"type": "stream_end"}, context)

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
        return self.build_message(
            {
                "type": "question",
                "request_id": request_id,
                "question": question,
                "options": options,
            },
            context,
        )

    def build_execute_command(
        self,
        command: str,
        request_id: str,
        context: "ExecutionContext",
        working_dir: Optional[str] = None,
        requires_approval: bool = False,
    ) -> Dict[str, Any]:
        """Build command execution request message.

        Base implementation for interfaces that support command execution.
        CLI builder may override for enhanced functionality.

        Args:
            command: Shell command to execute.
            request_id: Unique ID for tracking response.
            context: Execution context.
            working_dir: Working directory for execution.
            requires_approval: Whether user must approve first.

        Returns:
            Command execution request message.
        """
        return self.build_message(
            {
                "type": "execute_command",
                "request_id": request_id,
                "command": command,
                "working_dir": working_dir,
                "requires_approval": requires_approval,
            },
            context,
        )

    def build_completion_metrics(
        self,
        metadata: Dict[str, Any],
        context: "ExecutionContext",
    ) -> Optional[Dict[str, Any]]:
        """Build completion metrics message for interfaces that display them.

        Override in subclasses to provide interface-specific metrics.
        Returns None by default (most interfaces don't display metrics).

        Args:
            metadata: Execution result metadata with token counts, timing, etc.
            context: Execution context.

        Returns:
            Metrics message or None to skip.
        """
        return None
