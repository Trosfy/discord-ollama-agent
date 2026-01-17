"""Thought Organizer agent plugin definition."""
from .agent import ThoughtOrganizerAgent


PLUGIN = {
    "type": "agent",
    "name": "thought_organizer",
    "class": ThoughtOrganizerAgent,
    "description": "Structures raw thoughts into categories and themes",
    "category": "braindump",
    "tools": ["brain_search"],
    "config": {
        "temperature": 0.3,
        "max_tokens": 4096,
        "model_role": "braindump",
        "skip_universal_tools": True,  # Only needs brain_search for vault
    },
}
