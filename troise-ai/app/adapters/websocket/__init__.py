"""WebSocket message adapters.

This package provides interface-specific message builders that
construct WebSocket messages with appropriate metadata for each
interface (Discord, Web, CLI, API).

Usage:
    from app.adapters.websocket.factory import get_message_builder

    builder = get_message_builder(context)
    msg = builder.build_stream_chunk("Hello", context)
    await websocket.send_json(msg)
"""
from .base_builder import BaseMessageBuilder
from .discord_builder import DiscordMessageBuilder
from .factory import create_message_builder_factory, get_message_builder
from .web_builder import WebMessageBuilder

__all__ = [
    "BaseMessageBuilder",
    "DiscordMessageBuilder",
    "WebMessageBuilder",
    "get_message_builder",
    "create_message_builder_factory",
]
