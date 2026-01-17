"""Debugger agent plugin definition."""
from .agent import DebuggerAgent


PLUGIN = {
    "type": "agent",
    "name": "debugger",
    "class": DebuggerAgent,
    "description": "Fixes code issues identified by review or test failures",
    "category": "code",
    "tools": ["brain_search", "read_file", "run_code"],
    "config": {
        "temperature": 0.2,
        "max_tokens": 4096,
        "model_role": "code",
        "skip_universal_tools": True,  # Fixes code issues, doesn't need web
    },
}
