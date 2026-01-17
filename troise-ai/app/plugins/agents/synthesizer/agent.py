"""Synthesizer Agent implementation.

Combines research findings from multiple sources into coherent analysis.
Part of the RESEARCH graph workflow.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class SynthesizerAgent(BaseAgent):
    """
    Research synthesis agent that combines findings.

    Takes verified research from multiple sources and
    synthesizes into a coherent, well-organized analysis.

    Example:
        agent = SynthesizerAgent(orchestrator, tools, composer)
        result = await agent.execute(verified_research, context)
        # result.content contains synthesized analysis
    """

    name = "synthesizer"
    category = "research"
    # Uses brain_search for additional context
    tools = ["brain_search"]

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the synthesizer agent."""
        config = config or {}
        config.setdefault("temperature", 0.3)  # Some creativity for synthesis
        config.setdefault("max_tokens", 8192)  # Longer output for synthesis
        config.setdefault("model_role", "research")  # Use research model
        super().__init__(vram_orchestrator, tools, prompt_composer, config)

    async def execute(
        self,
        input: str,
        context: ExecutionContext,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Synthesize research findings.

        Args:
            input: Verified research to synthesize.
            context: Execution context.
            stream_handler: Optional handler for streaming.

        Returns:
            AgentResult with synthesized analysis.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )
