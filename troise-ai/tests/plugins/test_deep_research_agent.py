"""Unit tests for Deep Research Agent."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.plugins.agents.deep_research import DeepResearchAgent, create_deep_research_agent
from app.core.context import ExecutionContext, UserProfile
from app.core.interfaces.agent import AgentResult


# =============================================================================
# Mock Classes
# =============================================================================

class MockPromptComposer:
    """Mock PromptComposer for testing."""

    def compose_agent_prompt(
        self,
        agent_name: str,
        interface: str,
        profile: str = None,
        user_profile=None,
        **format_vars,
    ) -> str:
        """Compose agent prompt with interface and personalization layers."""
        interface_context = f"## {interface.title()} Interface\nFormatted for {interface}."
        personalization_context = ""
        if user_profile:
            personalization_context = user_profile.get_personalization_context()

        return f"""You are the {agent_name} agent.

{interface_context}

{personalization_context or "No specific preferences."}"""


# =============================================================================
# Helper - Empty async generator
# =============================================================================

async def empty_stream(*args, **kwargs):
    """Empty async generator for mocking stream_async."""
    return
    yield


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_context():
    """Create mock execution context."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
        user_profile=UserProfile(user_id="test-user"),
        agent_name="deep_research",
    )
    return context


@pytest.fixture
def mock_vram_orchestrator():
    """Create mock VRAM orchestrator."""
    orchestrator = MagicMock()
    mock_model = MagicMock()
    mock_model.close = AsyncMock()  # Make close awaitable
    orchestrator.get_model = AsyncMock(return_value=mock_model)
    # Mock get_profile_model (sync method) to return model for research role
    orchestrator.get_profile_model.return_value = "magistral:24b"
    return orchestrator


@pytest.fixture
def mock_tools():
    """Create mock tool list."""
    return [
        MagicMock(name="web_search"),
        MagicMock(name="brain_search"),
        MagicMock(name="save_note"),
    ]


@pytest.fixture
def mock_prompt_composer():
    """Create mock prompt composer."""
    return MockPromptComposer()


@pytest.fixture
def deep_research_agent(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """Create deep research agent with mocks."""
    return DeepResearchAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
    )


# =============================================================================
# Agent Attributes Tests
# =============================================================================

def test_agent_name():
    """Agent has correct name attribute."""
    assert DeepResearchAgent.name == "deep_research"


def test_agent_category():
    """Agent has correct category attribute."""
    assert DeepResearchAgent.category == "research"


def test_agent_tools():
    """Agent declares required tools."""
    assert "web_search" in DeepResearchAgent.tools
    assert "web_fetch" in DeepResearchAgent.tools
    assert "brain_search" in DeepResearchAgent.tools
    assert "save_note" in DeepResearchAgent.tools


# =============================================================================
# Initialization Tests
# =============================================================================

def test_init_stores_orchestrator(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() stores VRAM orchestrator."""
    agent = DeepResearchAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
    )

    assert agent._vram_orchestrator == mock_vram_orchestrator


def test_init_stores_tools(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() stores tools."""
    agent = DeepResearchAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
    )

    assert agent._tools == mock_tools


def test_init_default_model(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() uses default model when not specified."""
    agent = DeepResearchAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
    )

    assert agent._model_id == "magistral:24b"


def test_init_custom_model(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() accepts custom model in config."""
    agent = DeepResearchAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
        config={"model": "qwen3:72b"},
    )

    assert agent._model_id == "qwen3:72b"


def test_init_default_max_tokens(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() uses default max_tokens."""
    agent = DeepResearchAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
    )

    # Deep research uses 8192 for longer reports
    assert agent._max_tokens == 8192


def test_init_custom_max_tokens(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() accepts custom max_tokens."""
    agent = DeepResearchAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
        config={"max_tokens": 16384},
    )

    assert agent._max_tokens == 16384


# =============================================================================
# Execute Tests
# =============================================================================

@pytest.mark.asyncio
async def test_execute_gets_model(deep_research_agent, mock_context, mock_vram_orchestrator):
    """execute() requests model from orchestrator."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        await deep_research_agent.execute("research quantum computing", mock_context)

        mock_vram_orchestrator.get_model.assert_called_once()


@pytest.mark.asyncio
async def test_execute_creates_strands_agent(deep_research_agent, mock_context):
    """execute() creates Strands Agent with correct parameters."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        await deep_research_agent.execute("research quantum computing", mock_context)

        MockAgent.assert_called_once()
        call_kwargs = MockAgent.call_args[1]
        assert "model" in call_kwargs
        assert "tools" in call_kwargs
        assert "system_prompt" in call_kwargs


@pytest.mark.asyncio
async def test_execute_returns_agent_result(deep_research_agent, mock_context):
    """execute() returns AgentResult."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        result = await deep_research_agent.execute("research quantum computing", mock_context)

        assert isinstance(result, AgentResult)


@pytest.mark.asyncio
async def test_execute_handles_text_events(deep_research_agent, mock_context):
    """execute() collects text from contentBlockDelta events."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()

        async def mock_stream(*args, **kwargs):
            yield {"contentBlockDelta": {"delta": {"text": "Research "}}}
            yield {"contentBlockDelta": {"delta": {"text": "findings"}}}

        mock_agent_instance.stream_async = mock_stream
        MockAgent.return_value = mock_agent_instance

        result = await deep_research_agent.execute("research quantum computing", mock_context)

        assert result.content == "Research findings"


@pytest.mark.asyncio
async def test_execute_tracks_tool_calls(deep_research_agent, mock_context):
    """execute() tracks tool calls from events."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()

        async def mock_stream(*args, **kwargs):
            yield {"contentBlockStart": {"start": {"toolUse": {"name": "web_search", "toolUseId": "123"}}}}
            yield {"contentBlockStart": {"start": {"toolUse": {"name": "brain_search", "toolUseId": "456"}}}}
            yield {"contentBlockDelta": {"delta": {"text": "Done"}}}

        mock_agent_instance.stream_async = mock_stream
        MockAgent.return_value = mock_agent_instance

        result = await deep_research_agent.execute("research quantum computing", mock_context)

        assert len(result.tool_calls) == 2
        tool_names = [tc["name"] for tc in result.tool_calls]
        assert "web_search" in tool_names
        assert "brain_search" in tool_names


@pytest.mark.asyncio
async def test_execute_tracks_web_searches(deep_research_agent, mock_context):
    """execute() tracks web search calls in metadata."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()

        async def mock_stream(*args, **kwargs):
            yield {"contentBlockStart": {"start": {"toolUse": {"name": "web_search", "toolUseId": "123"}}}}
            yield {"contentBlockStart": {"start": {"toolUse": {"name": "web_search", "toolUseId": "456"}}}}

        mock_agent_instance.stream_async = mock_stream
        MockAgent.return_value = mock_agent_instance

        result = await deep_research_agent.execute("research quantum computing", mock_context)

        assert result.metadata["web_searches"] == 2


@pytest.mark.asyncio
async def test_execute_tracks_brain_searches(deep_research_agent, mock_context):
    """execute() tracks brain search calls in metadata."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()

        async def mock_stream(*args, **kwargs):
            yield {"contentBlockStart": {"start": {"toolUse": {"name": "brain_search", "toolUseId": "123"}}}}

        mock_agent_instance.stream_async = mock_stream
        MockAgent.return_value = mock_agent_instance

        result = await deep_research_agent.execute("research quantum computing", mock_context)

        assert result.metadata["brain_searches"] == 1


@pytest.mark.asyncio
async def test_execute_includes_metadata(deep_research_agent, mock_context):
    """execute() includes agent metadata in result."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        result = await deep_research_agent.execute("research quantum computing", mock_context)

        assert "agent" in result.metadata
        assert result.metadata["agent"] == "deep_research"
        assert "model" in result.metadata


@pytest.mark.asyncio
async def test_execute_checks_cancellation(deep_research_agent, mock_context):
    """execute() checks for cancellation during streaming."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()

        async def mock_stream(*args, **kwargs):
            yield {"contentBlockDelta": {"delta": {"text": "test"}}}

        mock_agent_instance.stream_async = mock_stream
        MockAgent.return_value = mock_agent_instance

        mock_context.check_cancelled = AsyncMock()

        await deep_research_agent.execute("research quantum computing", mock_context)

        mock_context.check_cancelled.assert_called()


@pytest.mark.asyncio
async def test_execute_handles_errors(deep_research_agent, mock_context):
    """execute() returns error result on exception."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        MockAgent.side_effect = Exception("Research failed")

        result = await deep_research_agent.execute("research quantum computing", mock_context)

        assert "error" in result.metadata
        assert "Research failed" in result.content


@pytest.mark.asyncio
async def test_execute_uses_interface_context(deep_research_agent, mock_context):
    """execute() includes interface context in system prompt."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        await deep_research_agent.execute("research quantum computing", mock_context)

        call_kwargs = MockAgent.call_args[1]
        assert "{interface_context}" not in call_kwargs["system_prompt"]


@pytest.mark.asyncio
async def test_execute_uses_personalization_context(deep_research_agent, mock_context):
    """execute() includes personalization context in system prompt."""
    mock_context.user_profile.preferences = {"detail_level": "high"}

    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        await deep_research_agent.execute("research quantum computing", mock_context)

        call_kwargs = MockAgent.call_args[1]
        assert "{personalization_context}" not in call_kwargs["system_prompt"]


@pytest.mark.asyncio
async def test_execute_closes_model_on_success(deep_research_agent, mock_context, mock_vram_orchestrator):
    """execute() closes model after successful execution."""
    mock_model = MagicMock()
    mock_model.close = AsyncMock()
    mock_vram_orchestrator.get_model.return_value = mock_model

    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        await deep_research_agent.execute("research quantum computing", mock_context)

        mock_model.close.assert_called_once()


@pytest.mark.asyncio
async def test_execute_closes_model_on_error(deep_research_agent, mock_context, mock_vram_orchestrator):
    """execute() closes model even on error."""
    mock_model = MagicMock()
    mock_model.close = AsyncMock()
    mock_vram_orchestrator.get_model.return_value = mock_model

    with patch("app.core.base_agent.Agent") as MockAgent:
        MockAgent.side_effect = Exception("Test error")

        await deep_research_agent.execute("research quantum computing", mock_context)

        mock_model.close.assert_called_once()


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_deep_research_agent_factory():
    """create_deep_research_agent() creates agent instance."""
    mock_orchestrator = AsyncMock()
    mock_tools = [MagicMock()]
    mock_composer = MockPromptComposer()

    agent = create_deep_research_agent(mock_orchestrator, mock_tools, mock_composer)

    assert isinstance(agent, DeepResearchAgent)
    assert agent._vram_orchestrator == mock_orchestrator


def test_create_deep_research_agent_with_config():
    """create_deep_research_agent() accepts config."""
    mock_orchestrator = AsyncMock()
    mock_tools = [MagicMock()]
    mock_composer = MockPromptComposer()

    agent = create_deep_research_agent(
        mock_orchestrator,
        mock_tools,
        mock_composer,
        config={"model": "qwen3:72b", "max_tokens": 16384},
    )

    assert agent._model_id == "qwen3:72b"
    assert agent._max_tokens == 16384
