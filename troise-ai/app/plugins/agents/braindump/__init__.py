"""Braindump agent plugin definition."""
from .agent import BraindumpAgent


def create_braindump_agent(vram_orchestrator, tools, config=None):
    """
    Factory function for creating BraindumpAgent instances.

    Args:
        vram_orchestrator: IVRAMOrchestrator for model access.
        tools: List of Strands tool instances.
        config: Optional agent configuration.

    Returns:
        BraindumpAgent instance.
    """
    return BraindumpAgent(
        vram_orchestrator=vram_orchestrator,
        tools=tools,
        config=config,
    )


PLUGIN = {
    "type": "agent",
    "name": "braindump",
    "class": BraindumpAgent,
    "factory": create_braindump_agent,
    "description": "Organizes unstructured thoughts into well-structured notes",
    "category": "productivity",
    "tools": ["brain_search", "brain_fetch"],  # + universal tools (remember, recall, web_search, web_fetch)
    "config": {
        # Model determined by profile's braindump_model via model_role
        "timeout": 300,  # 5 minutes max
    },
    "routing": {
        "keywords": ["braindump", "thoughts", "dump", "notes", "organize thoughts"],
        "examples": [
            "I need to dump some thoughts about the project",
            "Help me organize my random notes",
            "Let me braindump about the meeting",
        ],
    },
}
