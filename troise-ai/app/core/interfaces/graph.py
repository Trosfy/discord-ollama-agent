"""Graph interfaces for TROISE AI (Dependency Inversion Principle).

Defines protocols and data structures for graph-based multi-agent workflows.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from ..context import ExecutionContext
    from ..streaming import AgentStreamHandler


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class GraphState:
    """State passed between graph nodes.

    Mutable dictionary-like object that accumulates data as nodes execute.
    Each node can read from and write to the state.
    """
    _data: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from state."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in state."""
        self._data[key] = value

    def update(self, updates: Dict[str, Any]) -> None:
        """Update state with multiple values."""
        if updates:
            self._data.update(updates)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def keys(self) -> List[str]:
        return list(self._data.keys())

    def to_dict(self) -> Dict[str, Any]:
        """Export state as dictionary."""
        return dict(self._data)


@dataclass
class NodeResult:
    """Result from a single graph node execution."""
    node_name: str
    content: str
    success: bool
    state_updates: Dict[str, Any] = field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class GraphResult:
    """Aggregated result from complete graph execution."""
    graph_name: str
    domain: str
    node_results: List[NodeResult]
    final_state: GraphState
    final_content: str  # Last node's content or aggregated

    @property
    def success(self) -> bool:
        """True if all nodes executed successfully."""
        return all(r.success for r in self.node_results)

    @property
    def total_tool_calls(self) -> List[Dict[str, Any]]:
        """Aggregate tool calls from all nodes."""
        calls = []
        for result in self.node_results:
            calls.extend(result.tool_calls)
        return calls

    @property
    def nodes_executed(self) -> List[str]:
        """List of node names that were executed."""
        return [r.node_name for r in self.node_results]


@dataclass
class Edge:
    """An edge in the graph connecting two nodes."""
    to: str  # Target node name (or "END")
    condition: Optional[Callable[[GraphState], bool]] = None

    def matches(self, state: GraphState) -> bool:
        """Check if this edge should be taken given current state."""
        if self.condition is None:
            return True  # Unconditional edge
        return self.condition(state)


# =============================================================================
# Protocols (Interface Segregation Principle)
# =============================================================================


class IGraphNode(Protocol):
    """Protocol for graph nodes (Single Responsibility: Execute one step)."""

    @property
    def name(self) -> str:
        """Unique identifier for this node."""
        ...

    @property
    def streaming(self) -> bool:
        """Whether this node streams output to user (default: True).

        Internal nodes (code_reviewer, debugger) should set this to False
        to prevent internal output (like VERDICT) from leaking to the user.
        """
        ...

    async def execute(
        self,
        state: GraphState,
        context: "ExecutionContext",
        input_text: Optional[str] = None,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> NodeResult:
        """Execute this node.

        Args:
            state: Current graph state (read/write).
            context: Execution context with user info, cancellation, etc.
            input_text: Optional input text (typically for first node).
            stream_handler: Optional handler for WebSocket streaming.

        Returns:
            NodeResult with content, success status, and state updates.
        """
        ...


class IGraphCondition(Protocol):
    """Protocol for complex graph conditions (Single Responsibility: Evaluate)."""

    async def evaluate(self, state: GraphState) -> str:
        """Evaluate condition and return next node name.

        Args:
            state: Current graph state.

        Returns:
            Name of the next node to execute.
        """
        ...


class IGraph(Protocol):
    """Protocol for graph definitions (Immutable topology)."""

    @property
    def name(self) -> str:
        """Graph identifier."""
        ...

    @property
    def domain(self) -> str:
        """Domain for prompt variants ('code', 'research', 'braindump')."""
        ...

    @property
    def nodes(self) -> Dict[str, IGraphNode]:
        """All nodes in the graph."""
        ...

    @property
    def edges(self) -> Dict[str, List[Edge]]:
        """Edge definitions: node_name -> [edges]."""
        ...

    @property
    def entry_node(self) -> str:
        """Name of the entry node."""
        ...

    @property
    def simple_entry(self) -> Optional[str]:
        """Alternative entry node for simple requests (skip exploration)."""
        ...

    @property
    def max_loops(self) -> int:
        """Maximum loop iterations before terminating."""
        ...

    def get_all_tool_names(self) -> List[str]:
        """Get union of all tool names used by all nodes."""
        ...


class IGraphExecutor(Protocol):
    """Protocol for graph execution (Single Responsibility: Orchestrate)."""

    async def execute(
        self,
        graph: IGraph,
        context: "ExecutionContext",
        input_text: str,
        tools: List[Any] = None,
    ) -> GraphResult:
        """Execute a graph from start to END.

        Args:
            graph: Graph definition to execute.
            context: Execution context.
            input_text: Initial user input.
            tools: Pre-created tools to share across nodes.

        Returns:
            GraphResult with all node results and final state.
        """
        ...


class IGraphRegistry(Protocol):
    """Protocol for graph registration and discovery."""

    def register(self, graph: IGraph) -> None:
        """Register a graph."""
        ...

    def get(self, name: str) -> Optional[IGraph]:
        """Get a graph by name."""
        ...

    def list_graphs(self) -> List[str]:
        """List all registered graph names."""
        ...


# =============================================================================
# Constants
# =============================================================================

# Special node name indicating graph termination
END = "END"
