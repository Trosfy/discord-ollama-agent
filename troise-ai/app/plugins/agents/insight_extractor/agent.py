"""Insight Extractor Agent implementation.

Extracts actionable insights from richly connected thoughts.
Part of the BRAINDUMP graph workflow.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class InsightExtractorAgent(BaseAgent):
    """
    Insight extraction agent for deep analysis.

    When thoughts have rich connections to existing knowledge,
    this agent extracts actionable insights, patterns, and
    potential next steps.

    Example:
        agent = InsightExtractorAgent(orchestrator, tools, composer)
        result = await agent.execute(richly_connected_thoughts, context)
        # result.content contains extracted insights
    """

    name = "insight_extractor"
    category = "braindump"
    # Uses brain_search for pattern finding
    tools = ["brain_search"]

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the insight extractor agent."""
        config = config or {}
        config.setdefault("temperature", 0.3)  # Some creativity for insights
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
        Extract insights from connected thoughts.

        Args:
            input: Richly connected thoughts to analyze.
            context: Execution context.
            stream_handler: Optional handler for streaming.

        Returns:
            AgentResult with extracted insights.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )
