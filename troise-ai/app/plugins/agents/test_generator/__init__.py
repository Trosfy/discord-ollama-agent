"""Test Generator agent plugin definition."""
from .agent import TestGeneratorAgent


PLUGIN = {
    "type": "agent",
    "name": "test_generator",
    "class": TestGeneratorAgent,
    "description": "Creates unit and integration tests for generated code",
    "category": "code",
    "tools": ["brain_search", "read_file"],
    "config": {
        "temperature": 0.2,
        "max_tokens": 4096,
        "model_role": "code",
        "skip_universal_tools": True,  # Generates tests from code, doesn't need web
    },
}
