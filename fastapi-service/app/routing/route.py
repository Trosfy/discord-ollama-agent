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

    def __init__(self, name: str, model: str, mode: str = 'single'):
        """Initialize route with name and model configuration.

        Args:
            name: Route name (e.g., "MATH", "SIMPLE_CODE")
            model: Model ID to use for this route
            mode: Execution mode (default: 'single')
        """
        self.name = name
        self.model = model
        self.mode = mode

    def get_model_config(self) -> Dict[str, Any]:
        """Get model configuration for this route.

        Returns:
            Dict with 'model' and 'mode' keys
        """
        return {
            'model': self.model,
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

    Model: rnj-1:8b (specialized math model)
    """

    def __init__(self):
        super().__init__(name='MATH', model=settings.MATH_MODEL)


class SimpleCodeRoute(Route):
    """Simple code writing route - single functions, algorithms, scripts.

    Handles:
    - Function implementations
    - Algorithm coding (sorting, searching, etc.)
    - Bug fixes on small code snippets
    - Code explanations
    - Single-file scripts

    Model: rnj-1:8b (fast code generation)
    """

    def __init__(self):
        super().__init__(name='SIMPLE_CODE', model=settings.SIMPLE_CODER_MODEL)


class ComplexCodeRoute(Route):
    """Complex code and system design route.

    Handles:
    - System architecture design
    - Multi-component applications
    - API design
    - Design patterns implementation
    - Scalability & performance optimization
    - Full-stack implementations

    Model: deepcoder:14b (O3-mini level reasoning)
    """

    def __init__(self):
        super().__init__(name='COMPLEX_CODE', model=settings.COMPLEX_CODER_MODEL)


class ReasoningRoute(Route):
    """Analytical reasoning with limited web search.

    Handles:
    - Comparisons (X vs Y)
    - Trade-off analysis
    - Pros/cons evaluations
    - Decision-making support
    - Analytical questions

    Model: magistral:24b (general reasoning model)
    Web search: Limited to 2-3 sources
    """

    def __init__(self):
        super().__init__(name='REASONING', model=settings.REASONING_MODEL)


class ResearchRoute(Route):
    """Deep research with extensive web search.

    Handles:
    - In-depth research topics
    - Current events investigation
    - Latest developments queries
    - Multi-source information gathering

    Model: magistral:24b (general reasoning model with thinking)
    Web search: Extensive, up to 5 sources
    Thinking mode: Enabled (for complex analysis)
    """

    def __init__(self):
        super().__init__(name='RESEARCH', model=settings.RESEARCH_MODEL)


class SelfHandleRoute(Route):
    """General conversation fallback route.

    Handles:
    - General questions
    - Conversational interactions
    - Quick facts
    - Simple information queries
    - Everything else (fallback)

    Model: gpt-oss:20b (general conversation model)
    """

    def __init__(self):
        super().__init__(name='SELF_HANDLE', model=settings.ROUTER_MODEL)
