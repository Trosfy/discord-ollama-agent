"""Read file tool plugin."""
from .tool import ReadFileTool, create_read_file_tool

PLUGIN = {
    "type": "tool",
    "name": "read_file",
    "class": ReadFileTool,
    "factory": create_read_file_tool,
    "description": "Read contents of a file from the filesystem"
}

__all__ = ["ReadFileTool", "create_read_file_tool", "PLUGIN"]
