"""Run code tool plugin."""
from .tool import RunCodeTool, create_run_code_tool

PLUGIN = {
    "type": "tool",
    "name": "run_code",
    "class": RunCodeTool,
    "factory": create_run_code_tool,
    "description": "Execute code in a sandboxed environment"
}

__all__ = ["RunCodeTool", "create_run_code_tool", "PLUGIN"]
