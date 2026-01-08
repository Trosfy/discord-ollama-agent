"""Simplified prompt management system using human-readable .prompt files.

This module provides a simple prompt management system:
- PromptRegistry: Singleton for loading .prompt text files
- PromptComposer: 5-layer composition engine using string formatting

Usage:
    from app.prompts import PromptComposer, prompt_registry

    # Compose a route-specific prompt
    composer = PromptComposer()
    prompt = composer.compose_route_prompt(
        route='math',
        postprocessing=[],
        format_context='standard'
    )

    # Access utility prompts
    detection_prompt = composer.get_detection_prompt()
    extraction_prompt = composer.get_extraction_prompt()
"""

from app.prompts.registry import PromptRegistry, prompt_registry
from app.prompts.composer import PromptComposer

__all__ = [
    'PromptRegistry',
    'prompt_registry',
    'PromptComposer',
]
