"""Graph executor for TROISE AI.

Orchestrates sequential execution of graph nodes with streaming support
and loop detection. Implements the IGraphExecutor protocol.
"""
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .interfaces.graph import (
    GraphState,
    NodeResult,
    GraphResult,
    IGraph,
    END,
)

if TYPE_CHECKING:
    from .context import ExecutionContext
    from .streaming import AgentStreamHandler
    from .tool_factory import ToolFactory

logger = logging.getLogger(__name__)


class GraphStreamHandler:
    """Wraps AgentStreamHandler with graph-level context.

    Emits node transition events to the WebSocket so the frontend
    can display which agent is currently executing.

    Events emitted:
    - graph_node_start: When a node begins execution
    - graph_node_end: When a node completes
    - Standard stream events from agents (with node context added)
    """

    def __init__(
        self,
        base_handler: Optional["AgentStreamHandler"],
        graph_name: str,
    ):
        """Initialize graph stream handler.

        Args:
            base_handler: Underlying stream handler (may be None).
            graph_name: Name of the graph being executed.
        """
        self._base = base_handler
        self._graph_name = graph_name
        self._current_node: Optional[str] = None

    async def start_node(self, node_name: str) -> None:
        """Emit node start event.

        Args:
            node_name: Name of the node starting execution.
        """
        self._current_node = node_name

        if self._base:
            await self._base.stream_event({
                "type": "graph_node_start",
                "graph": self._graph_name,
                "node": node_name,
            })

        logger.debug(f"Graph {self._graph_name}: Starting node '{node_name}'")

    async def stream_event(self, event: Dict[str, Any]) -> None:
        """Forward stream event with node context.

        Args:
            event: Event from agent streaming.
        """
        if self._base:
            # Add node identification to content events
            if "contentBlockDelta" in event:
                event["_graph_node"] = self._current_node
            await self._base.stream_event(event)

    async def end_node(self, node_name: str, result: NodeResult) -> None:
        """Emit node completion event.

        Args:
            node_name: Name of the completed node.
            result: Result from node execution.
        """
        if self._base:
            await self._base.stream_event({
                "type": "graph_node_end",
                "graph": self._graph_name,
                "node": node_name,
                "success": result.success,
            })

        logger.debug(
            f"Graph {self._graph_name}: Node '{node_name}' completed "
            f"(success={result.success})"
        )

    async def finalize(self) -> None:
        """Finalize streaming when graph completes."""
        if self._base:
            await self._base.finalize()


class SwarmStreamHandler:
    """Wraps AgentStreamHandler with swarm-level context.

    Follows the same pattern as GraphStreamHandler (ISP compliance).
    Emits swarm-specific events in the same format as graph events.

    Events emitted:
    - swarm_handoff: When agents transfer control
    - swarm_agent_start: When a swarm agent begins
    - swarm_agent_end: When a swarm agent completes
    """

    def __init__(
        self,
        base_handler: Optional["AgentStreamHandler"],
        swarm_name: str,
    ):
        """Initialize swarm stream handler.

        Args:
            base_handler: Underlying stream handler (may be None).
            swarm_name: Name of the swarm being executed.
        """
        self._base = base_handler
        self._swarm_name = swarm_name
        self._current_agent: Optional[str] = None

    async def on_handoff(self, from_agent: str, to_agent: str) -> None:
        """Emit handoff event when agents transfer control.

        Args:
            from_agent: Source agent name.
            to_agent: Target agent name.
        """
        if self._base:
            await self._base.stream_event({
                "type": "swarm_handoff",
                "swarm": self._swarm_name,
                "from": from_agent,
                "to": to_agent,
            })

        logger.debug(f"Swarm {self._swarm_name}: {from_agent} -> {to_agent}")

    async def start_agent(self, agent_name: str) -> None:
        """Emit agent start event.

        Args:
            agent_name: Name of the agent starting execution.
        """
        self._current_agent = agent_name

        if self._base:
            await self._base.stream_event({
                "type": "swarm_agent_start",
                "swarm": self._swarm_name,
                "agent": agent_name,
            })

        logger.debug(f"Swarm {self._swarm_name}: Starting agent '{agent_name}'")

    async def stream_event(self, event: Dict[str, Any]) -> None:
        """Forward stream event with agent context.

        Args:
            event: Event from agent streaming.
        """
        if self._base:
            if "contentBlockDelta" in event:
                event["_swarm_agent"] = self._current_agent
            await self._base.stream_event(event)

    async def end_agent(self, agent_name: str) -> None:
        """Emit agent completion event.

        Args:
            agent_name: Name of the completed agent.
        """
        if self._base:
            await self._base.stream_event({
                "type": "swarm_agent_end",
                "swarm": self._swarm_name,
                "agent": agent_name,
            })

        logger.debug(f"Swarm {self._swarm_name}: Agent '{agent_name}' completed")


class GraphExecutor:
    """Executes graph nodes sequentially with streaming support.

    Sequential execution ensures thread safety with shared ExecutionContext.
    Parallel node execution is deferred to v2 (requires context isolation).

    Features:
    - Loop detection and termination (max_loops)
    - Cancellation support via context.check_cancelled()
    - Node transition streaming to WebSocket
    - State propagation between nodes

    Example:
        executor = GraphExecutor()
        result = await executor.execute(
            graph=code_graph,
            context=context,
            input_text="Write a REST API",
        )
    """

    async def execute(
        self,
        graph: IGraph,
        context: "ExecutionContext",
        input_text: str,
        stream_handler: Optional["AgentStreamHandler"] = None,
        tool_factory: Optional["ToolFactory"] = None,
    ) -> GraphResult:
        """Execute a graph from entry to END.

        Traverses the graph sequentially, executing each node and
        following edges based on runtime state. Terminates when
        reaching END or exceeding max_loops.

        Args:
            graph: Graph definition to execute.
            context: Execution context with user info, cancellation, etc.
            input_text: Initial user input.
            stream_handler: Optional handler for WebSocket streaming.
            tool_factory: Factory for creating per-agent tools (respects skip_universal_tools).

        Returns:
            GraphResult with all node results and final state.
        """
        # Initialize graph state
        state = GraphState()
        state.set("input", input_text)

        # Set graph domain in context for prompt variant selection
        if hasattr(context, "graph_domain"):
            context.graph_domain = graph.domain

        # Create graph-aware stream handler
        graph_stream = GraphStreamHandler(stream_handler, graph.name)

        # Determine entry point based on complexity
        current_node = graph.get_entry_node(input_text)

        results: List[NodeResult] = []
        loop_count = 0
        visited_counts: Dict[str, int] = {}

        logger.info(
            f"Starting graph '{graph.name}' at node '{current_node}' "
            f"(domain={graph.domain})"
        )

        while current_node != END:
            # Check cancellation
            await context.check_cancelled()

            # Check loop limit
            visited_counts[current_node] = visited_counts.get(current_node, 0) + 1
            if visited_counts[current_node] > graph.max_loops:
                logger.warning(
                    f"Loop limit reached for node '{current_node}' "
                    f"(visited {visited_counts[current_node]} times)"
                )
                # Add error result and terminate
                results.append(NodeResult(
                    node_name=current_node,
                    content=f"Loop limit exceeded (max {graph.max_loops} iterations)",
                    success=False,
                    error="loop_limit_exceeded",
                ))
                break

            # Get node
            if current_node not in graph.nodes:
                logger.error(f"Node '{current_node}' not found in graph")
                results.append(NodeResult(
                    node_name=current_node,
                    content=f"Node '{current_node}' not found",
                    success=False,
                    error="node_not_found",
                ))
                break

            node = graph.nodes[current_node]

            # Emit node start event
            await graph_stream.start_node(current_node)

            # Execute node
            try:
                # Sync collected_sources from context to state for downstream access
                # This allows citation_formatter to access URLs captured by SourceCaptureHook
                if hasattr(context, "collected_sources") and context.collected_sources:
                    state.set("collected_sources", context.collected_sources)

                # Determine input for this node
                # First node gets original input, subsequent nodes get previous output
                node_input = input_text if not results else results[-1].content

                result = await node.execute(
                    state=state,
                    context=context,
                    input_text=node_input,
                    tool_factory=tool_factory,
                )

            except Exception as e:
                logger.error(f"Node '{current_node}' failed: {e}")
                result = NodeResult(
                    node_name=current_node,
                    content=f"Error: {str(e)}",
                    success=False,
                    error=str(e),
                )

            # Record result
            results.append(result)

            # Update state with node outputs
            state.update(result.state_updates)

            # Emit node end event
            await graph_stream.end_node(current_node, result)

            # Handle failure - terminate graph
            if not result.success:
                logger.warning(f"Node '{current_node}' failed, terminating graph")
                break

            # Get next node
            current_node = graph.get_next_node(current_node, state)
            logger.debug(f"Next node: {current_node}")

            loop_count += 1

        # Finalize streaming
        await graph_stream.finalize()

        # Build final result
        final_content = results[-1].content if results else ""

        graph_result = GraphResult(
            graph_name=graph.name,
            domain=graph.domain,
            node_results=results,
            final_state=state,
            final_content=final_content,
        )

        logger.info(
            f"Graph '{graph.name}' completed: "
            f"{len(results)} nodes executed, success={graph_result.success}"
        )

        return graph_result


# Factory function for dependency injection
def create_graph_executor() -> GraphExecutor:
    """Create a GraphExecutor instance.

    Returns:
        New GraphExecutor instance.
    """
    return GraphExecutor()
