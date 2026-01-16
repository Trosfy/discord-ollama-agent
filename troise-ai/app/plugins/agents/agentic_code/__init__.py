"""Agentic code agent plugin definition."""
from .agent import AgenticCodeAgent


def create_agentic_code_agent(vram_orchestrator, tools, prompt_composer, config=None):
    """
    Factory function for creating AgenticCodeAgent instances.

    Args:
        vram_orchestrator: IVRAMOrchestrator for model access.
        tools: List of Strands tool instances.
        prompt_composer: PromptComposer for building system prompts.
        config: Optional agent configuration.

    Returns:
        AgenticCodeAgent instance.
    """
    return AgenticCodeAgent(
        vram_orchestrator=vram_orchestrator,
        tools=tools,
        prompt_composer=prompt_composer,
        config=config,
    )


PLUGIN = {
    "type": "agent",
    "name": "agentic_code",
    "class": AgenticCodeAgent,
    "factory": create_agentic_code_agent,
    "description": "Writes, modifies, and tests code with file I/O capabilities",
    "category": "code",
    "tools": ["brain_search", "read_file", "write_file", "run_code"],  # + universal tools
    "config": {
        "model_role": "code",  # Use profile's code_model
        "timeout": 600,  # 10 minutes max for complex code tasks
    },
    "routing": {
        "keywords": ["code", "implement", "create function", "write script", "fix bug", "refactor"],
        "examples": [
            "Implement a REST API for user management",
            "Create a Python script to process CSV files",
            "Fix the bug in the authentication module",
            "Refactor the database queries for better performance",
            "Write unit tests for the payment service",
        ],
    },
}
