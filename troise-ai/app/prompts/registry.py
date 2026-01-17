"""Prompt Registry for TROISE AI.

Singleton file loader with profile-aware fallback for loading prompt templates.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class PromptRegistry:
    """Singleton registry for loading prompt files with profile fallback.

    Prompts are loaded from the prompts/ directory with the following lookup order:
    1. prompts/{category}/variants/{profile}/{name}.prompt (if profile specified)
    2. prompts/{category}/{name}.prompt (fallback/default)

    Example:
        registry = PromptRegistry()
        prompt = registry.get_prompt("agents", "braindump", profile="conservative")
    """

    _instance: Optional["PromptRegistry"] = None
    _initialized: bool = False

    def __new__(cls) -> "PromptRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, prompts_dir: Optional[Path] = None):
        """Initialize the prompt registry.

        Args:
            prompts_dir: Path to prompts directory. Defaults to app/prompts/.
        """
        if self._initialized:
            return

        if prompts_dir is None:
            # Default to app/prompts/ relative to this file
            prompts_dir = Path(__file__).parent

        self._prompts_dir = prompts_dir
        self._cache: Dict[str, str] = {}
        self._initialized = True

        logger.info(f"PromptRegistry initialized with prompts_dir: {prompts_dir}")

    def get_prompt(
        self,
        category: str,
        name: str,
        profile: Optional[str] = None,
        graph_domain: Optional[str] = None,
    ) -> str:
        """Load prompt with profile and graph_domain fallback.

        Lookup order (most specific to least specific):
        1. prompts/{category}/variants/{profile}/{graph_domain}/{name}.prompt
        2. prompts/{category}/variants/{profile}/{name}.prompt
        3. prompts/{category}/{name}.prompt (fallback)

        Args:
            category: Prompt category ('agents', 'layers', 'routing', 'preprocessing')
            name: Prompt name without extension
            profile: Optional profile ('performance', 'conservative', 'balanced')
            graph_domain: Optional graph domain ('code', 'research', 'braindump')

        Returns:
            Prompt content as string.

        Raises:
            FileNotFoundError: If prompt not found in any location.
        """
        # Try profile + graph_domain variant first (most specific)
        if profile and profile != "balanced" and graph_domain:
            cache_key = f"{category}/variants/{profile}/{graph_domain}/{name}"
            if cache_key in self._cache:
                return self._cache[cache_key]

            variant_path = (
                self._prompts_dir / category / "variants" / profile / graph_domain / f"{name}.prompt"
            )
            if variant_path.exists():
                content = variant_path.read_text()
                self._cache[cache_key] = content
                logger.debug(f"Loaded prompt variant (profile+domain): {cache_key}")
                return content

        # Try profile-specific variant (if profile provided and not "balanced")
        if profile and profile != "balanced":
            cache_key = f"{category}/variants/{profile}/{name}"
            if cache_key in self._cache:
                return self._cache[cache_key]

            variant_path = self._prompts_dir / category / "variants" / profile / f"{name}.prompt"
            if variant_path.exists():
                content = variant_path.read_text()
                self._cache[cache_key] = content
                logger.debug(f"Loaded prompt variant (profile): {cache_key}")
                return content

        # Fall back to default (balanced)
        cache_key = f"{category}/{name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        default_path = self._prompts_dir / category / f"{name}.prompt"
        if default_path.exists():
            content = default_path.read_text()
            self._cache[cache_key] = content
            logger.debug(f"Loaded prompt: {cache_key}")
            return content

        raise FileNotFoundError(
            f"Prompt not found: category='{category}', name='{name}', "
            f"profile='{profile}', graph_domain='{graph_domain}'. "
            f"Searched: {default_path}"
        )

    def list_prompts(self, category: str) -> List[str]:
        """List available prompts in a category.

        Args:
            category: Prompt category ('agents', 'layers', etc.)

        Returns:
            List of prompt names (without .prompt extension).
        """
        category_dir = self._prompts_dir / category
        if not category_dir.exists():
            return []

        prompts = []
        for path in category_dir.glob("*.prompt"):
            prompts.append(path.stem)

        return sorted(prompts)

    def list_variants(
        self, category: str, profile: str, graph_domain: Optional[str] = None
    ) -> List[str]:
        """List available profile variants in a category.

        Args:
            category: Prompt category
            profile: Profile name ('conservative', 'performance')
            graph_domain: Optional graph domain for nested variants

        Returns:
            List of variant prompt names.
        """
        if graph_domain:
            variants_dir = self._prompts_dir / category / "variants" / profile / graph_domain
        else:
            variants_dir = self._prompts_dir / category / "variants" / profile

        if not variants_dir.exists():
            return []

        variants = []
        for path in variants_dir.glob("*.prompt"):
            variants.append(path.stem)

        return sorted(variants)

    def list_graph_domains(self, category: str, profile: str) -> List[str]:
        """List available graph domains for a profile.

        Args:
            category: Prompt category
            profile: Profile name ('conservative', 'performance')

        Returns:
            List of graph domain names (subdirectories under profile).
        """
        profile_dir = self._prompts_dir / category / "variants" / profile
        if not profile_dir.exists():
            return []

        domains = []
        for path in profile_dir.iterdir():
            if path.is_dir():
                domains.append(path.name)

        return sorted(domains)

    def clear_cache(self):
        """Clear the prompt cache (for development/testing)."""
        self._cache.clear()
        logger.info("Prompt cache cleared")

    def reload(self):
        """Reload prompts by clearing cache.

        Alias for clear_cache() for semantic clarity.
        """
        self.clear_cache()


# Singleton instance
prompt_registry = PromptRegistry()
