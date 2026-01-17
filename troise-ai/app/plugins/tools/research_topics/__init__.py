"""Research Topics Tool - Parallel sub-agent execution."""
from .tool import ResearchTopicsTool, create_research_topics_tool

PLUGIN = {
    "type": "tool",
    "name": "research_topics",
    "class": ResearchTopicsTool,
    "factory": create_research_topics_tool,
    "description": "Research multiple topics in parallel using sub-agents"
}

__all__ = ["ResearchTopicsTool", "create_research_topics_tool", "PLUGIN"]
