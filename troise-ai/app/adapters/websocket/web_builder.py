"""Web interface WebSocket message builder."""
from .base_builder import BaseMessageBuilder


class WebMessageBuilder(BaseMessageBuilder):
    """Message builder for web interface.

    Currently passthrough - web interface doesn't need
    special metadata beyond base fields.

    Future extensions could add:
    - browser_session_id: For session tracking
    - client_capabilities: For feature detection
    - viewport_size: For responsive formatting
    """

    @property
    def interface_name(self) -> str:
        """Interface this builder handles."""
        return "web"
