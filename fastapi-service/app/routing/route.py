"""Route abstraction for request routing.

This module implements route classes as data holders for model configuration.
Each route encapsulates model configuration (model ID, mode) without any
routing logic - routing is handled by the Router class using LLM classification.
"""

from typing import Dict, Any
from app.config import settings


class Route:
    """Base class for all routes.

    Routes are data holders that store model configuration for different
    request types. Routing logic is handled by the Router class using LLM.
    """

    def __init__(self, name: str, model_attr: str, mode: str = 'single'):
        """Initialize route with name and settings attribute name.

        Args:
            name: Route name (e.g., "MATH", "SIMPLE_CODE")
            model_attr: Settings attribute name (e.g., "MATH_MODEL")
            mode: Execution mode (default: 'single')
        """
        self.name = name
        self.model_attr = model_attr  # Store attribute name, not value
        self.mode = mode

    def get_model_config(self) -> Dict[str, Any]:
        """Get model configuration for this route.

        Reads model dynamically from active profile to support runtime profile switching.

        Returns:
            Dict with 'model' and 'mode' keys
        """
        # Read model from settings dynamically (supports profile switching)
        model = getattr(settings, self.model_attr)
        return {
            'model': model,
            'mode': self.mode
        }


class MathRoute(Route):
    """Mathematical problem solving route.

    Handles:
    - Integration, differentiation, derivatives
    - Equation solving
    - Calculations, evaluations
    - Limits, summations
    - Mathematical notation (∫, ∑, ∂, √, etc.)

    Model: Reads from active profile's MATH_MODEL
    """

    def __init__(self):
        super().__init__(name='MATH', model_attr='MATH_MODEL')


class SimpleCodeRoute(Route):
    """Simple code writing route - single functions, algorithms, scripts.

    Handles:
    - Function implementations
    - Algorithm coding (sorting, searching, etc.)
    - Bug fixes on small code snippets
    - Code explanations
    - Single-file scripts

    Model: Reads from active profile's SIMPLE_CODER_MODEL
    """

    def __init__(self):
        super().__init__(name='SIMPLE_CODE', model_attr='SIMPLE_CODER_MODEL')


class ComplexCodeRoute(Route):
    """Complex code and system design route.

    Handles:
    - System architecture design
    - Multi-component applications
    - API design
    - Design patterns implementation
    - Scalability & performance optimization
    - Full-stack implementations

    Model: Reads from active profile's COMPLEX_CODER_MODEL
    """

    def __init__(self):
        super().__init__(name='COMPLEX_CODE', model_attr='COMPLEX_CODER_MODEL')


class ReasoningRoute(Route):
    """Analytical reasoning with limited web search.

    Handles:
    - Comparisons (X vs Y)
    - Trade-off analysis
    - Pros/cons evaluations
    - Decision-making support
    - Analytical questions

    Model: Reads from active profile's REASONING_MODEL
    Web search: Limited to 2-3 sources
    """

    def __init__(self):
        super().__init__(name='REASONING', model_attr='REASONING_MODEL')


class ResearchRoute(Route):
    """Deep research with extensive web search.

    Handles:
    - In-depth research topics
    - Current events investigation
    - Latest developments queries
    - Multi-source information gathering

    Model: Reads from active profile's RESEARCH_MODEL
    Web search: Extensive, up to 5 sources
    Thinking mode: Enabled (for complex analysis)
    """

    def __init__(self):
        super().__init__(name='RESEARCH', model_attr='RESEARCH_MODEL')


class SelfHandleRoute(Route):
    """General conversation fallback route.

    Handles:
    - General questions
    - Conversational interactions
    - Quick facts
    - Simple information queries
    - Everything else (fallback)

    Model: Reads from active profile's ROUTER_MODEL
    """

    def __init__(self):
        super().__init__(name='SELF_HANDLE', model_attr='ROUTER_MODEL')
