"""Note Formatter agent plugin definition."""
from .agent import NoteFormatterAgent


PLUGIN = {
    "type": "agent",
    "name": "note_formatter",
    "class": NoteFormatterAgent,
    "description": "Formats organized thoughts for Obsidian vault storage",
    "category": "braindump",
    "tools": ["brain_search", "save_note"],
    "config": {
        "temperature": 0.1,
        "max_tokens": 4096,
        "model_role": "braindump",
        "skip_universal_tools": True,  # Only needs brain_search/save_note for vault
    },
}
