"""Citation Formatter agent plugin definition."""
from .agent import CitationFormatterAgent


PLUGIN = {
    "type": "agent",
    "name": "citation_formatter",
    "class": CitationFormatterAgent,
    "description": "Formats references and citations in research outputs",
    "category": "research",
    "tools": ["brain_search"],
    "config": {
        "temperature": 0.1,
        "max_tokens": 8192,
        "model_role": "general",
        "skip_universal_tools": True,  # Only uses brain_search - no redundant web searches
    },
}
