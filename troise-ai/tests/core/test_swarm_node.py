"""Unit tests for SwarmNode classes.

Tests the SwarmNode adapter that wraps Strands Swarm
for graph execution with deferred agent creation.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from dataclasses import dataclass
from typing import Any, Dict, List

from app.core.graph_nodes import SwarmNode, SwarmAgentConfig, QualitySwarmNode, ResearchSwarmNode
from app.core.interfaces.graph import GraphState, NodeResult


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_agent_configs():
    """Create sample SwarmAgentConfig objects."""
    return [
        SwarmAgentConfig(
            name="agent1",
            model_id="test-model-1",
            model_role="research",
            temperature=0.7,
            max_tokens=4096,
            tools=["tool_a", "tool_b"],
        ),
        SwarmAgentConfig(
            name="agent2",
            model_id="test-model-2",
            model_role="research",
            temperature=0.7,
            max_tokens=4096,
            tools=["tool_b", "tool_c"],
        ),
    ]


@pytest.fixture
def mock_vram_orchestrator():
    """Create mock VRAMOrchestrator."""
    orchestrator = MagicMock()
    mock_model = MagicMock()
    orchestrator.get_model = AsyncMock(return_value=mock_model)
    return orchestrator


@pytest.fixture
def mock_prompt_composer():
    """Create mock PromptComposer."""
    composer = MagicMock()
    composer.compose_agent_prompt = MagicMock(return_value="Test system prompt")
    return composer


@pytest.fixture
def mock_tool_factory():
    """Create mock ToolFactory."""
    factory = MagicMock()
    factory.get_tool = MagicMock(return_value=MagicMock())
    return factory


@pytest.fixture
def mock_context(mock_vram_orchestrator, mock_prompt_composer):
    """Create mock execution context with required dependencies."""
    context = MagicMock()
    context.check_cancelled = AsyncMock()
    context.vram_orchestrator = mock_vram_orchestrator
    context.prompt_composer = mock_prompt_composer
    context.interface = "discord"
    context.user_profile = MagicMock()
    context.graph_domain = "research"
    return context


# =============================================================================
# SwarmNode Tests
# =============================================================================


class TestSwarmNode:
    """Unit tests for base SwarmNode."""

    def test_implements_igraph_node_protocol(self, mock_agent_configs):
        """SwarmNode should implement IGraphNode protocol (LSP)."""
        node = SwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="test_swarm",
        )
        assert hasattr(node, "name")
        assert hasattr(node, "execute")
        assert hasattr(node, "tools")
        assert callable(node.execute)

    def test_name_property(self, mock_agent_configs):
        """name should return the node name."""
        node = SwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="test_swarm",
        )
        assert node.name == "test_swarm"

    def test_tools_returns_empty_managed_by_strands(self, mock_agent_configs):
        """tools property should return empty - Strands manages tools internally."""
        node = SwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="test_swarm",
        )
        # Swarm tools are managed by Strands SDK, not exposed via property
        assert node.tools == []

    def test_tools_empty_when_no_configs(self):
        """tools should return empty list when no agent configs."""
        node = SwarmNode(
            agent_configs=[],
            entry_point_name="",
            name="empty_swarm",
        )
        assert node.tools == []

    def test_custom_state_key(self, mock_agent_configs):
        """SwarmNode should use custom state_key when provided."""
        node = SwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="my_swarm",
            state_key="custom_key",
        )
        assert node._state_key == "custom_key"

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_execute_returns_node_result(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """execute() should return NodeResult (LSP compliance)."""
        # Setup mock swarm with async invoke_async method
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(return_value="test swarm output")
        mock_swarm_cls.return_value = mock_swarm

        node = SwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="test_swarm",
        )
        state = GraphState()
        state.set("input", "test input")

        result = await node.execute(
            state, mock_context, input_text="test input", tool_factory=mock_tool_factory
        )

        assert isinstance(result, NodeResult)
        assert result.node_name == "test_swarm"
        assert result.success is True

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_execute_creates_agents_with_composed_prompts(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """execute() should create agents with prompts from PromptComposer."""
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(return_value="swarm output")
        mock_swarm_cls.return_value = mock_swarm

        node = SwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="test_swarm",
        )
        state = GraphState()

        await node.execute(
            state, mock_context, input_text="test", tool_factory=mock_tool_factory
        )

        # Verify PromptComposer was called for each agent
        assert mock_context.prompt_composer.compose_agent_prompt.call_count == 2

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_execute_uses_vram_orchestrator_for_models(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """execute() should use VRAMOrchestrator to get models."""
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(return_value="swarm output")
        mock_swarm_cls.return_value = mock_swarm

        node = SwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="test_swarm",
        )
        state = GraphState()

        await node.execute(
            state, mock_context, input_text="test", tool_factory=mock_tool_factory
        )

        # Verify VRAMOrchestrator was called for each agent
        assert mock_context.vram_orchestrator.get_model.call_count == 2

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_execute_handles_swarm_error(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """execute() should handle swarm errors gracefully."""
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(side_effect=Exception("Swarm failed"))
        mock_swarm_cls.return_value = mock_swarm

        node = SwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="failing_swarm",
        )
        state = GraphState()

        result = await node.execute(
            state, mock_context, input_text="test", tool_factory=mock_tool_factory
        )

        assert result.success is False
        assert "Swarm failed" in result.content

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_state_updates_include_output(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """execute() should include output in state updates."""
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(return_value="test swarm output")
        mock_swarm_cls.return_value = mock_swarm

        node = SwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="test_swarm",
        )
        state = GraphState()
        state.set("input", "test")

        result = await node.execute(
            state, mock_context, input_text="test", tool_factory=mock_tool_factory
        )

        assert "test_swarm_output" in result.state_updates

    @pytest.mark.asyncio
    async def test_execute_fails_without_vram_orchestrator(self, mock_agent_configs):
        """execute() should fail gracefully if vram_orchestrator missing."""
        context = MagicMock()
        context.check_cancelled = AsyncMock()
        context.vram_orchestrator = None
        context.prompt_composer = MagicMock()

        node = SwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="test_swarm",
        )
        state = GraphState()

        result = await node.execute(state, context, input_text="test")

        assert result.success is False
        # Error is gracefully captured (message may vary based on where None is accessed)
        assert "Error" in result.content or "NoneType" in result.content

    @pytest.mark.asyncio
    async def test_execute_fails_without_prompt_composer(
        self, mock_agent_configs, mock_vram_orchestrator
    ):
        """execute() should fail gracefully if prompt_composer missing."""
        context = MagicMock()
        context.check_cancelled = AsyncMock()
        context.vram_orchestrator = mock_vram_orchestrator
        context.prompt_composer = None

        node = SwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="test_swarm",
        )
        state = GraphState()

        result = await node.execute(state, context, input_text="test")

        assert result.success is False
        assert "PromptComposer" in result.content or "prompt" in result.content.lower()


# =============================================================================
# QualitySwarmNode Tests
# =============================================================================


class TestQualitySwarmNode:
    """Tests for QualitySwarmNode state extraction."""

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_extracts_review_issues_when_present(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """Should extract review_issues when issues found."""
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(return_value="Found bug in line 42, needs fix")
        mock_swarm_cls.return_value = mock_swarm

        node = QualitySwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="quality_swarm",
        )
        state = GraphState()
        state.set("input", "review code")

        result = await node.execute(
            state, mock_context, input_text="review code", tool_factory=mock_tool_factory
        )

        assert result.state_updates.get("review_issues") != []
        assert result.state_updates.get("review_passed") is False

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_no_issues_when_clean_code(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """Should set review_passed when no issues found."""
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(return_value="Code looks good, all tests passing")
        mock_swarm_cls.return_value = mock_swarm

        node = QualitySwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="quality_swarm",
        )
        state = GraphState()
        state.set("input", "review code")

        result = await node.execute(
            state, mock_context, input_text="review code", tool_factory=mock_tool_factory
        )

        assert result.state_updates.get("review_issues") == []
        assert result.state_updates.get("review_passed") is True

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_extracts_test_results_passed(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """Should extract test_results when tests passed."""
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(return_value="All tests passed successfully")
        mock_swarm_cls.return_value = mock_swarm

        node = QualitySwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="quality_swarm",
        )
        state = GraphState()

        result = await node.execute(
            state, mock_context, input_text="review", tool_factory=mock_tool_factory
        )

        assert result.state_updates["test_results"]["passed"] is True

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_extracts_test_results_failed(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """Should extract test_results when tests failed."""
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(return_value="Tests failed: 2 errors")
        mock_swarm_cls.return_value = mock_swarm

        node = QualitySwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="quality_swarm",
        )
        state = GraphState()

        result = await node.execute(
            state, mock_context, input_text="review", tool_factory=mock_tool_factory
        )

        assert result.state_updates["test_results"]["passed"] is False

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_detects_security_vulnerability(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """Should detect security-related issues."""
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(return_value="Found SQL injection vulnerability")
        mock_swarm_cls.return_value = mock_swarm

        node = QualitySwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="quality_swarm",
        )
        state = GraphState()

        result = await node.execute(
            state, mock_context, input_text="review", tool_factory=mock_tool_factory
        )

        assert result.state_updates.get("review_passed") is False


# =============================================================================
# ResearchSwarmNode Tests
# =============================================================================


class TestResearchSwarmNode:
    """Tests for ResearchSwarmNode state extraction."""

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_extracts_unverified_claims(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """Should extract unverified_claims when facts not verified."""
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(return_value="Unable to verify the claim about X")
        mock_swarm_cls.return_value = mock_swarm

        node = ResearchSwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="research_swarm",
        )
        state = GraphState()
        state.set("input", "research topic")

        result = await node.execute(
            state, mock_context, input_text="research topic", tool_factory=mock_tool_factory
        )

        assert result.state_updates.get("unverified_claims") != []
        assert result.state_updates.get("facts_verified") is False

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_facts_verified_when_all_confirmed(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """Should set facts_verified when all claims verified."""
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(return_value="All claims verified with sources")
        mock_swarm_cls.return_value = mock_swarm

        node = ResearchSwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="research_swarm",
        )
        state = GraphState()
        state.set("input", "research topic")

        result = await node.execute(
            state, mock_context, input_text="research topic", tool_factory=mock_tool_factory
        )

        assert result.state_updates.get("unverified_claims") == []
        assert result.state_updates.get("facts_verified") is True

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_detects_insufficient_sources(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """Should detect when more sources needed."""
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(return_value="Insufficient evidence for this claim")
        mock_swarm_cls.return_value = mock_swarm

        node = ResearchSwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="research_swarm",
        )
        state = GraphState()

        result = await node.execute(
            state, mock_context, input_text="research", tool_factory=mock_tool_factory
        )

        assert result.state_updates.get("facts_verified") is False

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_detects_no_source_found(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """Should detect when no source found."""
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(return_value="No source available for this")
        mock_swarm_cls.return_value = mock_swarm

        node = ResearchSwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="research_swarm",
        )
        state = GraphState()

        result = await node.execute(
            state, mock_context, input_text="research", tool_factory=mock_tool_factory
        )

        assert result.state_updates.get("facts_verified") is False


# =============================================================================
# Integration Tests (within unit test file)
# =============================================================================


class TestSwarmNodeIntegration:
    """Basic integration tests for SwarmNode with graph state."""

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_state_propagation_through_nodes(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """State updates from SwarmNode should be usable by subsequent nodes."""
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(return_value="Code reviewed, all tests passed")
        mock_swarm_cls.return_value = mock_swarm

        node = QualitySwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="quality_swarm",
        )
        state = GraphState()
        state.set("input", "test input")
        state.set("previous_code", "def foo(): pass")

        result = await node.execute(
            state, mock_context, input_text="test input", tool_factory=mock_tool_factory
        )

        # Update state with results
        state.update(result.state_updates)

        # Verify state was updated
        assert state.get("quality_swarm_output") is not None
        assert state.get("review_passed") is True
        assert state.get("test_results")["passed"] is True

    @pytest.mark.asyncio
    @patch("strands.multiagent.Swarm")
    @patch("strands.Agent")
    async def test_node_preserves_existing_state(
        self,
        mock_strands_agent_cls,
        mock_swarm_cls,
        mock_agent_configs,
        mock_context,
        mock_tool_factory,
    ):
        """SwarmNode should not overwrite unrelated state."""
        mock_swarm = MagicMock()
        mock_swarm.invoke_async = AsyncMock(return_value="done")
        mock_swarm_cls.return_value = mock_swarm

        node = SwarmNode(
            agent_configs=mock_agent_configs,
            entry_point_name="agent1",
            name="test_swarm",
        )
        state = GraphState()
        state.set("input", "test")
        state.set("existing_key", "existing_value")

        result = await node.execute(
            state, mock_context, input_text="test", tool_factory=mock_tool_factory
        )
        state.update(result.state_updates)

        assert state.get("existing_key") == "existing_value"
        assert state.get("test_swarm_output") is not None
