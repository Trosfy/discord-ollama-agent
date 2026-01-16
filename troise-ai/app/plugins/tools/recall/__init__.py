"""Recall tool plugin.

Allows agents to retrieve learned information about the user.
"""
from .tool import RecallTool, create_recall_tool

PLUGIN = {
    "type": "tool",
    "name": "recall",
    "class": RecallTool,
    "factory": create_recall_tool,
    "category": "memory",
    "description": "Retrieve learned information about the user",
}

__all__ = ["RecallTool", "create_recall_tool", "PLUGIN"]
