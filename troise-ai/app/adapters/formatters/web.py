"""Web interface response formatter.

Passthrough formatter - web interfaces typically have no length limits.
"""
from typing import Any, Dict, Optional

from .interface import IResponseFormatter, FormattedResponse


class WebResponseFormatter:
    """Format responses for Web interface.

    Passthrough formatter - no length limits on web.

    Example:
        formatter = WebResponseFormatter()

        formatted = formatter.format(content)
        # formatted.messages = [content] (single message)
    """

    @property
    def interface_name(self) -> str:
        return "web"

    def format(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FormattedResponse:
        """Format content for Web (passthrough).

        Args:
            content: Content to format.
            metadata: Optional metadata.

        Returns:
            FormattedResponse with single message.
        """
        return FormattedResponse(messages=[content])
