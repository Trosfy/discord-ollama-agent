"""Prompt system for TROISE AI.

This module provides a modular, profile-aware prompt system with:
- PromptRegistry: Singleton file loader with profile fallback
- PromptComposer: 4-layer prompt composition

Directory structure:
    prompts/
    ├── agents/              # Agent system prompts (balanced = default)
    │   └── variants/        # Profile-specific variants
    │       ├── conservative/
    │       └── performance/
    ├── layers/              # Reusable prompt layers
    │   └── variants/
    └── ...

Usage:
    from app.prompts import prompt_registry, PromptComposer

    # Load prompt directly
    prompt = prompt_registry.get_prompt("agents", "braindump", profile="performance")

    # Compose agent prompt with all layers
    composer = PromptComposer(prompt_registry, config)
    system_prompt = composer.compose_agent_prompt(
        agent_name="braindump",
        interface="discord",
        profile="performance",
        user_profile=user_profile,
    )
"""
from .registry import PromptRegistry, prompt_registry
from .composer import PromptComposer, create_prompt_composer

__all__ = [
    "PromptRegistry",
    "prompt_registry",
    "PromptComposer",
    "create_prompt_composer",
]
