"""Factory for creating interface-appropriate message builders."""
from typing import TYPE_CHECKING, Dict, Type

from .base_builder import BaseMessageBuilder
from .discord_builder import DiscordMessageBuilder
from .web_builder import WebMessageBuilder
from .cli_builder import CLIMessageBuilder

if TYPE_CHECKING:
    from app.core.context import ExecutionContext
    from app.core.interfaces.websocket import IWebSocketMessageBuilder


# Registry of interface -> builder class
_BUILDERS: Dict[str, Type[BaseMessageBuilder]] = {
    "discord": DiscordMessageBuilder,
    "web": WebMessageBuilder,
    "cli": CLIMessageBuilder,
    "api": BaseMessageBuilder,  # Future: APIMessageBuilder
}


def get_message_builder(context: "ExecutionContext") -> "IWebSocketMessageBuilder":
    """Get appropriate message builder for the context's interface.

    This factory function creates the correct builder based on the
    interface type in the execution context.

    Args:
        context: Execution context with interface type.

    Returns:
        Message builder for the interface.

    Example:
        >>> builder = get_message_builder(context)
        >>> msg = builder.build_stream_chunk("Hello", context)
        >>> await websocket.send_json(msg)
    """
    builder_class = _BUILDERS.get(context.interface, BaseMessageBuilder)
    return builder_class()


def create_message_builder_factory():
    """Create factory function for DI container registration.

    Returns a factory function that caches builders by interface
    (they're stateless singletons).

    Returns:
        Factory function: interface -> IWebSocketMessageBuilder

    Example:
        >>> factory = create_message_builder_factory()
        >>> container.register("message_builder_factory", factory)
        >>> builder = factory("discord")
    """
    _cache: Dict[str, "IWebSocketMessageBuilder"] = {}

    def factory(interface: str) -> "IWebSocketMessageBuilder":
        if interface not in _cache:
            builder_class = _BUILDERS.get(interface, BaseMessageBuilder)
            _cache[interface] = builder_class()
        return _cache[interface]

    return factory
