"""Task Planner Agent implementation.

Decomposes complex coding tasks into structured implementation steps.
Part of the CODE graph workflow.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class TaskPlannerAgent(BaseAgent):
    """
    Task decomposition agent for complex coding requests.

    Takes exploration findings and the user's request to produce
    a structured implementation plan with clear steps.

    Example:
        agent = TaskPlannerAgent(orchestrator, tools, composer)
        result = await agent.execute(
            "Build REST API with auth: " + exploration_findings,
            context
        )
    """

    name = "task_planner"
    category = "code"
    # Uses brain_search to find relevant patterns and examples
    tools = ["brain_search"]

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the task planner agent."""
        config = config or {}
        config.setdefault("temperature", 0.3)  # Balanced for structured planning
        config.setdefault("max_tokens", 4096)
        config.setdefault("model_role", "code")  # Use code model for technical planning
        super().__init__(vram_orchestrator, tools, prompt_composer, config)

    async def execute(
        self,
        input: str,
        context: ExecutionContext,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Decompose the task into implementation steps.

        Args:
            input: User request with exploration context.
            context: Execution context.
            stream_handler: Optional handler for streaming.

        Returns:
            AgentResult with structured implementation plan.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )
