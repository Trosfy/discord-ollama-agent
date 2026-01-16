"""Deep Research Agent implementation.

Conducts comprehensive research across web and knowledge base,
synthesizing findings into well-structured reports.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class DeepResearchAgent(BaseAgent):
    """
    Agent for conducting comprehensive multi-source research.

    Uses Strands SDK for the tool loop. Tools include:
    - web_search: Search the web for current information
    - web_fetch: Fetch and read full content from URLs
    - brain_search: Find related existing notes
    - save_note: Save research findings to vault

    Example:
        agent = DeepResearchAgent(
            vram_orchestrator=orchestrator,
            tools=[web_search, web_fetch, brain_search, save_note],
            config={"model": "magistral:24b"}
        )
        result = await agent.execute("Research quantum computing trends", context)
    """

    name = "deep_research"
    category = "research"
    tools = ["web_search", "web_fetch", "brain_search", "save_note"]
    # Prompt loaded from app/prompts/agents/deep_research.prompt

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the deep research agent."""
        config = config or {}
        # Override defaults for research
        config.setdefault("model_role", "research")  # Use research_model from profile
        config.setdefault("temperature", 0.2)  # Lower for factual research
        config.setdefault("thinking_level", "high")  # More reasoning for synthesis
        config.setdefault("max_tokens", 8192)  # Longer for detailed reports
        super().__init__(vram_orchestrator, tools, prompt_composer, config)

    async def execute(
        self,
        input: str,
        context: ExecutionContext,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Conduct deep research on a topic.

        Args:
            input: Research question or topic to investigate.
            context: Execution context with user profile and interface info.
            stream_handler: Optional handler for streaming to WebSocket.

        Returns:
            AgentResult with research findings and report.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )

    def _build_metadata(self, tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build metadata with research-specific tracking."""
        metadata = super()._build_metadata(tool_calls)

        # Add research-specific metrics
        metadata["web_searches"] = len([tc for tc in tool_calls if tc["name"] == "web_search"])
        metadata["brain_searches"] = len([tc for tc in tool_calls if tc["name"] == "brain_search"])

        return metadata
