"""Custom tools for Discord-Trollama Agent."""
from app.tools.web_tools import web_search, fetch_webpage
from app.tools.file_tools import list_attachments, get_file_content
from app.tools.strands_tools_wrapped import file_read_wrapped, file_write_wrapped

__all__ = [
    "web_search",
    "fetch_webpage",
    "list_attachments",
    "get_file_content",
    "file_read_wrapped",
    "file_write_wrapped",
]

# DEPRECATED: Replaced by new architecture
# - get_file_content → list_attachments (pre-extracted content from preprocessing)
# - create_artifact → file_write_wrapped (Strands file_write + DiscordFileExtension)
