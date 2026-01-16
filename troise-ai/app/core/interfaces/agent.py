"""IAgent interface - multi-step operations with tools."""
from typing import Protocol, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from ..context import ExecutionContext
    from ..streaming import AgentStreamHandler


@dataclass
class AgentResult:
    """Result from agent execution."""
    content: str
    tool_calls: List[dict] = field(default_factory=list)
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class IAgent(Protocol):
    """
    Agent - multi-step with tools, loops until done.

    Examples: braindump, agentic-code, deep-research

    Agents are:
    - Multi-step (multiple LLM calls)
    - Tool-enabled (can call tools during execution)
    - State managed by LLM internally (conversation context)
    - Longer running (minutes, not seconds)
    """
    name: str
    category: str
    tools: List[str]  # Tool names to inject

    async def execute(
        self,
        input: str,
        context: "ExecutionContext",
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Run agent loop with tools until completion.

        The model handles internal state and looping via Strands SDK.
        If stream_handler is provided, streams responses to WebSocket.

        Args:
            input: User input to process
            context: Execution context with user profile, interface info
            stream_handler: Optional handler for streaming to WebSocket

        Returns:
            AgentResult with content, tool calls made, and metadata
        """
        ...
