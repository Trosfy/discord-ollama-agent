"""Insight Extractor agent plugin definition."""
from .agent import InsightExtractorAgent


PLUGIN = {
    "type": "agent",
    "name": "insight_extractor",
    "class": InsightExtractorAgent,
    "description": "Extracts actionable insights from connected thoughts",
    "category": "braindump",
    "tools": ["brain_search"],
    "config": {
        "temperature": 0.3,
        "max_tokens": 4096,
        "model_role": "braindump",
        "skip_universal_tools": True,  # Only needs brain_search for vault
    },
}
