"""Route handler for managing route-specific configuration and prompt building.

This module provides the RouteHandler class that wraps a Route and PromptComposer
to provide unified access to route configuration and prompt composition.
"""

from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.routing.route import Route
    from app.prompts.composer import PromptComposer


class RouteHandler:
    """Handles route-specific logic and configuration.

    The RouteHandler acts as a bridge between a Route and the PromptComposer,
    providing a unified interface for:
    - Building route-specific prompts
    - Getting route configuration (model, mode, route name)

    This follows the Facade Pattern - simplifying the interface for consumers.
    """

    def __init__(self, route: 'Route', prompt_composer: 'PromptComposer'):
        """Initialize route handler with route and prompt composer.

        Args:
            route: The Route instance to handle
            prompt_composer: PromptComposer for building prompts
        """
        self.route = route
        self.prompt_composer = prompt_composer

    def build_prompt(self, **kwargs) -> str:
        """Build route-specific prompt using composer.

        This delegates to PromptComposer.compose_route_prompt() with the
        route's template name.

        Args:
            **kwargs: Additional context for prompt composition
                - postprocessing: List[str] - Postprocessing strategies
                - format_context: str - 'standard' or 'file_creation'
                - user_base_prompt: Optional[str] - User customization

        Returns:
            Composed system prompt string

        Example:
            >>> handler = RouteHandler(MathRoute(), composer)
            >>> prompt = handler.build_prompt(
            ...     postprocessing=[],
            ...     format_context='standard'
            ... )
        """
        template_name = self.route.get_prompt_template_name()
        return self.prompt_composer.compose_route_prompt(
            route=template_name,
            **kwargs
        )

    def get_config(self) -> Dict[str, Any]:
        """Get complete route configuration.

        Returns dict compatible with Orchestrator expectations:
        - route: str - Route name (e.g., "MATH", "SIMPLE_CODE")
        - model: str - Model ID (e.g., "rnj-1:8b")
        - mode: str - Execution mode (e.g., "single")

        Returns:
            Dict with route configuration

        Example:
            >>> handler = RouteHandler(MathRoute(), composer)
            >>> config = handler.get_config()
            >>> print(config)
            {'route': 'MATH', 'model': 'rnj-1:8b', 'mode': 'single'}
        """
        return {
            'route': self.route.name,
            **self.route.get_model_config()
        }

    def get_route_name(self) -> str:
        """Get the route name.

        Returns:
            Route name (e.g., "MATH", "SIMPLE_CODE")
        """
        return self.route.name

    def get_model(self) -> str:
        """Get the model ID for this route.

        Returns:
            Model ID (e.g., "rnj-1:8b", "qwen2.5-coder:7b")
        """
        return self.route.model
