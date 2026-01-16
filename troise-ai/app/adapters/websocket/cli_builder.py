"""CLI/TUI WebSocket message builder.

Handles CLI/TUI-specific message construction:
- Command execution requests
- Progress updates
- Tool call notifications
"""
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .base_builder import BaseMessageBuilder

if TYPE_CHECKING:
    from app.core.context import ExecutionContext


class CLIMessageBuilder(BaseMessageBuilder):
    """Message builder for CLI/TUI interface.

    Extends base builder with CLI-specific message types:
    - execute_command: Request command execution on user's machine
    - tool_call: Notify about tool being called
    - progress: Progress updates for long-running operations
    """

    @property
    def interface_name(self) -> str:
        return "cli"

    def build_execute_command(
        self,
        command: str,
        request_id: str,
        context: "ExecutionContext",
        working_dir: Optional[str] = None,
        requires_approval: bool = False,
    ) -> Dict[str, Any]:
        """Build command execution request message.

        Sent to TUI to request shell command execution.
        TUI will:
        1. Show approval dialog if requires_approval=True
        2. Execute command in user's environment
        3. Send back result via command_result message

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

    def build_tool_call(
        self,
        tool_name: str,
        status: str,
        context: "ExecutionContext",
        result: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build tool call notification message.

        Informs TUI about tool execution status.

        Args:
            tool_name: Name of the tool being called.
            status: Status (calling, completed, error).
            context: Execution context.
            result: Optional result summary.

        Returns:
            Tool call notification message.
        """
        msg = {
            "type": "tool_call",
            "tool_name": tool_name,
            "status": status,
        }
        if result:
            msg["result"] = result[:500]  # Truncate long results
        return self.build_message(msg, context)

    def build_progress(
        self,
        message: str,
        context: "ExecutionContext",
        progress: Optional[float] = None,
        step: Optional[int] = None,
        total_steps: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build progress update message.

        For long-running operations that want to show progress.

        Args:
            message: Progress message.
            context: Execution context.
            progress: Progress percentage (0.0-1.0).
            step: Current step number.
            total_steps: Total number of steps.

        Returns:
            Progress update message.
        """
        msg = {
            "type": "progress",
            "message": message,
        }
        if progress is not None:
            msg["progress"] = progress
        if step is not None:
            msg["step"] = step
        if total_steps is not None:
            msg["total_steps"] = total_steps
        return self.build_message(msg, context)

    def build_thinking(
        self,
        thinking: str,
        context: "ExecutionContext",
    ) -> Dict[str, Any]:
        """Build thinking content message.

        Shows agent's reasoning/thinking process.

        Args:
            thinking: Thinking content.
            context: Execution context.

        Returns:
            Thinking message.
        """
        return self.build_message(
            {
                "type": "thinking",
                "content": thinking,
            },
            context,
        )
