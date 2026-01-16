"""General Agent implementation.

Handles general queries, Q&A, and tasks. Uses the skill_gateway
tool to access specialized instructions on demand.

This implements the "guidebook" pattern where skills are chapters
the agent can read for specialized guidance.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class GeneralAgent(BaseAgent):
    """
    General-purpose agent with skill gateway access.

    Uses the skill_gateway tool to dynamically access specialized
    instructions for tasks like drafting emails, creating diagrams,
    analyzing documents, and more.

    Example:
        agent = GeneralAgent(
            vram_orchestrator=orchestrator,
            tools=[skill_gateway],
            config={"model": "magistral:24b"}
        )
        result = await agent.execute("Draft an email to my team", context)
    """

    name = "general"
    category = "general"
    tools = ["skill_gateway"]
    # Prompt loaded from app/prompts/agents/general.prompt

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the general agent."""
        config = config or {}
        # Override defaults for general assistant
        config.setdefault("temperature", 0.3)  # Slightly creative for helpfulness
        config.setdefault("model_role", "general")  # Use general_model from profile
        super().__init__(vram_orchestrator, tools, prompt_composer, config)

    async def execute(
        self,
        input: str,
        context: ExecutionContext,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Process user input with optional skill guidance.

        Args:
            input: User's question or request.
            context: Execution context with user profile and interface info.
            stream_handler: Optional handler for streaming to WebSocket.

        Returns:
            AgentResult with response content.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )
