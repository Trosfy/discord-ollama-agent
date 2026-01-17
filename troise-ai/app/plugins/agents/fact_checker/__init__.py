"""Fact Checker agent plugin definition."""
from .agent import FactCheckerAgent


PLUGIN = {
    "type": "agent",
    "name": "fact_checker",
    "class": FactCheckerAgent,
    "description": "Validates research claims against authoritative sources",
    "category": "research",
    "tools": ["web_search", "web_fetch"],
    "config": {
        "temperature": 0.1,
        "max_tokens": 4096,
        "model_role": "research",
    },
}
