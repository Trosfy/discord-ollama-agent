"""Simplified prompt registry for loading .prompt text files.

This module provides the PromptRegistry that loads human-readable .prompt files
instead of complex JSON configs with template classes.

The registry implements caching to avoid re-reading files on every request.
"""

from pathlib import Path
from typing import Dict, Optional
import logging_client

logger = logging_client.setup_logger('fastapi')


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

    def get_prompt(self, category: str, name: str, profile: Optional[str] = None) -> str:
        """Load prompt from .prompt file with profile-aware fallback.

        Args:
            category: Prompt category ('routes', 'layers', 'routing', or 'artifacts')
            name: Prompt name without extension (e.g., 'math', 'role', 'classification')
            profile: Optional profile name ('performance', 'conservative', 'balanced')
                    If provided, will check variants/{profile}/ first, then fall back to default

        Returns:
            Raw prompt template string

        Raises:
            FileNotFoundError: If prompt file doesn't exist (neither variant nor default)

        Example:
            >>> registry = PromptRegistry()
            >>> # Load profile-specific variant (or fall back to default)
            >>> math_prompt = registry.get_prompt('routes', 'math', profile='conservative')
            >>> # Load default prompt
            >>> role_prompt = registry.get_prompt('layers', 'role')
        """
        cache_key = f"{category}/{name}" if not profile else f"{category}/{profile}/{name}"

        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]

        prompt_file = None

        # Try profile-specific variant first (if profile provided)
        if profile:
            variant_file = self._prompts_dir / category / 'variants' / profile / f"{name}.prompt"
            if variant_file.exists():
                prompt_file = variant_file
                logger.debug(f"📋 Loading {category}/{name} from {profile} profile variant")

        # Fall back to default prompt
        if not prompt_file:
            default_file = self._prompts_dir / category / f"{name}.prompt"
            if default_file.exists():
                prompt_file = default_file
                if profile:
                    logger.debug(f"📋 Loading {category}/{name} from default (no {profile} variant)")

        if not prompt_file:
            raise FileNotFoundError(
                f"Prompt file not found: {category}/{name} "
                f"(checked profile='{profile}' variant and default)"
            )

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
