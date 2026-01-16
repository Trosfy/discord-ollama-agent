"""Discord-specific WebSocket message builder."""
from typing import TYPE_CHECKING, Any, Dict

from .base_builder import BaseMessageBuilder

if TYPE_CHECKING:
    from app.core.context import ExecutionContext


class DiscordMessageBuilder(BaseMessageBuilder):
    """Message builder that adds Discord-specific metadata.

    Adds channel_id, message_channel_id, message_id for Discord
    streaming state tracking and reaction updates.

    Discord-specific fields:
    - channel_id: Thread ID where responses are sent
    - message_channel_id: Original channel for reaction updates
    - message_id: Original message ID for reaction targeting
    """

    @property
    def interface_name(self) -> str:
        """Interface this builder handles."""
        return "discord"

    def _add_discord_fields(
        self,
        msg: Dict[str, Any],
        context: "ExecutionContext",
    ) -> Dict[str, Any]:
        """Add Discord-specific metadata.

        Args:
            msg: Message dict to augment.
            context: Execution context with Discord metadata.

        Returns:
            Message with Discord fields added.
        """
        if context.discord_channel_id:
            msg["channel_id"] = context.discord_channel_id
        if context.discord_message_channel_id:
            msg["message_channel_id"] = context.discord_message_channel_id
        if context.discord_message_id:
            msg["message_id"] = context.discord_message_id
        return msg

    def build_message(
        self,
        base_message: Dict[str, Any],
        context: "ExecutionContext",
    ) -> Dict[str, Any]:
        """Build message with Discord-specific metadata.

        Args:
            base_message: Core message fields (type, content, etc.)
            context: Execution context with Discord metadata.

        Returns:
            Complete message with Discord fields added.
        """
        msg = super().build_message(base_message, context)
        return self._add_discord_fields(msg, context)
