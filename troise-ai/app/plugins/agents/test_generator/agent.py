"""Test Generator Agent implementation.

Creates unit and integration tests for generated code.
Part of the CODE graph workflow.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class TestGeneratorAgent(BaseAgent):
    """
    Test generation agent for code validation.

    Creates appropriate tests based on the code and context:
    - Unit tests for functions/methods
    - Integration tests for APIs
    - Edge case coverage

    Updates graph state with test results for potential
    iteration back to debugger if tests fail.

    Example:
        agent = TestGeneratorAgent(orchestrator, tools, composer)
        result = await agent.execute(code_to_test, context)
        # result.content contains generated tests
    """

    name = "test_generator"
    category = "code"
    # Uses brain_search for patterns, read_file for existing tests
    tools = ["brain_search", "read_file"]

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the test generator agent."""
        config = config or {}
        config.setdefault("temperature", 0.2)  # Low creativity for tests
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
        Generate tests for the provided code.

        Args:
            input: Code to generate tests for.
            context: Execution context.
            stream_handler: Optional handler for streaming.

        Returns:
            AgentResult with generated tests.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )
