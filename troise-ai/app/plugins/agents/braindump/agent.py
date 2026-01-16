"""Braindump Agent implementation.

Takes unstructured thoughts and organizes them into notes,
using the knowledge base for context and deduplication.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class BraindumpAgent(BaseAgent):
    """
    Agent for processing unstructured thoughts into organized notes.

    Uses Strands SDK for the tool loop. Tools include:
    - brain_search: Find related existing notes
    - brain_fetch: Get full content of a note
    - save_note: Save organized notes to vault
    - ask_user: Clarify unclear points

    Example:
        agent = BraindumpAgent(
            vram_orchestrator=orchestrator,
            tools=[brain_search, brain_fetch, save_note, ask_user],
            config={"model": "magistral:24b"}
        )
        result = await agent.execute("random thoughts about project X", context)
    """

    name = "braindump"
    category = "productivity"
    tools = ["brain_search", "brain_fetch", "save_note", "ask_user"]
    # Prompt loaded from app/prompts/agents/braindump.prompt

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the braindump agent."""
        config = config or {}
        # Override defaults for braindump
        config.setdefault("model_role", "braindump")  # Use braindump_model from profile
        config.setdefault("temperature", 0.2)  # Low for consistent organization
        super().__init__(vram_orchestrator, tools, prompt_composer, config)

    async def execute(
        self,
        input: str,
        context: ExecutionContext,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Process braindump input into organized notes.

        Args:
            input: User's unstructured thoughts.
            context: Execution context with user profile and interface info.
            stream_handler: Optional handler for streaming to WebSocket.

        Returns:
            AgentResult with summary of created notes.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )
