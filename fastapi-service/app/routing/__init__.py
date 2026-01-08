"""Routing module for request routing using Strategy and Chain of Responsibility patterns.

This module provides:
- Route: Abstract base class for routes
- Concrete route implementations (MathRoute, SimpleCodeRoute, etc.)
- Router: Chain of Responsibility router
- RouteHandler: Facade for route configuration and prompt building

Usage:
    from app.routing import Router, MathRoute, SimpleCodeRoute
    from app.prompts.composer import PromptComposer

    composer = PromptComposer()
    router = Router(composer)
    handler = await router.route("integrate x^2 + 3x")
    config = handler.get_config()
"""

from app.routing.route import (
    Route,
    MathRoute,
    SimpleCodeRoute,
    ReasoningRoute,
    ResearchRoute,
    SelfHandleRoute
)
from app.routing.router import Router
from app.routing.route_handler import RouteHandler

__all__ = [
    'Route',
    'MathRoute',
    'SimpleCodeRoute',
    'ReasoningRoute',
    'ResearchRoute',
    'SelfHandleRoute',
    'Router',
    'RouteHandler',
]
