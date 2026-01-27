"""Image Generator Agent plugin definition.

Generates images using FLUX 2.dev via the generate_image tool.
The agent interprets requests and crafts effective prompts for FLUX.
"""
from .agent import ImageGeneratorAgent


def create_image_generator_agent(vram_orchestrator, tools, prompt_composer, config=None):
    """
    Factory function for creating ImageGeneratorAgent instances.

    Args:
        vram_orchestrator: IVRAMOrchestrator for model access.
        tools: List of Strands tool instances.
        prompt_composer: PromptComposer for prompt building.
        config: Optional agent configuration.

    Returns:
        ImageGeneratorAgent instance.
    """
    return ImageGeneratorAgent(
        vram_orchestrator=vram_orchestrator,
        tools=tools,
        prompt_composer=prompt_composer,
        config=config,
    )


PLUGIN = {
    "type": "agent",
    "name": "image_generator",
    "class": ImageGeneratorAgent,
    "factory": create_image_generator_agent,
    "description": "Generates images using FLUX 2.dev",
    "category": "image",
    "tools": ["generate_image"],
    "config": {
        "model_role": "image_handler",  # Uses profile.image_handler_model (LLM for prompt crafting)
        "temperature": 0.7,  # Creative for prompt crafting
        "max_tokens": 2048,
        "skip_universal_tools": True,  # Don't add web_search, remember, etc.
    },
    "routing": {
        # IMAGE domain is routed via router classification, not keywords
        "keywords": [],
        "examples": [],
    },
}
