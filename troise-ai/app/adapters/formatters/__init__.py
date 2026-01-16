"""Response formatters for different interfaces.

Provides interface-specific formatting:
- DiscordResponseFormatter: Message splitting at 2000 chars
- WebResponseFormatter: Passthrough (no length limits)
- CLIResponseFormatter: Terminal-friendly formatting
"""
from .interface import IResponseFormatter, FormattedResponse
from .discord import DiscordResponseFormatter
from .web import WebResponseFormatter
from .cli import CLIResponseFormatter

__all__ = [
    "IResponseFormatter",
    "FormattedResponse",
    "DiscordResponseFormatter",
    "WebResponseFormatter",
    "CLIResponseFormatter",
]
