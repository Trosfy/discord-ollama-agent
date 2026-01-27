"""Agentic Code Agent implementation.

Handles code generation, modification, and testing workflows
with file I/O and code execution capabilities.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class AgenticCodeAgent(BaseAgent):
    """
    Agent for code generation and modification workflows.

    Uses Strands SDK for pure code generation. No filesystem or knowledge tools -
    the agent focuses solely on generating code based on the user request.

    Output: Code should be provided in properly formatted code blocks.
    Postprocessing will extract file artifacts from the response.

    Example:
        agent = AgenticCodeAgent(
            vram_orchestrator=orchestrator,
            tools=[],
            config={"model": "devstral:24b"}
        )
        result = await agent.execute("Create a REST API for user management", context)
    """

    name = "agentic_code"
    category = "code"
    tools = ["ask_user"]  # No filesystem/knowledge tools - pure code generation
    # Prompt loaded from app/prompts/agents/agentic_code.prompt

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the agentic code agent."""
        config = config or {}
        # Override defaults for code generation
        config.setdefault("model_role", "code")  # Use code_model from profile
        config.setdefault("temperature", 0.2)  # Low for deterministic code
        config.setdefault("max_tokens", 8192)  # Longer for code
        super().__init__(vram_orchestrator, tools, prompt_composer, config)

    async def execute(
        self,
        input: str,
        context: ExecutionContext,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Execute code generation or modification task.

        Args:
            input: Description of the coding task.
            context: Execution context with user profile and interface info.
            stream_handler: Optional handler for streaming to WebSocket.

        Returns:
            AgentResult with generated code and summary.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )

    def _build_metadata(
        self,
        tool_calls: List[Dict[str, Any]],
        token_usage: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build metadata with code-specific tracking."""
        metadata = super()._build_metadata(tool_calls, token_usage)

        # Add code-specific metrics
        code_runs = [tc for tc in tool_calls if tc["name"] == "run_code"]
        metadata["code_executions"] = len(code_runs)

        return metadata
