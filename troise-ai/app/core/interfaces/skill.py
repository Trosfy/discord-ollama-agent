"""ISkill interface - atomic, single LLM call operations."""
from typing import Protocol, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from ..context import ExecutionContext


@dataclass
class SkillResult:
    """Result from skill execution."""
    content: str
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ISkill(Protocol):
    """
    Atomic skill - single LLM call, no tools.

    Examples: summarize, translate, extract, explain

    Skills are:
    - Stateless (no memory between calls)
    - Single LLM invocation
    - No tool calling capability
    - Fast (seconds, not minutes)
    """
    name: str
    category: str

    async def execute(
        self,
        input: str,
        context: "ExecutionContext"
    ) -> SkillResult:
        """
        Execute the skill with a single LLM call.

        Args:
            input: User input to process
            context: Execution context with user profile, interface info

        Returns:
            SkillResult with content and optional metadata
        """
        ...
