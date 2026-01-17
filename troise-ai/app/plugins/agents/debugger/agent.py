"""Debugger Agent implementation.

Fixes issues identified by code review or test failures.
Part of the CODE graph workflow.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class DebuggerAgent(BaseAgent):
    """
    Debugging agent that fixes code issues.

    Takes review findings or test failures and produces
    corrected code. The corrected code loops back to
    code_reviewer for re-validation.

    Tools include run_code for verifying fixes locally.

    Example:
        agent = DebuggerAgent(orchestrator, tools, composer)
        result = await agent.execute(
            "Fix these issues: " + review_findings,
            context
        )
        # result.content contains corrected code
    """

    name = "debugger"
    category = "code"
    # Uses brain_search for patterns, read_file for context, run_code for testing
    tools = ["brain_search", "read_file", "run_code"]

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the debugger agent."""
        config = config or {}
        config.setdefault("temperature", 0.2)  # Low creativity for fixes
        config.setdefault("max_tokens", 4096)
        config.setdefault("model_role", "code")  # Use code model
        super().__init__(vram_orchestrator, tools, prompt_composer, config)

    async def execute(
        self,
        input: str,
        context: ExecutionContext,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Fix issues in the provided code.

        Args:
            input: Issue description and code to fix.
            context: Execution context.
            stream_handler: Optional handler for streaming.

        Returns:
            AgentResult with corrected code.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )
