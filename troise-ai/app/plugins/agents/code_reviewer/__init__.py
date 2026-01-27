"""Code Reviewer agent plugin definition."""
from .agent import CodeReviewerAgent


PLUGIN = {
    "type": "agent",
    "name": "code_reviewer",
    "class": CodeReviewerAgent,
    "description": "Reviews code for bugs, security issues, and style violations",
    "category": "code",
    "tools": ["brain_search"],  # Reviews code passed in context - no filesystem access
    "config": {
        "temperature": 0.1,  # Deterministic review
        "max_tokens": 4096,
        "model_role": "code",
        "skip_universal_tools": True,  # Reviews existing code, doesn't need web
    },
}
