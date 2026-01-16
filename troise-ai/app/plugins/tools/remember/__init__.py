"""Remember tool plugin.

Allows agents to store learned information about the user.
"""
from .tool import RememberTool, create_remember_tool

PLUGIN = {
    "type": "tool",
    "name": "remember",
    "class": RememberTool,
    "factory": create_remember_tool,
    "category": "memory",
    "description": "Store learned information about the user",
}

__all__ = ["RememberTool", "create_remember_tool", "PLUGIN"]
