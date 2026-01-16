"""Router for TROISE AI.

Routes user input to one of 4 classifications using LLM.
Simple plain-text response format for reliable parsing.

Classifications:
- GENERAL: Chat, Q&A, general tasks (uses skill gateway for specialized instructions)
- RESEARCH: Deep research requiring web searches and multiple sources
- CODE: Code writing, debugging, technical implementation
- BRAINDUMP: Thought capture, organization, journaling
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, TYPE_CHECKING

from strands import Agent

from .config import Config

if TYPE_CHECKING:
    from .interfaces.services import IVRAMOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class RoutingResult:
    """Result of routing classification."""
    type: str  # "skill" or "agent"
    name: str  # Name of the skill or agent
    reason: str  # Brief explanation for the routing decision
    confidence: float = 0.9  # Confidence score (0.0-1.0)
    fallback: bool = False  # True if this is a fallback to default


# Mapping from classification to handler
ROUTE_MAP = {
    "GENERAL": ("agent", "general"),  # Uses skill gateway for specialized tasks
    "RESEARCH": ("agent", "deep_research"),
    "CODE": ("agent", "agentic_code"),
    "BRAINDUMP": ("agent", "braindump"),
}


class Router:
    """
    Routes input to one of 4 classifications using LLM.

    Uses a simple plain-text response format for reliable parsing.
    The smaller routing table (4 options vs 40+) allows room for
    full file_context without overwhelming the router model.

    Uses VRAMOrchestrator.get_model() with additional_args=None to
    disable thinking for fast, deterministic classification.

    Example:
        router = Router(config, vram_orchestrator)
        result = await router.route("Research quantum computing advances", context)
        # result.type = "agent", result.name = "deep_research"
    """

    ROUTING_PROMPT = """Reasoning: low

You are a request classifier. Analyze the user's request and classify it.

CLASSIFICATIONS:

1. GENERAL - General chat, Q&A, explanations, simple tasks
   Examples: "What is Python?", "Explain recursion", "Tell me about HTTP"

2. RESEARCH - Deep research requiring extensive web searches and many sources
   Examples: "Research the history of Bitcoin regulation", "Find latest AI developments"

3. CODE - Code writing, debugging, technical implementation
   Examples: "Write a function to reverse a string", "Fix this bug", "Build a REST API"

4. BRAINDUMP - Thought capture, organization, journaling, brain dumps
   Examples: "Let me dump my thoughts about...", "I need to organize my ideas"

USER REQUEST: {user_input}
{file_context_line}
Output ONLY the classification name (e.g., "GENERAL" or "CODE"), nothing else."""

    DEFAULT_ROUTE = "GENERAL"

    def __init__(
        self,
        config: Config,
        vram_orchestrator: "IVRAMOrchestrator",
    ):
        """
        Initialize the router.

        Args:
            config: Application configuration.
            vram_orchestrator: VRAM orchestrator for model access.
        """
        self._config = config
        self._orchestrator = vram_orchestrator

    async def route(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        file_context: Optional[str] = None,
    ) -> RoutingResult:
        """
        Route user input to appropriate handler.

        Args:
            user_input: The user's message/request.
            context: Optional context dict (interface, user_id, etc.).
            file_context: Optional extracted file content (full, no truncation).

        Returns:
            RoutingResult indicating which skill/agent to use.
        """
        # Build file context line for prompt (only if files present)
        file_context_line = ""
        if file_context:
            file_context_line = f"ATTACHED FILE CONTENT:\n{file_context}\n"

        # Build system prompt for classification
        system_prompt = self.ROUTING_PROMPT.format(
            user_input=user_input,
            file_context_line=file_context_line,
        )

        try:
            # Get router model from profile
            router_model_id = self._config.profile.router_model
            logger.debug(f"Routing with model: {router_model_id}")

            # Get model through VRAMOrchestrator
            # Note: gpt-oss models ignore think=False and always generate thinking tokens.
            # We use max_tokens=500 to give room for thinking + classification output.
            route_start = time.time()
            router_model = await self._orchestrator.get_model(
                model_id=router_model_id,
                temperature=0.1,  # Low temp for consistent classification
                max_tokens=500,  # Room for thinking tokens + classification
                additional_args=None,  # Will use profile's think setting
            )

            # Create Strands Agent for classification
            agent = Agent(
                model=router_model,
                tools=[],  # No tools - pure classification
                system_prompt=system_prompt,
            )

            # Run agent synchronously (Strands Agent is sync)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, agent, user_input)
            response_str = str(response).strip()

            route_ms = (time.time() - route_start) * 1000
            logger.info(f"Router raw response ({len(response_str)} chars): '{response_str}'")

            # Parse plain text response
            result = self._parse_response(response_str)

            logger.info(f"Routed to {result.type}:{result.name} in {route_ms:.0f}ms")
            return result

        except Exception as e:
            logger.error(f"Routing failed: {e}")
            return self._fallback_result()

    def _parse_response(self, response: str) -> RoutingResult:
        """
        Parse plain text LLM response into RoutingResult.

        Args:
            response: Raw LLM response text.

        Returns:
            Parsed RoutingResult.
        """
        # Clean and uppercase response
        route_str = response.strip().upper()

        # Check for exact match first
        if route_str in ROUTE_MAP:
            route_type, route_name = ROUTE_MAP[route_str]
            return RoutingResult(
                type=route_type,
                name=route_name,
                reason=f"Classified as {route_str}",
                confidence=0.9,
            )

        # Try to extract route name from response (in case of extra text)
        for route_name in ROUTE_MAP.keys():
            if route_name in route_str:
                route_type, handler_name = ROUTE_MAP[route_name]
                logger.warning(f"Extracted route from response: {route_name}")
                return RoutingResult(
                    type=route_type,
                    name=handler_name,
                    reason=f"Extracted {route_name} from response",
                    confidence=0.7,
                )

        # Fallback
        logger.warning(f"Unknown classification: '{route_str}', defaulting to GENERAL")
        return self._fallback_result()

    def _fallback_result(self) -> RoutingResult:
        """
        Create a fallback result when routing fails.

        Returns:
            Fallback RoutingResult using GENERAL route.
        """
        route_type, route_name = ROUTE_MAP[self.DEFAULT_ROUTE]
        return RoutingResult(
            type=route_type,
            name=route_name,
            reason="Fallback due to routing failure",
            confidence=0.5,
            fallback=True,
        )

    def get_routing_table(self) -> str:
        """
        Get the current routing table for debugging.

        Returns:
            The routing table as a formatted string.
        """
        lines = ["Available Routes:"]
        for route, (handler_type, handler_name) in ROUTE_MAP.items():
            lines.append(f"  {route} -> {handler_type}:{handler_name}")
        return "\n".join(lines)
