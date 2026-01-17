"""Thought Organizer Agent implementation.

Structures raw thoughts into categories and themes.
Part of the BRAINDUMP graph workflow.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class ThoughtOrganizerAgent(BaseAgent):
    """
    Thought organization agent for braindumps.

    Takes raw, unstructured thoughts and organizes them into
    coherent categories, themes, and action items.

    Example:
        agent = ThoughtOrganizerAgent(orchestrator, tools, composer)
        result = await agent.execute(raw_braindump, context)
        # result.content contains organized thoughts
    """

    name = "thought_organizer"
    category = "braindump"
    # Uses brain_search for existing categories
    tools = ["brain_search"]

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the thought organizer agent."""
        config = config or {}
        config.setdefault("temperature", 0.3)  # Some creativity for organization
        config.setdefault("max_tokens", 4096)
        config.setdefault("model_role", "braindump")  # Use braindump model
        super().__init__(vram_orchestrator, tools, prompt_composer, config)

    async def execute(
        self,
        input: str,
        context: ExecutionContext,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Organize raw thoughts into structure.

        Args:
            input: Raw braindump text.
            context: Execution context.
            stream_handler: Optional handler for streaming.

        Returns:
            AgentResult with organized thoughts.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )
