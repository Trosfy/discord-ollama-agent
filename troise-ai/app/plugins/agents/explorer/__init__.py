"""Explorer agent plugin definition.

Generic exploration agent used as the first node in graphs to gather
context before specialized agents act. Behavior varies by prompt variant
based on graph domain (code, research, braindump).
"""
from .agent import ExplorerAgent


def create_explorer_agent(vram_orchestrator, tools, prompt_composer, config=None):
    """
    Factory function for creating ExplorerAgent instances.

    Args:
        vram_orchestrator: IVRAMOrchestrator for model access.
        tools: List of Strands tool instances.
        prompt_composer: PromptComposer for prompt building.
        config: Optional agent configuration.

    Returns:
        ExplorerAgent instance.
    """
    return ExplorerAgent(
        vram_orchestrator=vram_orchestrator,
        tools=tools,
        prompt_composer=prompt_composer,
        config=config,
    )


PLUGIN = {
    "type": "agent",
    "name": "explorer",
    "class": ExplorerAgent,
    "factory": create_explorer_agent,
    "description": "Context gathering agent that explores codebase, knowledge, or web before action",
    "category": "shared",
    # Union of all exploration tools - prompt variants guide which to use
    "tools": ["read_file", "brain_search", "brain_fetch", "web_search", "web_fetch"],
    "config": {
        "temperature": 0.2,  # Factual exploration
        "max_tokens": 4096,
        "model_role": "general",  # Use profile's general_model
    },
    "routing": {
        # Explorer is not directly routed - it's used as graph entry node
        "keywords": [],
        "examples": [],
    },
}
