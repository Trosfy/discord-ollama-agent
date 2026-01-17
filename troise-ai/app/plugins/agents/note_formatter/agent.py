"""Note Formatter Agent implementation.

Formats organized thoughts for Obsidian vault storage.
Part of the BRAINDUMP graph workflow.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class NoteFormatterAgent(BaseAgent):
    """
    Note formatting agent for vault storage.

    Takes organized and connected thoughts and formats them
    as proper Obsidian markdown notes with frontmatter,
    tags, and links.

    Example:
        agent = NoteFormatterAgent(orchestrator, tools, composer)
        result = await agent.execute(connected_thoughts, context)
        # result.content contains formatted note
    """

    name = "note_formatter"
    category = "braindump"
    # Uses brain_search for formatting patterns, save_note for storage
    tools = ["brain_search", "save_note"]

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the note formatter agent."""
        config = config or {}
        config.setdefault("temperature", 0.1)  # Deterministic formatting
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
        Format thoughts as vault note.

        Args:
            input: Connected thoughts to format.
            context: Execution context.
            stream_handler: Optional handler for streaming.

        Returns:
            AgentResult with formatted note.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )
