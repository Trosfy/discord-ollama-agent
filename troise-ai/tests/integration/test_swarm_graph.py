"""Integration tests for graphs with swarm nodes.

Tests end-to-end execution of graphs containing swarm nodes
(Phase 2: Strands Swarm Integration).
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from typing import Any, Dict, List, Optional

from app.core.interfaces.graph import GraphState, NodeResult, GraphResult
from app.core.graph_nodes import (
    SwarmNode,
    SwarmAgentConfig,
    QualitySwarmNode,
    ResearchSwarmNode,
)
from app.core.graph_executor import GraphExecutor, SwarmStreamHandler
from app.graphs.loader import GraphLoader, SPECIALIZED_SWARM_NODES


# =============================================================================
# Mock Infrastructure
# =============================================================================


def create_mock_swarm(response: str = "swarm response") -> MagicMock:
    """Create a mock Strands Swarm with invoke_async."""
    mock_swarm = MagicMock()
    mock_swarm.invoke_async = AsyncMock(return_value=response)
    return mock_swarm


def create_agent_configs(names: List[str], model_role: str = "research") -> List[SwarmAgentConfig]:
    """Create SwarmAgentConfig objects for testing."""
    return [
        SwarmAgentConfig(
            name=name,
            model_id=f"test-model-{name}",
            model_role=model_role,
            temperature=0.7,
            max_tokens=4096,
            tools=["tool_a", "tool_b"],
        )
        for name in names
    ]


class MockAgentNode:
    """Mock agent node for graph integration tests."""

    def __init__(self, name: str, response: str = "agent response"):
        self.name = name
        self._response = response
        self.tools = []

    async def execute(
        self,
        state: GraphState,
        context: Any,
        input_text: Optional[str] = None,
        tool_factory: Any = None,
    ) -> NodeResult:
        return NodeResult(
            node_name=self.name,
            content=self._response,
            success=True,
            state_updates={f"{self.name}_output": self._response},
        )


class MockGraph:
    """Mock graph for testing executor with swarm nodes."""

    def __init__(
        self,
        name: str,
        nodes: Dict[str, Any],
        edges: Dict[str, List[Dict]],
        entry_node: str,
    ):
        self.name = name
        self.domain = "test"
        self.nodes = nodes
        self.edges = edges
        self._entry_node = entry_node
        self.max_loops = 3

    def get_entry_node(self, input_text: str) -> str:
        return self._entry_node

    def get_next_node(self, current_node: str, state: GraphState) -> str:
        """Get next node based on edges."""
        if current_node not in self.edges:
            return "END"

        for edge in self.edges[current_node]:
            # Check condition if present
            if "condition" in edge:
                condition_fn = edge["condition"]
                if condition_fn and not condition_fn(state):
                    continue
            return edge["to"]

        return "END"


# =============================================================================
# SwarmStreamHandler Tests
# =============================================================================


class TestSwarmStreamHandler:
    """Tests for SwarmStreamHandler."""

    @pytest.fixture
    def mock_base_handler(self):
        """Create mock base handler."""
        handler = MagicMock()
        handler.stream_event = AsyncMock()
        return handler

    @pytest.mark.asyncio
    async def test_on_handoff_emits_event(self, mock_base_handler):
        """on_handoff should emit swarm_handoff event."""
        handler = SwarmStreamHandler(mock_base_handler, "test_swarm")

        await handler.on_handoff("agent1", "agent2")

        mock_base_handler.stream_event.assert_called_once()
        event = mock_base_handler.stream_event.call_args[0][0]
        assert event["type"] == "swarm_handoff"
        assert event["swarm"] == "test_swarm"
        assert event["from"] == "agent1"
        assert event["to"] == "agent2"

    @pytest.mark.asyncio
    async def test_start_agent_emits_event(self, mock_base_handler):
        """start_agent should emit swarm_agent_start event."""
        handler = SwarmStreamHandler(mock_base_handler, "test_swarm")

        await handler.start_agent("my_agent")

        mock_base_handler.stream_event.assert_called_once()
        event = mock_base_handler.stream_event.call_args[0][0]
        assert event["type"] == "swarm_agent_start"
        assert event["agent"] == "my_agent"

    @pytest.mark.asyncio
    async def test_end_agent_emits_event(self, mock_base_handler):
        """end_agent should emit swarm_agent_end event."""
        handler = SwarmStreamHandler(mock_base_handler, "test_swarm")

        await handler.end_agent("my_agent")

        mock_base_handler.stream_event.assert_called_once()
        event = mock_base_handler.stream_event.call_args[0][0]
        assert event["type"] == "swarm_agent_end"
        assert event["agent"] == "my_agent"

    @pytest.mark.asyncio
    async def test_stream_event_adds_agent_context(self, mock_base_handler):
        """stream_event should add current agent to content events."""
        handler = SwarmStreamHandler(mock_base_handler, "test_swarm")
        handler._current_agent = "active_agent"

        await handler.stream_event({"contentBlockDelta": {"text": "chunk"}})

        call_event = mock_base_handler.stream_event.call_args[0][0]
        assert call_event["_swarm_agent"] == "active_agent"

    @pytest.mark.asyncio
    async def test_handles_none_base_handler(self):
        """Should handle None base handler gracefully."""
        handler = SwarmStreamHandler(None, "test_swarm")

        # Should not raise
        await handler.on_handoff("a", "b")
        await handler.start_agent("a")
        await handler.end_agent("a")
        await handler.stream_event({"test": "event"})


# =============================================================================
# GraphExecutor with Swarm Node Tests
# =============================================================================


class TestGraphExecutorWithSwarm:
    """Tests for GraphExecutor executing graphs with swarm nodes."""

    @pytest.fixture
    def mock_vram_orchestrator(self):
        """Create mock VRAMOrchestrator."""
        orchestrator = MagicMock()
        mock_model = MagicMock()
        orchestrator.get_model = AsyncMock(return_value=mock_model)
        return orchestrator

    @pytest.fixture
    def mock_prompt_composer(self):
        """Create mock PromptComposer."""
        composer = MagicMock()
        composer.compose_agent_prompt = MagicMock(return_value="Test system prompt")
        return composer

    @pytest.fixture
    def mock_tool_factory(self):
        """Create mock tool factory."""
        factory = MagicMock()
        factory.create_tools = MagicMock(return_value=[])
        return factory

    @pytest.fixture
    def mock_context(self, mock_vram_orchestrator, mock_prompt_composer, mock_tool_factory):
        """Create mock execution context with required dependencies."""
        context = MagicMock()
        context.check_cancelled = AsyncMock()
        context.graph_domain = "code"
        context.interface = "test"
        context.user_profile = MagicMock()
        context.vram_orchestrator = mock_vram_orchestrator
        context.prompt_composer = mock_prompt_composer
        context.tool_factory = mock_tool_factory
        return context

    @pytest.fixture
    def executor(self):
        """Create graph executor."""
        return GraphExecutor()

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_executes_swarm_node_in_graph(
        self, mock_strands_agent_cls, mock_swarm_cls, executor, mock_context
    ):
        """Executor should execute swarm nodes like agent nodes."""
        # Setup mock swarm with invoke_async
        mock_swarm = create_mock_swarm("Code reviewed, all tests passed")
        mock_swarm_cls.return_value = mock_swarm

        # Create swarm node with new API
        agent_configs = create_agent_configs(["code_reviewer", "debugger"], model_role="code")
        swarm_node = QualitySwarmNode(
            agent_configs=agent_configs,
            entry_point_name="code_reviewer",
            name="quality_swarm",
        )

        # Create simple graph: entry -> swarm -> END
        entry_node = MockAgentNode("entry", "initial code")
        graph = MockGraph(
            name="test_graph",
            nodes={
                "entry": entry_node,
                "quality_swarm": swarm_node,
            },
            edges={
                "entry": [{"to": "quality_swarm"}],
                "quality_swarm": [{"to": "END"}],
            },
            entry_node="entry",
        )

        result = await executor.execute(
            graph=graph,
            context=mock_context,
            input_text="test code",
        )

        assert result.success is True
        assert len(result.node_results) == 2
        assert result.node_results[0].node_name == "entry"
        assert result.node_results[1].node_name == "quality_swarm"

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_swarm_node_state_flows_to_conditions(
        self, mock_strands_agent_cls, mock_swarm_cls, executor, mock_context
    ):
        """State from swarm node should be available for edge conditions."""
        # Swarm that returns response containing "passed"
        mock_swarm = create_mock_swarm("All good, passed review")
        mock_swarm_cls.return_value = mock_swarm

        # Create swarm node with new API
        agent_configs = create_agent_configs(["code_reviewer"], model_role="code")
        swarm_node = QualitySwarmNode(
            agent_configs=agent_configs,
            entry_point_name="code_reviewer",
            name="quality_swarm",
        )

        # Node after successful review
        success_node = MockAgentNode("success", "success path")
        failure_node = MockAgentNode("failure", "failure path")

        def review_passed(state):
            return state.get("review_passed", False)

        def review_failed(state):
            return not state.get("review_passed", True)

        graph = MockGraph(
            name="test_graph",
            nodes={
                "quality_swarm": swarm_node,
                "success": success_node,
                "failure": failure_node,
            },
            edges={
                "quality_swarm": [
                    {"to": "success", "condition": review_passed},
                    {"to": "failure", "condition": review_failed},
                ],
                "success": [{"to": "END"}],
                "failure": [{"to": "END"}],
            },
            entry_node="quality_swarm",
        )

        result = await executor.execute(
            graph=graph,
            context=mock_context,
            input_text="test input",
        )

        assert result.success is True
        # Should have taken success path
        node_names = [r.node_name for r in result.node_results]
        assert "success" in node_names
        assert "failure" not in node_names

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_swarm_node_error_terminates_graph(
        self, mock_strands_agent_cls, mock_swarm_cls, executor, mock_context
    ):
        """Swarm node errors should terminate graph execution."""
        # Create failing swarm
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(side_effect=Exception("Swarm crashed"))
        mock_swarm_cls.return_value = mock_swarm

        # Create swarm node with new API
        agent_configs = create_agent_configs(["agent1"])
        swarm_node = SwarmNode(
            agent_configs=agent_configs,
            entry_point_name="agent1",
            name="failing_swarm",
        )

        after_node = MockAgentNode("after", "should not reach")

        graph = MockGraph(
            name="test_graph",
            nodes={
                "failing_swarm": swarm_node,
                "after": after_node,
            },
            edges={
                "failing_swarm": [{"to": "after"}],
                "after": [{"to": "END"}],
            },
            entry_node="failing_swarm",
        )

        result = await executor.execute(
            graph=graph,
            context=mock_context,
            input_text="test",
        )

        assert result.success is False
        assert len(result.node_results) == 1
        assert result.node_results[0].node_name == "failing_swarm"


# =============================================================================
# GraphLoader Swarm Integration Tests
# =============================================================================


class TestGraphLoaderSwarmIntegration:
    """Tests for GraphLoader swarm node building."""

    def test_specialized_swarm_nodes_registered(self):
        """SPECIALIZED_SWARM_NODES should contain expected mappings."""
        assert "quality_swarm" in SPECIALIZED_SWARM_NODES
        assert "research_swarm" in SPECIALIZED_SWARM_NODES
        assert SPECIALIZED_SWARM_NODES["quality_swarm"] is QualitySwarmNode
        assert SPECIALIZED_SWARM_NODES["research_swarm"] is ResearchSwarmNode

    @pytest.mark.asyncio
    async def test_build_swarm_node_creates_correct_type(self):
        """_build_swarm_node should use SPECIALIZED_SWARM_NODES for type lookup."""
        # This test verifies the OCP-compliant extension mechanism
        # Adding new swarm types only requires updating SPECIALIZED_SWARM_NODES

        # Mock container and conditions
        mock_container = MagicMock()
        mock_conditions = {}

        # Create loader
        loader = GraphLoader(mock_container, mock_conditions)

        # Mock agent resolution to return mock agents
        mock_agent = MagicMock()
        mock_agent.name = "code_reviewer"
        mock_agent._prompt_composer = MagicMock()
        mock_agent._prompt_composer.compose_agent_prompt.return_value = "test prompt"
        loader._resolve_agent = MagicMock(return_value=mock_agent)

        # Mock Strands imports at the point they're called (inside _build_swarm_node)
        with patch.dict("sys.modules", {
            "strands": MagicMock(),
            "strands.multiagent": MagicMock(),
        }):
            import sys
            mock_strands = sys.modules["strands"]
            mock_multiagent = sys.modules["strands.multiagent"]

            # Configure mock Agent class
            mock_strands_agent = MagicMock()
            mock_strands_agent.name = "mock_agent"
            mock_strands.Agent = MagicMock(return_value=mock_strands_agent)

            # Configure mock Swarm class
            mock_swarm_instance = MagicMock()
            mock_swarm_instance.agents = [mock_strands_agent]
            mock_multiagent.Swarm = MagicMock(return_value=mock_swarm_instance)

            # Build quality_swarm node
            node_def = {
                "type": "swarm",
                "agents": ["code_reviewer"],
                "entry_point": "code_reviewer",
            }

            # This should return QualitySwarmNode due to SPECIALIZED_SWARM_NODES lookup
            node = loader._build_swarm_node("quality_swarm", node_def)
            assert isinstance(node, QualitySwarmNode)


# =============================================================================
# Research Swarm Integration Tests
# =============================================================================


class TestResearchSwarmGraph:
    """Tests for research graph with swarm node."""

    @pytest.fixture
    def mock_vram_orchestrator(self):
        """Create mock VRAMOrchestrator."""
        orchestrator = MagicMock()
        mock_model = MagicMock()
        orchestrator.get_model = AsyncMock(return_value=mock_model)
        return orchestrator

    @pytest.fixture
    def mock_prompt_composer(self):
        """Create mock PromptComposer."""
        composer = MagicMock()
        composer.compose_agent_prompt = MagicMock(return_value="Test system prompt")
        return composer

    @pytest.fixture
    def mock_tool_factory(self):
        """Create mock tool factory."""
        factory = MagicMock()
        factory.create_tools = MagicMock(return_value=[])
        return factory

    @pytest.fixture
    def mock_context(self, mock_vram_orchestrator, mock_prompt_composer, mock_tool_factory):
        """Create mock execution context with required dependencies."""
        context = MagicMock()
        context.check_cancelled = AsyncMock()
        context.graph_domain = "research"
        context.interface = "test"
        context.user_profile = MagicMock()
        context.vram_orchestrator = mock_vram_orchestrator
        context.prompt_composer = mock_prompt_composer
        context.tool_factory = mock_tool_factory
        return context

    @pytest.fixture
    def executor(self):
        """Create graph executor."""
        return GraphExecutor()

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_research_swarm_flows_to_citation_formatter(
        self, mock_strands_agent_cls, mock_swarm_cls, executor, mock_context
    ):
        """Research swarm should flow to citation_formatter when complete."""
        # Setup mock swarm
        mock_swarm = create_mock_swarm("Research complete with verified facts")
        mock_swarm_cls.return_value = mock_swarm

        # Explorer determines research needed
        explorer = MockAgentNode("explorer", "need more research")

        # Research swarm does the work - use new API
        agent_configs = create_agent_configs(
            ["deep_research", "fact_checker", "synthesizer"],
            model_role="research"
        )
        research_swarm = ResearchSwarmNode(
            agent_configs=agent_configs,
            entry_point_name="deep_research",
            name="research_swarm",
        )

        # Citation formatter finalizes
        citation = MockAgentNode("citation_formatter", "formatted citations")

        def needs_research(state):
            return state.get("knowledge_score", 0) < 0.7

        graph = MockGraph(
            name="research_graph",
            nodes={
                "explorer": explorer,
                "research_swarm": research_swarm,
                "citation_formatter": citation,
            },
            edges={
                "explorer": [{"to": "research_swarm", "condition": needs_research}],
                "research_swarm": [{"to": "citation_formatter"}],
                "citation_formatter": [{"to": "END"}],
            },
            entry_node="explorer",
        )

        result = await executor.execute(
            graph=graph,
            context=mock_context,
            input_text="research AI safety",
        )

        assert result.success is True
        node_names = [r.node_name for r in result.node_results]
        assert "explorer" in node_names
        assert "research_swarm" in node_names
        assert "citation_formatter" in node_names
