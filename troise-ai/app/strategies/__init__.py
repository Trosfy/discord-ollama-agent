"""Output strategies for interface-specific handling."""
from .discord_strategy import DiscordOutputStrategy
from .terminal_strategy import TerminalOutputStrategy

__all__ = [
    "DiscordOutputStrategy",
    "TerminalOutputStrategy",
]
