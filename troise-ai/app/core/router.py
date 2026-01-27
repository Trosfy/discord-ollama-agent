"""Router for TROISE AI.

Routes user input to one of 5 classifications using LLM.
Simple plain-text response format for reliable parsing.

Classifications:
- GENERAL: Chat, Q&A, general tasks (uses skill gateway for specialized instructions)
- RESEARCH: Deep research requiring web searches and multiple sources
- CODE: Code writing, debugging, technical implementation
- BRAINDUMP: Thought capture, organization, journaling
- IMAGE: Image generation, creating pictures, artwork, visualizations

Routes are loaded from app/config/routes.yaml for OCP compliance.
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

from strands import Agent

from .config import Config
from ..config import load_routes_config

if TYPE_CHECKING:
    from .interfaces.services import IVRAMOrchestrator
    from .interfaces.graph import IGraphRegistry

logger = logging.getLogger(__name__)


@dataclass
class RoutingResult:
    """Result of routing classification."""
    type: str  # "skill", "agent", or "graph"
    name: str  # Name of the skill, agent, or graph
    reason: str  # Brief explanation for the routing decision
    confidence: float = 0.9  # Confidence score (0.0-1.0)
    fallback: bool = False  # True if this is a fallback to default
    classification: str = None  # Original classification (GENERAL, CODE, IMAGE, etc.)


def _load_route_map() -> Tuple[Dict[str, Tuple[str, str]], str, str]:
    """Load route map from YAML configuration.

    Returns:
        Tuple of (route_map dict, execution mode, default route).
    """
    config = load_routes_config()

    mode = config.get("mode", "agent")
    default_route = config.get("default_route", "GENERAL")
    routes = config.get("routes", {})

    route_map = {}
    for classification, route_config in routes.items():
        # Determine handler based on mode
        if mode == "graph" and "graph" in route_config:
            handler_type = "graph"
            handler_name = route_config["graph"]["name"]
        elif "agent" in route_config:
            handler_type = "agent"
            handler_name = route_config["agent"]["name"]
        else:
            # Fallback to general agent
            handler_type = "agent"
            handler_name = "general"
            logger.warning(f"No handler configured for {classification}, using default")

        route_map[classification] = (handler_type, handler_name)

    # Ensure we have at least the default routes if config is empty
    if not route_map:
        route_map = {
            "GENERAL": ("agent", "general"),
            "RESEARCH": ("agent", "deep_research"),
            "CODE": ("agent", "agentic_code"),
            "BRAINDUMP": ("agent", "braindump"),
        }
        logger.warning("Using hardcoded routes - config not loaded")

    return route_map, mode, default_route


# Load routes from configuration
ROUTE_MAP, EXECUTION_MODE, DEFAULT_ROUTE = _load_route_map()


class Router:
    """
    Routes input to one of 5 classifications using LLM.

    Uses a simple plain-text response format for reliable parsing.
    The smaller routing table (5 options vs 40+) allows room for
    full file_context without overwhelming the router model.

    Uses VRAMOrchestrator.get_model() with additional_args=None to
    disable thinking for fast, deterministic classification.

    Routes are loaded from app/config/routes.yaml. Set mode to "graph"
    to use graph-based multi-agent workflows instead of direct agents.

    Example:
        router = Router(config, vram_orchestrator)
        result = await router.route("Research quantum computing advances", context)
        # result.type = "agent", result.name = "deep_research"
        # Or if mode=graph: result.type = "graph", result.name = "research_graph"
    """

    ROUTING_PROMPT = """Classify the request into exactly ONE category.

CRITICAL RULES (apply first):
- Look at USER'S INTENT in the text, not just attachment presence
- Analysis intent + attachment = GENERAL (or CODE if technical)
  Keywords: "what is", "describe", "explain", "OCR", "read", "analyze", "summarize"
- Generation intent = IMAGE (with or without reference attachment)
  Keywords: "generate", "create", "draw", "make an image", "produce", "render", "similar to this"
- No text + attachment = GENERAL (analyze by default)
- IMAGE is for creating NEW images (can use attachment as reference)

CATEGORIES:
GENERAL - Chat, Q&A, explanations, analyzing files/images
  ✓ "What does this image show?"
  ✓ "Summarize this document"
  ✓ "Explain quantum computing"
  ✗ NOT: creating new images

CODE - Writing, debugging, building code
  ✓ "Write a Python function"
  ✓ "Fix this code" (with or without screenshot)
  ✓ "Debug this error from screenshot"

RESEARCH - Deep research needing many web sources
  ✓ "Research Bitcoin regulation history"
  ✓ "Find all papers on transformer architecture"

BRAINDUMP - Thought capture, journaling, idea organization
  ✓ "Let me dump my thoughts"
  ✓ "Organize these ideas"

IMAGE - Generate NEW images (can use attachment as reference)
  ✓ "Generate image of a sunset"
  ✓ "Create picture of a cat"
  ✓ "Generate something similar to this" + attachment
  ✓ "Make this in watercolor style" + attachment
  ✗ NOT: "What's in this image?" (= GENERAL)
  ✗ NOT: "OCR this screenshot" (= GENERAL)
  ✗ NOT: "Analyze this diagram" (= GENERAL)

{file_context_line}REQUEST: {user_input}

Output ONLY the category name: GENERAL, CODE, RESEARCH, BRAINDUMP, or IMAGE"""

    def __init__(
        self,
        config: Config,
        vram_orchestrator: "IVRAMOrchestrator",
        graph_registry: Optional["IGraphRegistry"] = None,
    ):
        """
        Initialize the router.

        Args:
            config: Application configuration.
            vram_orchestrator: VRAM orchestrator for model access.
            graph_registry: Optional graph registry for graph mode validation.
        """
        self._config = config
        self._orchestrator = vram_orchestrator
        self._graph_registry = graph_registry
        self._mode = EXECUTION_MODE
        self._default_route = DEFAULT_ROUTE

        logger.info(f"Router initialized with mode={self._mode}, default={self._default_route}")

    async def route(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        file_context: Optional[str] = None,
        has_attachments: bool = False,
    ) -> RoutingResult:
        """
        Route user input to appropriate handler.

        Args:
            user_input: The user's message/request.
            context: Optional context dict (interface, user_id, etc.).
            file_context: Optional extracted file content (full, no truncation).
            has_attachments: Whether user attached files (signals analysis vs generation).

        Returns:
            RoutingResult indicating which skill/agent to use.
        """
        # Build file context line for prompt (only if files present)
        # Use explicit signal to help smaller models apply CRITICAL RULES
        file_context_line = ""
        if file_context:
            file_context_line = f"[USER ATTACHED FILE]\nContent: {file_context}\n"

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
            return self._resolve_graph_fallback(route_str)

        # Try to extract route name from response (in case of extra text)
        for classification in ROUTE_MAP.keys():
            if classification in route_str:
                logger.warning(f"Extracted route from response: {classification}")
                result = self._resolve_graph_fallback(classification)
                result.confidence = 0.7
                result.reason = f"Extracted {classification} from response"
                return result

        # Fallback
        logger.warning(
            f"Unknown classification: '{route_str}', defaulting to {self._default_route}"
        )
        return self._fallback_result()

    def _fallback_result(self) -> RoutingResult:
        """
        Create a fallback result when routing fails.

        Returns:
            Fallback RoutingResult using default route from config.
        """
        if self._default_route in ROUTE_MAP:
            route_type, route_name = ROUTE_MAP[self._default_route]
        else:
            # Ultimate fallback
            route_type, route_name = "agent", "general"

        return RoutingResult(
            type=route_type,
            name=route_name,
            reason="Fallback due to routing failure",
            confidence=0.5,
            fallback=True,
            classification=self._default_route,
        )

    def _resolve_graph_fallback(self, classification: str) -> RoutingResult:
        """
        Resolve routing when graph mode is enabled but graph doesn't exist.

        Falls back to agent mode if the graph isn't registered.

        Args:
            classification: The classification name.

        Returns:
            RoutingResult using agent fallback if graph not available.
        """
        route_type, route_name = ROUTE_MAP.get(classification, ("agent", "general"))

        # If graph mode and we have a graph registry, verify graph exists
        if route_type == "graph" and self._graph_registry:
            graph = self._graph_registry.get(route_name)
            if graph is None:
                # Graph not registered, fall back to agent
                config = load_routes_config()
                routes = config.get("routes", {})
                route_config = routes.get(classification, {})

                if "agent" in route_config:
                    route_name = route_config["agent"]["name"]
                    route_type = "agent"
                    logger.warning(
                        f"Graph '{route_name}' not registered, falling back to agent"
                    )
                else:
                    route_type = "agent"
                    route_name = "general"
                    logger.warning(
                        f"No agent fallback for {classification}, using general"
                    )

        return RoutingResult(
            type=route_type,
            name=route_name,
            reason=f"Classified as {classification}",
            confidence=0.9,
            classification=classification,
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
