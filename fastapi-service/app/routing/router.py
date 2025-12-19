"""Router for routing requests to appropriate handlers using LLM classification.

This module implements intelligent routing using LLM-based classification.
The Router uses gpt-oss:20b to classify requests and route them to the
appropriate handler, falling back to REASONING if classification fails.
"""

import sys
sys.path.insert(0, '/shared')

import asyncio
from typing import Dict, Any, TYPE_CHECKING

from strands import Agent
from strands.models.ollama import OllamaModel

from app.routing.route import (
    MathRoute,
    SimpleCodeRoute,
    ComplexCodeRoute,
    ResearchRoute,
    ReasoningRoute,
    SelfHandleRoute
)
from app.routing.route_handler import RouteHandler
import logging_client

if TYPE_CHECKING:
    from app.prompts.composer import PromptComposer

logger = logging_client.setup_logger('fastapi')


class Router:
    """Intelligent router using LLM classification.

    Receives configuration from RouterService (which gets it from settings/env),
    making it configurable and testable.

    The Router:
    1. Loads classification prompt from JSON config
    2. Uses LLM (gpt-oss:20b) to classify requests
    3. Returns appropriate RouteHandler based on classification
    4. Falls back to REASONING if classification fails
    """

    def __init__(
        self,
        prompt_composer: 'PromptComposer',
        ollama_host: str,
        router_model_id: str
    ):
        """Initialize Router with LLM configuration.

        Args:
            prompt_composer: PromptComposer instance for loading prompts from JSON
            ollama_host: Ollama API host (from settings.OLLAMA_HOST)
            router_model_id: Model ID for classification (from settings.ROUTER_MODEL)
        """
        self.prompt_composer = prompt_composer
        self.ollama_host = ollama_host
        self.router_model_id = router_model_id

        # Load classification prompt from JSON config
        self.classification_prompt = self.prompt_composer.get_classification_prompt()

        # Initialize route instances (data holders, not matchers)
        self.routes = {
            'MATH': MathRoute(),
            'SIMPLE_CODE': SimpleCodeRoute(),
            'COMPLEX_CODE': ComplexCodeRoute(),
            'REASONING': ReasoningRoute(),
            'RESEARCH': ResearchRoute(),
            'SELF_HANDLE': SelfHandleRoute()
        }
        self.fallback_route = ReasoningRoute()  # Most capable fallback

        logger.info(f"✅ Router initialized with LLM classification (model: {router_model_id})")

    async def route(self, user_message: str, context: Dict[str, Any] = None) -> RouteHandler:
        """Use LLM to classify request and return appropriate RouteHandler.

        Args:
            user_message: User's input message
            context: Optional context dict (e.g., file_refs)

        Returns:
            RouteHandler configured for the classified route

        Example:
            >>> router = Router(prompt_composer, "http://ollama:11434", "gpt-oss:20b")
            >>> handler = await router.route("integrate x^2 + 3x + 1")
            >>> print(handler.get_route_name())
            'MATH'
        """
        try:
            logger.info(f"🔀 Classifying request: {user_message[:100]}...")

            # Create Ollama model via Strands (config from settings)
            router_model = OllamaModel(
                host=self.ollama_host,  # From settings.OLLAMA_HOST
                model_id=self.router_model_id,  # From settings.ROUTER_MODEL
                temperature=0.1,  # Low for deterministic classification
                keep_alive="120s"  # Smart router reuse for SELF_HANDLE
            )

            # Create Strands Agent for classification
            loop = asyncio.get_event_loop()
            agent = Agent(
                model=router_model,
                tools=[],  # No tools - pure classification
                system_prompt=self.classification_prompt
            )

            # Invoke agent with user message
            response = await loop.run_in_executor(None, agent, f"USER REQUEST: {user_message}")
            route_str = str(response).strip().upper()

            # Parse and return appropriate route
            if route_str in self.routes:
                logger.info(f"✅ Classified as: {route_str}")
                return RouteHandler(self.routes[route_str], self.prompt_composer)
            else:
                # Fallback: try to extract route name from response
                for route_name in self.routes.keys():
                    if route_name in route_str:
                        logger.warning(f"⚠️ Extracted route from response: {route_name}")
                        return RouteHandler(self.routes[route_name], self.prompt_composer)

                # Last resort: fallback to REASONING
                logger.warning(f"⚠️ Classification unclear: '{route_str}', defaulting to REASONING")
                return RouteHandler(self.fallback_route, self.prompt_composer)

        except Exception as e:
            logger.error(f"❌ Classification failed: {e}, defaulting to REASONING")
            return RouteHandler(self.fallback_route, self.prompt_composer)
