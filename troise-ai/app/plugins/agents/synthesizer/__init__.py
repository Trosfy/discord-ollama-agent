"""Synthesizer agent plugin definition."""
from .agent import SynthesizerAgent


PLUGIN = {
    "type": "agent",
    "name": "synthesizer",
    "class": SynthesizerAgent,
    "description": "Combines multi-source research into coherent analysis",
    "category": "research",
    "tools": [],
    "config": {
        "temperature": 0.3,
        "max_tokens": 8192,
        "model_role": "research",
        "skip_universal_tools": True,  # deep_research already did web searches
    },
}
