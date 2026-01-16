"""Web search tool plugin."""
from .tool import WebSearchTool, create_web_search_tool

PLUGIN = {
    "type": "tool",
    "name": "web_search",
    "class": WebSearchTool,
    "factory": create_web_search_tool,
    "description": "Search the web for information using DuckDuckGo"
}

__all__ = ["WebSearchTool", "create_web_search_tool", "PLUGIN"]
