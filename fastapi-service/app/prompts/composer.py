"""Simplified prompt composer for composing prompts from .prompt text files.

This module provides the PromptComposer class that implements the 5-layer
composition pattern using simple string formatting:
1. ROLE & IDENTITY - Who you are
2. CRITICAL PROTOCOLS - Special cases (file creation, thinking mode)
3. TASK DEFINITION - What to do (route-specific)
4. FORMAT RULES - How to format (context-aware)
5. USER CUSTOMIZATION - User preferences

The composer loads .prompt files and uses Python's .format() for substitution.

Profile-Aware Loading:
- Automatically detects active profile (performance, conservative, balanced)
- Loads profile-specific prompt variants when available
- Falls back to default prompts if variant doesn't exist
"""

from datetime import datetime
from typing import List, Optional
from app.prompts.registry import prompt_registry
from app.config import get_active_profile
import logging_client

logger = logging_client.setup_logger('fastapi')


class PromptComposer:
    """Composes prompts by loading and formatting .prompt files.

    This is a simple string formatter that:
    - Loads .prompt text files from PromptRegistry
    - Substitutes {placeholders} using .format()
    - Layers prompts in the correct order

    Usage:
        composer = PromptComposer()
        prompt = composer.compose_route_prompt(
            route='math',
            postprocessing=['OUTPUT_ARTIFACT'],
            format_context='file_creation',
            user_base_prompt='Be very detailed'
        )
    """

    def __init__(self):
        """Initialize composer with prompt registry and active profile."""
        self.registry = prompt_registry

        # Get active profile for profile-aware prompt loading
        try:
            self.profile_name = get_active_profile().profile_name
            logger.info(f"✅ PromptComposer initialized with {self.profile_name} profile")
        except RuntimeError:
            # Fallback if no profile set (e.g., during initialization)
            self.profile_name = None
            logger.warning("⚠️  PromptComposer initialized without active profile (will use default prompts)")

    def compose_route_prompt(
        self,
        route: str,
        postprocessing: List[str] = None,
        format_context: str = 'standard',
        user_base_prompt: Optional[str] = None,
        context_window: Optional[int] = None,
        source: str = 'discord',
        **kwargs
    ) -> str:
        """Compose a complete prompt using 5-layer architecture.

        Layers (in order):
        1. ROLE & IDENTITY - Who you are
        2. CRITICAL PROTOCOLS - Special cases (file creation, thinking mode)
        3. TASK DEFINITION - What to do (route-specific)
        4. FORMAT RULES - How to format (source-aware: discord vs webui)
        5. USER CUSTOMIZATION - User preferences

        Args:
            route: Route name (math, simple_code, reasoning, research, self_handle)
            postprocessing: List of postprocessing strategies (e.g., ['OUTPUT_ARTIFACT'])
            format_context: 'standard' or 'file_creation' for context-aware formatting
            user_base_prompt: Optional user custom prompt
            context_window: Optional context window size in tokens (for performance variants)
            source: Request source ('discord', 'webui', or other) - affects formatting rules
            **kwargs: Additional context for string formatting

        Returns:
            Composed system prompt string

        Example:
            >>> composer = PromptComposer()
            >>> prompt = composer.compose_route_prompt(
            ...     route='math',
            ...     postprocessing=[],
            ...     format_context='standard',
            ...     context_window=40960,
            ...     source='webui'
            ... )
        """
        layers = []
        postprocessing = postprocessing or []

        # LAYER 1: ROLE & IDENTITY (always first, source-aware)
        role_name = f'role_{source}' if source in ['webui', 'discord'] else 'role'
        try:
            role = self.registry.get_prompt('layers', role_name)
            logger.debug(f"📝 Using role prompt for source: {source}")
        except Exception:
            # Fallback to default role if source-specific doesn't exist
            role = self.registry.get_prompt('layers', 'role')
            logger.debug(f"📝 Using default role prompt (source: {source})")
        layers.append(role)

        # LAYER 2: CRITICAL PROTOCOLS (conditional, no profile variant)
        if 'OUTPUT_ARTIFACT' in postprocessing:
            protocol = self.registry.get_prompt('layers', 'file_creation_protocol')
            layers.append(protocol)

        # LAYER 3: TASK DEFINITION (route-specific with profile-aware loading)
        route_prompt = self.registry.get_prompt('routes', route.lower(), profile=self.profile_name)

        # Load sub-prompts for substitution (profile-aware)
        tool_usage = self.registry.get_prompt('layers', 'tool_usage')
        
        # Load source-specific format rules (webui vs discord)
        format_rules_name = f'format_rules_{source}' if source in ['webui', 'discord'] else 'format_rules'
        try:
            format_rules = self.registry.get_prompt('layers', format_rules_name, profile=self.profile_name)
            logger.debug(f"📝 Using format rules for source: {source}")
        except Exception:
            # Fallback to default format_rules if source-specific doesn't exist
            format_rules = self.registry.get_prompt('layers', 'format_rules', profile=self.profile_name)
            logger.debug(f"📝 Using default format rules (source: {source})")

        # Format the route prompt with substitutions
        format_vars = {
            'current_date': datetime.now().strftime("%Y-%m-%d"),
            'tool_usage_rules': tool_usage,
            'format_rules': format_rules,
            'critical_output_format': "",  # Empty for now, could load from file if needed
            **kwargs
        }

        # Add context_window if provided (for performance variants)
        if context_window:
            format_vars['context_window'] = context_window

        try:
            route_prompt = route_prompt.format(**format_vars)
        except KeyError as e:
            # If a placeholder is missing, just leave it as-is
            pass

        layers.append(route_prompt)

        # LAYER 4: FORMAT RULES - already included in route prompt via {format_rules}
        # No need to add separately

        # LAYER 5: USER CUSTOMIZATION (optional)
        if user_base_prompt:
            layers.append(f"\n\nUser Instructions:\n{user_base_prompt}")

        # Compose with clear separation (double newlines between layers)
        return "\n\n".join(layers)

    def get_classification_prompt(self) -> str:
        """Get route classification prompt for LLM-based routing.

        Returns:
            Classification prompt string

        Example:
            >>> composer = PromptComposer()
            >>> prompt = composer.get_classification_prompt()
        """
        return self.registry.get_prompt('routing', 'classification')

    def get_rephrase_prompt(self) -> str:
        """Get file language rephrase prompt.

        Used to remove file creation language from user messages:
        - "save to .md file" → removed
        - "create bitcoin.py" → "implement bitcoin algorithm"

        Returns:
            Rephrase prompt string

        Example:
            >>> composer = PromptComposer()
            >>> prompt = composer.get_rephrase_prompt()
        """
        return self.registry.get_prompt('routing', 'rephrase')

    def get_detection_prompt(self) -> str:
        """Get artifact detection prompt.

        Used by OutputArtifactDetector to detect if user wants file output.

        Returns:
            Detection prompt string

        Example:
            >>> composer = PromptComposer()
            >>> prompt = composer.get_detection_prompt()
        """
        return self.registry.get_prompt('artifacts', 'detection')

    def get_extraction_prompt(self) -> str:
        """Get artifact extraction prompt.

        Used by OutputArtifactStrategy to extract file content from responses.

        Returns:
            Extraction prompt string

        Example:
            >>> composer = PromptComposer()
            >>> prompt = composer.get_extraction_prompt()
        """
        return self.registry.get_prompt('artifacts', 'extraction')
