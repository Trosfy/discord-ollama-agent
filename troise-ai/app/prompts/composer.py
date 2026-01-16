"""Prompt Composer for TROISE AI.

Composes multi-layer prompts for agents and skills with profile and interface awareness.
"""
import logging
from datetime import date
from typing import Optional, TYPE_CHECKING

from .registry import PromptRegistry, prompt_registry

if TYPE_CHECKING:
    from ..core.config import Config
    from ..core.context import UserProfile

logger = logging.getLogger(__name__)


class PromptComposer:
    """Composes multi-layer prompts for agents and skills.

    4-Layer Composition:
    1. AGENT/SKILL IDENTITY - Who you are, what you do
    2. TOOL USAGE RULES - How to use tools (if agent)
    3. INTERFACE FORMATTING - Discord/Web/CLI/API rules
    4. USER PERSONALIZATION - User preferences (optional)

    Example:
        composer = PromptComposer(registry, config)
        prompt = composer.compose_agent_prompt(
            agent_name="braindump",
            interface="discord",
            profile="performance",
            user_profile=user_profile,
        )
    """

    def __init__(
        self,
        registry: PromptRegistry = None,
        config: "Config" = None,
    ):
        """Initialize the prompt composer.

        Args:
            registry: PromptRegistry instance. Defaults to singleton.
            config: Config instance for default profile.
        """
        self._registry = registry or prompt_registry
        self._config = config

    def _get_profile(self, profile: Optional[str] = None) -> str:
        """Get profile name, falling back to config default.

        Args:
            profile: Explicit profile or None.

        Returns:
            Profile name ('conservative', 'balanced', 'performance').
        """
        if profile:
            return profile

        if self._config and hasattr(self._config, "profile"):
            return self._config.profile.profile_name

        return "balanced"

    def compose_agent_prompt(
        self,
        agent_name: str,
        interface: str,
        profile: Optional[str] = None,
        user_profile: Optional["UserProfile"] = None,
        **format_vars,
    ) -> str:
        """Compose complete agent system prompt.

        Layers:
        1. Agent identity (from agents/{agent_name}.prompt)
        2. Interface formatting (from layers/interface_{interface}.prompt)
        3. User personalization (from user_profile.get_personalization_context())

        Template variables in prompts:
        - {interface_context}: Replaced with interface layer content
        - {personalization_context}: Replaced with user preferences
        - {current_date}: Today's date
        - Any additional **format_vars

        Args:
            agent_name: Agent identifier ('braindump', 'deep_research', etc.)
            interface: Interface type ('discord', 'web', 'cli', 'api')
            profile: Profile for prompt variant ('conservative', 'balanced', 'performance')
            user_profile: Optional user profile for personalization
            **format_vars: Additional template variables

        Returns:
            Complete system prompt string.
        """
        effective_profile = self._get_profile(profile)

        # Layer 1: Agent identity
        try:
            agent_prompt = self._registry.get_prompt(
                category="agents",
                name=agent_name,
                profile=effective_profile,
            )
        except FileNotFoundError:
            logger.error(f"Agent prompt not found: {agent_name}, profile={effective_profile}")
            raise

        # Layer 2: Interface formatting
        try:
            interface_context = self._registry.get_prompt(
                category="layers",
                name=f"interface_{interface}",
                profile=effective_profile,
            )
        except FileNotFoundError:
            logger.warning(f"Interface layer not found: {interface}, using empty")
            interface_context = ""

        # Layer 3: User personalization
        personalization_context = ""
        if user_profile:
            personalization_context = user_profile.get_personalization_context()

        # Build template variables
        template_vars = {
            "interface_context": interface_context,
            "personalization_context": personalization_context or "No specific user preferences.",
            "current_date": date.today().isoformat(),
            **format_vars,
        }

        # Apply template substitution
        try:
            composed = agent_prompt.format(**template_vars)
        except KeyError as e:
            logger.error(f"Missing template variable in {agent_name}.prompt: {e}")
            # Fall back to partial substitution
            composed = agent_prompt
            for key, value in template_vars.items():
                composed = composed.replace(f"{{{key}}}", str(value))

        # Prepend date context
        composed = f"Today's date: {date.today().isoformat()}\n\n{composed}"

        logger.debug(
            f"Composed agent prompt: agent={agent_name}, profile={effective_profile}, "
            f"interface={interface}, length={len(composed)}"
        )

        return composed

    def compose_skill_prompt(
        self,
        skill_system_prompt: str,
        interface: str,
        profile: Optional[str] = None,
        user_profile: Optional["UserProfile"] = None,
    ) -> str:
        """Compose skill prompt with interface and personalization layers.

        Skills already have their own system prompts from skill.md files.
        This adds interface context and personalization.

        Args:
            skill_system_prompt: The skill's system prompt from skill.md
            interface: Interface type ('discord', 'web', 'cli', 'api')
            profile: Profile for interface layer variant
            user_profile: Optional user profile for personalization

        Returns:
            Complete skill system prompt with layers.
        """
        effective_profile = self._get_profile(profile)

        # Get interface context
        try:
            interface_context = self._registry.get_prompt(
                category="layers",
                name=f"interface_{interface}",
                profile=effective_profile,
            )
        except FileNotFoundError:
            interface_context = ""

        # Get personalization
        personalization_context = ""
        if user_profile:
            personalization_context = user_profile.get_personalization_context()

        # Template variables
        template_vars = {
            "interface_context": interface_context,
            "personalization_context": personalization_context or "No specific user preferences.",
            "current_date": date.today().isoformat(),
        }

        # Apply template substitution
        try:
            composed = skill_system_prompt.format(**template_vars)
        except KeyError as e:
            logger.debug(f"Missing template variable in skill prompt: {e}")
            # Fall back to partial substitution
            composed = skill_system_prompt
            for key, value in template_vars.items():
                composed = composed.replace(f"{{{key}}}", str(value))

        # Prepend date context
        composed = f"Today's date: {date.today().isoformat()}\n\n{composed}"

        return composed


# Factory function for container registration
def create_prompt_composer(
    registry: PromptRegistry = None,
    config: "Config" = None,
) -> PromptComposer:
    """Create a PromptComposer instance.

    Args:
        registry: PromptRegistry instance
        config: Config instance

    Returns:
        PromptComposer instance
    """
    return PromptComposer(registry=registry, config=config)
