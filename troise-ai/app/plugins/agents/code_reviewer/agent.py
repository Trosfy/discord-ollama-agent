"""Code Reviewer Agent implementation.

Reviews generated code for bugs, style violations, and security issues.
Part of the CODE graph workflow.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class CodeReviewerAgent(BaseAgent):
    """
    Code review agent that validates generated code.

    Reviews code for:
    - Logic errors and bugs
    - Security vulnerabilities
    - Style and convention violations
    - Best practice adherence

    Updates graph state with review findings for potential
    iteration back to debugger.

    Example:
        agent = CodeReviewerAgent(orchestrator, tools, composer)
        result = await agent.execute(generated_code, context)
        # result.content contains review findings
        # Graph state updated with has_issues flag
    """

    name = "code_reviewer"
    category = "code"
    # Uses brain_search for patterns, read_file for context
    tools = ["brain_search", "read_file"]

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the code reviewer agent."""
        config = config or {}
        config.setdefault("temperature", 0.1)  # Deterministic review
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
        Review code and report findings.

        Args:
            input: Code to review from previous node.
            context: Execution context with graph_state.
            stream_handler: Optional handler for streaming.

        Returns:
            AgentResult with review findings.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )
