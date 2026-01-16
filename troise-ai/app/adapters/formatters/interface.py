"""Response formatter interface."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class FormattedResponse:
    """Formatted response for sending."""
    messages: List[str]  # Split messages for the interface
    metadata: Dict[str, Any] = field(default_factory=dict)


class IResponseFormatter(Protocol):
    """Interface for response formatters.

    Each formatter handles interface-specific formatting:
    - Discord: Split at 2000 chars, preserve code blocks
    - Web: No splitting needed
    - CLI: Compact formatting
    """

    @property
    def interface_name(self) -> str:
        """Name of the interface this formatter handles."""
        ...

    def format(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FormattedResponse:
        """Format content for the interface.

        Args:
            content: Content to format.
            metadata: Optional metadata about the content.

        Returns:
            FormattedResponse with possibly split messages.
        """
        ...
