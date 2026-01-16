"""CLI response formatter.

Handles:
- Terminal-friendly formatting
- ANSI color code support (optional)
- Compact output for terminal display
"""
from typing import Any, Dict, List, Optional

from .interface import IResponseFormatter, FormattedResponse


class CLIResponseFormatter:
    """Format responses for CLI/TUI interface.

    Features:
    - No message splitting (terminals handle long text)
    - Optional syntax highlighting markers
    - Compact metadata formatting
    - Progress indicator support

    Example:
        formatter = CLIResponseFormatter()
        formatted = formatter.format(content)
    """

    @property
    def interface_name(self) -> str:
        return "cli"

    def format(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FormattedResponse:
        """Format content for CLI display.

        Args:
            content: Content to format.
            metadata: Optional metadata (source, model, etc.).

        Returns:
            FormattedResponse with single message (no splitting needed).
        """
        formatted_content = content

        # Add source attribution if present
        if metadata and metadata.get("source"):
            source = metadata["source"]
            formatted_content = f"[{source}]\n{formatted_content}"

        return FormattedResponse(
            messages=[formatted_content],
            metadata=metadata or {},
        )

    def format_tool_call(
        self,
        tool_name: str,
        status: str,
        result: Optional[str] = None
    ) -> str:
        """Format a tool call for CLI display.

        Args:
            tool_name: Name of the tool being called.
            status: Status (running, completed, error).
            result: Optional result to display.

        Returns:
            Formatted tool call string.
        """
        status_icons = {
            "running": "⚡",
            "completed": "✓",
            "error": "✗",
        }
        icon = status_icons.get(status, "•")

        if status == "running":
            return f"{icon} {tool_name}..."
        elif result:
            return f"{icon} {tool_name}: {result[:200]}"
        else:
            return f"{icon} {tool_name}"

    def format_progress(
        self,
        message: str,
        progress: Optional[float] = None
    ) -> str:
        """Format a progress message for CLI display.

        Args:
            message: Progress message.
            progress: Optional progress percentage (0-1).

        Returns:
            Formatted progress string.
        """
        if progress is not None:
            pct = int(progress * 100)
            bar_width = 20
            filled = int(bar_width * progress)
            bar = "█" * filled + "░" * (bar_width - filled)
            return f"[{bar}] {pct}% {message}"
        else:
            return f"⏳ {message}"

    def format_error(self, error: str) -> str:
        """Format an error message for CLI display.

        Args:
            error: Error message.

        Returns:
            Formatted error string.
        """
        return f"❌ Error: {error}"

    def format_warning(self, warning: str) -> str:
        """Format a warning message for CLI display.

        Args:
            warning: Warning message.

        Returns:
            Formatted warning string.
        """
        return f"⚠️ Warning: {warning}"

    def format_success(self, message: str) -> str:
        """Format a success message for CLI display.

        Args:
            message: Success message.

        Returns:
            Formatted success string.
        """
        return f"✅ {message}"
