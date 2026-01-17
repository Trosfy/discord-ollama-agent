"""Fact Checker Agent implementation.

Validates claims against authoritative sources.
Part of the RESEARCH graph workflow.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class FactCheckerAgent(BaseAgent):
    """
    Fact verification agent for research accuracy.

    Validates claims and information gathered during research
    against authoritative sources. Flags unverified claims
    for additional research.

    Example:
        agent = FactCheckerAgent(orchestrator, tools, composer)
        result = await agent.execute(research_findings, context)
        # result.content contains verification report
    """

    name = "fact_checker"
    category = "research"
    # Uses web tools for verification, brain_search for cross-reference
    tools = ["web_search", "web_fetch", "brain_search"]

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the fact checker agent."""
        config = config or {}
        config.setdefault("temperature", 0.1)  # Highly factual
        config.setdefault("max_tokens", 4096)
        config.setdefault("model_role", "research")  # Use research model
        super().__init__(vram_orchestrator, tools, prompt_composer, config)

    async def execute(
        self,
        input: str,
        context: ExecutionContext,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Verify claims and facts in the research.

        Args:
            input: Research findings to verify.
            context: Execution context.
            stream_handler: Optional handler for streaming.

        Returns:
            AgentResult with verification report.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )
