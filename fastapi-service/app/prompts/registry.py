"""Simplified prompt registry for loading .prompt text files.

This module provides the PromptRegistry that loads human-readable .prompt files
instead of complex JSON configs with template classes.

The registry implements caching to avoid re-reading files on every request.
"""

from pathlib import Path
from typing import Dict, Optional


class PromptRegistry:
    """Loads prompt templates from .prompt text files.

    This is a simple file loader that reads .prompt files and caches them.
    No complex template classes or JSON parsing - just plain text files.

    Usage:
        from app.prompts.registry import prompt_registry

        # Get a route prompt
        math_prompt = prompt_registry.get_prompt('routes', 'math')

        # Get a layer prompt
        role_prompt = prompt_registry.get_prompt('layers', 'role')

        # Get a routing prompt
        classification_prompt = prompt_registry.get_prompt('routing', 'classification')
    """

    _instance: Optional['PromptRegistry'] = None

    def __new__(cls):
        """Ensure only one instance exists (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize registry.

        This is only executed once due to Singleton pattern.
        """
        if self._initialized:
            return

        self._prompts_dir = Path(__file__).parent
        self._cache: Dict[str, str] = {}
        self._initialized = True

    def get_prompt(self, category: str, name: str) -> str:
        """Load prompt from .prompt file.

        Args:
            category: Prompt category ('routes', 'layers', 'routing', or 'artifacts')
            name: Prompt name without extension (e.g., 'math', 'role', 'classification')

        Returns:
            Raw prompt template string

        Raises:
            FileNotFoundError: If prompt file doesn't exist

        Example:
            >>> registry = PromptRegistry()
            >>> math_prompt = registry.get_prompt('routes', 'math')
            >>> # Returns the full MATH prompt as a string with {placeholders}
        """
        cache_key = f"{category}/{name}"

        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Load from file
        prompt_file = self._prompts_dir / category / f"{name}.prompt"

        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

        prompt = prompt_file.read_text(encoding='utf-8')

        # Cache it
        self._cache[cache_key] = prompt

        return prompt

    def list_available_prompts(self, category: str) -> list:
        """Get list of all available prompts in a category.

        Args:
            category: Prompt category ('routes', 'layers', 'routing', or 'artifacts')

        Returns:
            List of prompt names (without .prompt extension)

        Example:
            >>> registry = PromptRegistry()
            >>> print(registry.list_available_prompts('routes'))
            ['math', 'simple_code', 'reasoning', 'research', 'self_handle']
        """
        category_dir = self._prompts_dir / category

        if not category_dir.exists():
            return []

        return [
            f.stem  # filename without extension
            for f in category_dir.glob('*.prompt')
        ]


# Singleton instance for application-wide use
prompt_registry = PromptRegistry()
