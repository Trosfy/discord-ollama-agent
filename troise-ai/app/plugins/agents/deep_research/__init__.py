"""Deep research agent plugin definition."""
from .agent import DeepResearchAgent


def create_deep_research_agent(vram_orchestrator, tools, prompt_composer, config=None):
    """
    Factory function for creating DeepResearchAgent instances.

    Args:
        vram_orchestrator: IVRAMOrchestrator for model access.
        tools: List of Strands tool instances.
        prompt_composer: PromptComposer for building system prompts.
        config: Optional agent configuration.

    Returns:
        DeepResearchAgent instance.
    """
    return DeepResearchAgent(
        vram_orchestrator=vram_orchestrator,
        tools=tools,
        prompt_composer=prompt_composer,
        config=config,
    )


PLUGIN = {
    "type": "agent",
    "name": "deep_research",
    "class": DeepResearchAgent,
    "factory": create_deep_research_agent,
    "description": "Conducts comprehensive multi-source research and creates reports",
    "category": "research",
    "tools": ["brain_search"],  # + universal tools (remember, recall, web_search, web_fetch)
    "config": {
        # Model determined by profile's research_model via model_role
        "timeout": 600,  # 10 minutes max for deep research
    },
    "routing": {
        "keywords": ["research", "investigate", "deep dive", "explore", "study"],
        "examples": [
            "Research the latest trends in AI",
            "Do a deep dive on quantum computing",
            "Investigate options for database migration",
            "Research best practices for microservices",
        ],
    },
}
