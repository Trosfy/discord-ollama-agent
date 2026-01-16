"""Brain search tool - search knowledge base."""
from .tool import create_brain_search_tool

PLUGIN = {
    "type": "tool",
    "name": "brain_search",
    "factory": create_brain_search_tool,
    "description": "Search the user's knowledge base (Obsidian notes) for relevant information",
}
