"""Graph definitions and registry for TROISE AI.

Provides the Graph dataclass for defining multi-agent workflows
and GraphRegistry for discovering and managing graphs.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .interfaces.graph import Edge, IGraph, IGraphNode, END

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class Graph:
    """Immutable graph definition for multi-agent workflows.

    A graph defines a topology of nodes (agents/skills) and edges
    (transitions with optional conditions). The graph executor
    traverses this topology based on runtime state.

    Attributes:
        name: Unique identifier for this graph (e.g., "code_graph").
        domain: Domain for prompt variants ("code", "research", "braindump").
        nodes: Dictionary mapping node names to IGraphNode instances.
        edges: Dictionary mapping node names to lists of outgoing edges.
        entry_node: Name of the first node to execute.
        simple_entry: Alternative entry for simple requests (skip exploration).
        max_loops: Maximum iterations for cyclic graphs before termination.
        description: Human-readable description of the graph.

    Example:
        graph = Graph(
            name="code_graph",
            domain="code",
            nodes={"explorer": explorer_node, "coder": coder_node},
            edges={
                "explorer": [Edge(to="coder")],
                "coder": [Edge(to=END)],
            },
            entry_node="explorer",
        )
    """
    name: str
    domain: str
    nodes: Dict[str, IGraphNode]
    edges: Dict[str, List[Edge]]
    entry_node: str
    simple_entry: Optional[str] = None
    max_loops: int = 3
    description: str = ""
    complexity_indicators: Dict[str, List[str]] = field(default_factory=dict)

    def get_next_node(self, current_node: str, state: "GraphState") -> str:
        """Determine the next node based on current node and state.

        Evaluates edges from current node in order, returning the first
        edge whose condition matches (or unconditional edge).

        Args:
            current_node: Name of the node that just completed.
            state: Current graph state for condition evaluation.

        Returns:
            Name of the next node, or END if no edges match.
        """
        from .interfaces.graph import GraphState

        if current_node not in self.edges:
            logger.warning(f"No edges defined for node '{current_node}', terminating")
            return END

        for edge in self.edges[current_node]:
            if edge.matches(state):
                logger.debug(f"Edge matched: {current_node} -> {edge.to}")
                return edge.to

        # No matching edge - should not happen in well-defined graphs
        logger.warning(f"No matching edge from '{current_node}', terminating")
        return END

    def get_all_tool_names(self) -> List[str]:
        """Get union of all tool names used by all nodes.

        Used to create shared tools for the entire graph execution.

        Returns:
            Deduplicated list of tool names.
        """
        all_tools = set()
        for node in self.nodes.values():
            if hasattr(node, "tools"):
                all_tools.update(node.tools)
            elif hasattr(node, "_agent") and hasattr(node._agent, "tools"):
                all_tools.update(node._agent.tools)
        return list(all_tools)

    def is_complex_request(self, input_text: str) -> bool:
        """Check if input indicates a complex request.

        Used to determine whether to use entry_node or simple_entry.

        Args:
            input_text: User's input text.

        Returns:
            True if the request appears complex.
        """
        complex_indicators = self.complexity_indicators.get("complex", [])
        input_lower = input_text.lower()
        return any(ind in input_lower for ind in complex_indicators)

    def is_trivial_request(self, input_text: str) -> bool:
        """Check if input indicates a trivial request.

        Args:
            input_text: User's input text.

        Returns:
            True if the request appears trivial.
        """
        trivial_indicators = self.complexity_indicators.get("trivial", [])
        input_lower = input_text.lower()
        return any(ind in input_lower for ind in trivial_indicators)

    def get_entry_node(self, input_text: str) -> str:
        """Determine the appropriate entry node based on input complexity.

        Args:
            input_text: User's input text.

        Returns:
            Entry node name (entry_node for complex, simple_entry for trivial).
        """
        if self.simple_entry:
            if self.is_trivial_request(input_text):
                logger.info(f"Trivial request, using simple_entry: {self.simple_entry}")
                return self.simple_entry
            if not self.is_complex_request(input_text):
                # Default to simple entry for non-complex requests
                logger.info(f"Standard request, using simple_entry: {self.simple_entry}")
                return self.simple_entry

        logger.info(f"Complex request, using entry_node: {self.entry_node}")
        return self.entry_node


class GraphRegistry:
    """Registry for discovering and managing graphs.

    Follows the plugin registry pattern - graphs are discovered from
    YAML definitions and registered at startup. Open for extension
    (add new YAML files), closed for modification (no code changes).

    Example:
        registry = GraphRegistry()
        registry.register(code_graph)
        graph = registry.get("code_graph")
    """

    def __init__(self):
        """Initialize empty graph registry."""
        self._graphs: Dict[str, Graph] = {}

    def register(self, graph: Graph) -> None:
        """Register a graph.

        Args:
            graph: Graph instance to register.
        """
        if graph.name in self._graphs:
            logger.warning(f"Overwriting existing graph: {graph.name}")

        self._graphs[graph.name] = graph
        logger.info(f"Registered graph: {graph.name} (domain={graph.domain})")

    def get(self, name: str) -> Optional[Graph]:
        """Get a graph by name.

        Args:
            name: Graph identifier.

        Returns:
            Graph instance or None if not found.
        """
        return self._graphs.get(name)

    def list_graphs(self) -> List[str]:
        """List all registered graph names.

        Returns:
            Sorted list of graph names.
        """
        return sorted(self._graphs.keys())

    def list_by_domain(self, domain: str) -> List[str]:
        """List graphs for a specific domain.

        Args:
            domain: Domain filter ("code", "research", "braindump").

        Returns:
            List of graph names in that domain.
        """
        return [
            name for name, graph in self._graphs.items()
            if graph.domain == domain
        ]

    def clear(self) -> None:
        """Clear all registered graphs (for testing)."""
        self._graphs.clear()
        logger.info("Graph registry cleared")


# Factory function for dependency injection
def create_graph_registry() -> GraphRegistry:
    """Create a GraphRegistry instance.

    Returns:
        New GraphRegistry instance.
    """
    return GraphRegistry()
