"""Web Fetch Tool - Fetches and extracts content from URLs."""

from .tool import WebFetchTool, create_web_fetch_tool

PLUGIN = {
    "name": "web_fetch",
    "type": "tool",
    "description": "Fetch and extract readable content from web pages",
    "factory": create_web_fetch_tool,
}

__all__ = ["WebFetchTool", "create_web_fetch_tool", "PLUGIN"]
