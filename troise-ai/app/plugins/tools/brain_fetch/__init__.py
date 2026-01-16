"""Brain fetch tool - fetch full note content."""
from .tool import create_brain_fetch_tool

PLUGIN = {
    "type": "tool",
    "name": "brain_fetch",
    "factory": create_brain_fetch_tool,
    "description": "Fetch the full content of a note from the knowledge base",
}
