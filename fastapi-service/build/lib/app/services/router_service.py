"""Intelligent request routing service using gpt-oss:20b."""
import sys
sys.path.insert(0, '/shared')

from enum import Enum
from typing import Dict
import asyncio

from strands import Agent
from strands.models.ollama import OllamaModel
from app.config import settings
import logging_client

logger = logging_client.setup_logger('fastapi')


class RouteType(Enum):
    """Available request routes."""
    SELF_HANDLE = "SELF_HANDLE"
    SIMPLE_CODE = "SIMPLE_CODE"
    REASONING = "REASONING"


class RouterService:
    """Routes requests to appropriate models based on classification."""

    def __init__(self):
        self.router_model_id = settings.ROUTER_MODEL  # gpt-oss:20b
        self.ollama_host = settings.OLLAMA_HOST
        self.classification_prompt = self._build_classification_prompt()

    def _build_classification_prompt(self) -> str:
        """Build the router classification prompt."""
        return """You are a request classifier for an AI assistant system.

Analyze the user's request and classify it into ONE of these routes:

1. SELF_HANDLE - Simple questions, general conversation, quick facts
   Examples: "What is Python?", "Explain recursion", "Tell me about HTTP"

2. SIMPLE_CODE - Any coding task (simple or complex), bug fixes, design, architecture
   Examples: "Write a function to reverse a string", "Design a REST API",
             "Build a distributed caching system", "Fix this syntax error"

3. REASONING - Deep analysis, comparisons, research, investigations, trade-offs
   Examples: "Compare REST vs GraphQL", "Research authentication best practices",
             "Analyze microservices trade-offs", "Investigate caching strategies"

Output ONLY the route name (e.g., "SIMPLE_CODE"), nothing else."""

    async def classify_request(self, user_message: str) -> RouteType:
        """
        Classify user request using gpt-oss:20b via Strands Agent.

        Uses Strands framework for consistent LLM invocation pattern across the system.

        Args:
            user_message: User's input message

        Returns:
            RouteType enum indicating the appropriate route

        Raises:
            Exception: If classification fails
        """
        try:
            logger.info(f"🔀 Classifying request: {user_message[:100]}...")

            # Create Ollama model via Strands (consistent with rest of codebase)
            router_model = OllamaModel(
                host=self.ollama_host,
                model_id=self.router_model_id,
                temperature=0.1  # Low temperature for consistent classification
            )

            # Create Strands Agent for classification (no tools needed)
            loop = asyncio.get_event_loop()
            agent = Agent(
                model=router_model,
                tools=[],  # No tools - pure classification
                system_prompt=self.classification_prompt
            )

            # Invoke agent via Strands
            response = await loop.run_in_executor(None, agent, f"USER REQUEST: {user_message}")
            route_str = str(response).strip().upper()

            # Parse route
            try:
                route = RouteType[route_str]
                logger.info(f"✅ Classified as: {route.value}")
                return route
            except KeyError:
                # Fallback: try to find route name in response
                for route_type in RouteType:
                    if route_type.value in route_str:
                        logger.warning(f"⚠️ Extracted route from response: {route_type.value}")
                        return route_type

                # Last resort fallback
                logger.warning(f"⚠️ Classification unclear: '{route_str}', defaulting to REASONING")
                return RouteType.REASONING

        except Exception as e:
            logger.error(f"❌ Classification failed: {e}, defaulting to REASONING")
            return RouteType.REASONING  # Most capable fallback

    def get_model_for_route(self, route: RouteType) -> Dict[str, str]:
        """
        Get model configuration for a route.

        Args:
            route: Classified route type

        Returns:
            Dict with 'model', 'mode', and 'route_type' for prompt selection
        """
        route_configs = {
            RouteType.SELF_HANDLE: {
                'model': settings.ROUTER_MODEL,  # gpt-oss:20b
                'mode': 'single',
                'route_type': 'SELF_HANDLE'  # NEW: for prompt selection
            },
            RouteType.SIMPLE_CODE: {
                'model': settings.CODER_MODEL,  # qwen2.5-coder:7b
                'mode': 'single',
                'route_type': 'SIMPLE_CODE'  # NEW: for prompt selection
            },
            RouteType.REASONING: {
                'model': settings.REASONING_MODEL,  # deepseek-r1:8b
                'mode': 'single',
                'route_type': 'REASONING'  # NEW: for prompt selection
            }
        }

        return route_configs.get(route, route_configs[RouteType.REASONING])
