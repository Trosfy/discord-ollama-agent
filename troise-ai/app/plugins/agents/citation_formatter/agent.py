"""Citation Formatter Agent implementation.

Formats references and citations properly.
Part of the RESEARCH graph workflow.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class CitationFormatterAgent(BaseAgent):
    """
    Citation formatting agent for research outputs.

    Takes synthesized research and adds proper citations,
    formatting references according to standard formats.

    Example:
        agent = CitationFormatterAgent(orchestrator, tools, composer)
        result = await agent.execute(synthesized_research, context)
        # result.content contains properly cited research
    """

    name = "citation_formatter"
    category = "research"
    # Uses brain_search for citation style preferences
    tools = ["brain_search"]

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the citation formatter agent."""
        config = config or {}
        config.setdefault("temperature", 0.1)  # Deterministic formatting
        config.setdefault("max_tokens", 8192)  # Match synthesis length
        config.setdefault("model_role", "general")  # Use general model
        super().__init__(vram_orchestrator, tools, prompt_composer, config)

    async def execute(
        self,
        input: str,
        context: ExecutionContext,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Format citations in the research output.

        Args:
            input: Synthesized research to format.
            context: Execution context.
            stream_handler: Optional handler for streaming.

        Returns:
            AgentResult with properly cited output.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )
