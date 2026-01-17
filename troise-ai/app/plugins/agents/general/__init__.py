"""General agent plugin definition."""
from .agent import GeneralAgent


def create_general_agent(vram_orchestrator, tools, config=None):
    """
    Factory function for creating GeneralAgent instances.

    Args:
        vram_orchestrator: IVRAMOrchestrator for model access.
        tools: List of Strands tool instances.
        config: Optional agent configuration.

    Returns:
        GeneralAgent instance.
    """
    return GeneralAgent(
        vram_orchestrator=vram_orchestrator,
        tools=tools,
        config=config,
    )


PLUGIN = {
    "type": "agent",
    "name": "general",
    "class": GeneralAgent,
    "factory": create_general_agent,
    "description": "General-purpose assistant with access to specialized skills on demand",
    "category": "general",
    "tools": ["run_code", "skill_gateway"],  # + universal tools (remember, recall, web_search, web_fetch)
    "config": {
        "model_role": "general",
        "timeout": 120,
    },
    "routing": {
        "keywords": ["help", "explain", "what", "how", "tell me"],
        "examples": [
            "What is Python?",
            "Explain recursion to me",
            "How do I create an email?",
        ],
    },
}
