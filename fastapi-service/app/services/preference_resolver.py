"""Preference resolution service (Single Responsibility Principle).

Unifies preference handling across all interfaces (Discord, Web UI).
Priority: request['model'] > user_prefs['preferred_model'] > router

SOLID Compliance:
- Single Responsibility: Only resolves preferences
- Open/Closed: New sources can be added without modifying core logic
- Dependency Inversion: Depends on abstractions (IConfigProfile)
"""
import sys
sys.path.insert(0, '/shared')

from dataclasses import dataclass
from typing import Dict, Optional, Callable
import logging_client

logger = logging_client.setup_logger('fastapi')


@dataclass
class ResolvedPreferences:
    """Resolved user preferences for request processing."""

    # Model selection
    model: Optional[str]  # None = use router to determine model
    should_bypass_routing: bool

    # Artifact models (from profile)
    artifact_detection_model: str   # For preprocessing (YES/NO classification)
    artifact_extraction_model: str  # For postprocessing (file creation)

    # Generation settings
    temperature: float
    thinking_enabled: Optional[bool]

    # Source tracking (for logging/debugging)
    model_source: str  # "request", "user_preference", "router"


class PreferenceResolver:
    """
    Resolves preferences from multiple sources with clear priority.

    Priority order (highest to lowest):
    1. request.get('model') - Explicit per-request selection (Web UI/API)
    2. user_prefs.get('preferred_model') - Persistent preference (Discord /model)
    3. None - Let router decide

    When model is resolved (priority 1 or 2), routing is bypassed.
    """

    def __init__(self, profile_getter: Callable):
        """
        Initialize resolver.

        Args:
            profile_getter: Callable that returns current IConfigProfile
        """
        self._get_profile = profile_getter
        logger.info("PreferenceResolver initialized")

    def resolve(
        self,
        request: Dict,
        user_prefs: Dict,
        default_temperature: float = 0.2
    ) -> ResolvedPreferences:
        """
        Resolve preferences with clear priority order.

        Args:
            request: Request dictionary (may contain 'model' key)
            user_prefs: User preferences from storage
            default_temperature: Fallback temperature

        Returns:
            ResolvedPreferences with all resolved settings
        """
        profile = self._get_profile()

        # Resolve model with priority
        request_model = request.get('model')
        user_preferred_model = user_prefs.get('preferred_model')

        if request_model:
            # Highest priority: per-request selection (Web UI model selector)
            model = request_model
            should_bypass = True
            model_source = "request"
            logger.info(f"Using request model: {model} (bypassing routing)")

        elif user_preferred_model:
            # Second priority: persistent preference (Discord /model command)
            model = user_preferred_model
            should_bypass = True
            model_source = "user_preference"
            logger.info(f"Using user preferred model: {model} (bypassing routing)")

        else:
            # Lowest priority: let router decide
            model = None
            should_bypass = False
            model_source = "router"
            logger.debug("No model preference - using router for classification")

        # Resolve temperature (priority: request > user_prefs > default)
        request_temp = request.get('temperature')
        user_temp = user_prefs.get('temperature')
        if request_temp is not None:
            temperature = float(request_temp)
        elif user_temp is not None:
            temperature = float(user_temp)
        else:
            temperature = default_temperature

        # Resolve thinking (priority: request > user_prefs > None/model default)
        request_thinking = request.get('thinking_enabled')
        user_thinking = user_prefs.get('thinking_enabled')
        if request_thinking is not None:
            thinking_enabled = request_thinking
        else:
            thinking_enabled = user_thinking  # May be None (model default)

        # Get artifact models from profile
        artifact_detection_model = profile.artifact_detection_model
        artifact_extraction_model = profile.artifact_extraction_model

        return ResolvedPreferences(
            model=model,
            should_bypass_routing=should_bypass,
            artifact_detection_model=artifact_detection_model,
            artifact_extraction_model=artifact_extraction_model,
            temperature=temperature,
            thinking_enabled=thinking_enabled,
            model_source=model_source
        )
