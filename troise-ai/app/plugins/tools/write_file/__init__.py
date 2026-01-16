"""Write file tool plugin."""
from .tool import WriteFileTool, create_write_file_tool

PLUGIN = {
    "type": "tool",
    "name": "write_file",
    "class": WriteFileTool,
    "factory": create_write_file_tool,
    "description": "Write content to a file on the filesystem"
}

__all__ = ["WriteFileTool", "create_write_file_tool", "PLUGIN"]
