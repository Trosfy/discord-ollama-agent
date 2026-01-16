"""Unit tests for Agentic Code Agent."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.plugins.agents.agentic_code import AgenticCodeAgent, create_agentic_code_agent
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
        agent_name="agentic_code",
    )
    return context


@pytest.fixture
def mock_vram_orchestrator():
    """Create mock VRAM orchestrator."""
    orchestrator = MagicMock()
    mock_model = MagicMock()
    mock_model.close = AsyncMock()  # Make close awaitable
    orchestrator.get_model = AsyncMock(return_value=mock_model)
    # Mock get_profile_model (sync method) to return model for code role
    orchestrator.get_profile_model.return_value = "devstral:24b"
    return orchestrator


@pytest.fixture
def mock_tools():
    """Create mock tool list."""
    return [
        MagicMock(name="brain_search"),
        MagicMock(name="read_file"),
        MagicMock(name="write_file"),
        MagicMock(name="run_code"),
    ]


@pytest.fixture
def mock_prompt_composer():
    """Create mock prompt composer."""
    return MockPromptComposer()


@pytest.fixture
def agentic_code_agent(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """Create agentic code agent with mocks."""
    return AgenticCodeAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
    )


# =============================================================================
# Agent Attributes Tests
# =============================================================================

def test_agent_name():
    """Agent has correct name attribute."""
    assert AgenticCodeAgent.name == "agentic_code"


def test_agent_category():
    """Agent has correct category attribute."""
    assert AgenticCodeAgent.category == "code"


def test_agent_tools():
    """Agent declares required tools."""
    assert "brain_search" in AgenticCodeAgent.tools
    assert "read_file" in AgenticCodeAgent.tools
    assert "run_code" in AgenticCodeAgent.tools


# =============================================================================
# Initialization Tests
# =============================================================================

def test_init_stores_orchestrator(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() stores VRAM orchestrator."""
    agent = AgenticCodeAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
    )

    assert agent._vram_orchestrator == mock_vram_orchestrator


def test_init_stores_tools(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() stores tools."""
    agent = AgenticCodeAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
    )

    assert agent._tools == mock_tools


def test_init_default_model(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() uses code-optimized model by default."""
    agent = AgenticCodeAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
    )

    # Uses devstral for code generation
    assert agent._model_id == "devstral:24b"


def test_init_custom_model(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() accepts custom model in config."""
    agent = AgenticCodeAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
        config={"model": "codestral:22b"},
    )

    assert agent._model_id == "codestral:22b"


# =============================================================================
# Execute Tests
# =============================================================================

@pytest.mark.asyncio
async def test_execute_gets_model(agentic_code_agent, mock_context, mock_vram_orchestrator):
    """execute() requests model from orchestrator."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        await agentic_code_agent.execute("write a hello world function", mock_context)

        mock_vram_orchestrator.get_model.assert_called_once()


@pytest.mark.asyncio
async def test_execute_uses_low_temperature(agentic_code_agent, mock_context, mock_vram_orchestrator):
    """execute() uses low temperature for code generation."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        await agentic_code_agent.execute("write a function", mock_context)

        call_kwargs = mock_vram_orchestrator.get_model.call_args[1]
        assert call_kwargs["temperature"] == 0.2  # Low for deterministic code


@pytest.mark.asyncio
async def test_execute_uses_long_context(agentic_code_agent, mock_context, mock_vram_orchestrator):
    """execute() uses longer context for code."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        await agentic_code_agent.execute("write a function", mock_context)

        call_kwargs = mock_vram_orchestrator.get_model.call_args[1]
        assert call_kwargs["max_tokens"] == 8192


@pytest.mark.asyncio
async def test_execute_creates_strands_agent(agentic_code_agent, mock_context):
    """execute() creates Strands Agent with correct parameters."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        await agentic_code_agent.execute("write a function", mock_context)

        MockAgent.assert_called_once()
        call_kwargs = MockAgent.call_args[1]
        assert "model" in call_kwargs
        assert "tools" in call_kwargs
        assert "system_prompt" in call_kwargs


@pytest.mark.asyncio
async def test_execute_returns_agent_result(agentic_code_agent, mock_context):
    """execute() returns AgentResult."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        result = await agentic_code_agent.execute("write a function", mock_context)

        assert isinstance(result, AgentResult)


@pytest.mark.asyncio
async def test_execute_handles_text_events(agentic_code_agent, mock_context):
    """execute() collects text from contentBlockDelta events."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()

        async def mock_stream(*args, **kwargs):
            yield {"contentBlockDelta": {"delta": {"text": "def hello():"}}}
            yield {"contentBlockDelta": {"delta": {"text": "\n    pass"}}}

        mock_agent_instance.stream_async = mock_stream
        MockAgent.return_value = mock_agent_instance

        result = await agentic_code_agent.execute("write hello function", mock_context)

        assert result.content == "def hello():\n    pass"


@pytest.mark.asyncio
async def test_execute_tracks_tool_calls(agentic_code_agent, mock_context):
    """execute() tracks tool calls from events."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()

        async def mock_stream(*args, **kwargs):
            yield {"contentBlockStart": {"start": {"toolUse": {"name": "read_file", "toolUseId": "123"}}}}
            yield {"contentBlockStart": {"start": {"toolUse": {"name": "write_file", "toolUseId": "456"}}}}
            yield {"contentBlockStart": {"start": {"toolUse": {"name": "run_code", "toolUseId": "789"}}}}

        mock_agent_instance.stream_async = mock_stream
        MockAgent.return_value = mock_agent_instance

        result = await agentic_code_agent.execute("write and test function", mock_context)

        assert len(result.tool_calls) == 3
        tool_names = [tc["name"] for tc in result.tool_calls]
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "run_code" in tool_names


@pytest.mark.asyncio
async def test_execute_tracks_files_read(agentic_code_agent, mock_context):
    """execute() tracks file read operations in metadata."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()

        async def mock_stream(*args, **kwargs):
            yield {"contentBlockStart": {"start": {"toolUse": {"name": "read_file", "toolUseId": "1"}}}}
            yield {"contentBlockStart": {"start": {"toolUse": {"name": "read_file", "toolUseId": "2"}}}}

        mock_agent_instance.stream_async = mock_stream
        MockAgent.return_value = mock_agent_instance

        result = await agentic_code_agent.execute("review code", mock_context)

        assert result.metadata["files_read"] == 2


@pytest.mark.asyncio
async def test_execute_tracks_code_executions(agentic_code_agent, mock_context):
    """execute() tracks code execution operations in metadata."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()

        async def mock_stream(*args, **kwargs):
            yield {"contentBlockStart": {"start": {"toolUse": {"name": "run_code", "toolUseId": "1"}}}}
            yield {"contentBlockStart": {"start": {"toolUse": {"name": "run_code", "toolUseId": "2"}}}}

        mock_agent_instance.stream_async = mock_stream
        MockAgent.return_value = mock_agent_instance

        result = await agentic_code_agent.execute("test the function", mock_context)

        assert result.metadata["code_executions"] == 2


@pytest.mark.asyncio
async def test_execute_includes_metadata(agentic_code_agent, mock_context):
    """execute() includes agent metadata in result."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        result = await agentic_code_agent.execute("write a function", mock_context)

        assert result.metadata["agent"] == "agentic_code"
        assert result.metadata["model"] == "devstral:24b"


@pytest.mark.asyncio
async def test_execute_checks_cancellation(agentic_code_agent, mock_context):
    """execute() checks for cancellation during streaming."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()

        async def mock_stream(*args, **kwargs):
            yield {"contentBlockDelta": {"delta": {"text": "code"}}}

        mock_agent_instance.stream_async = mock_stream
        MockAgent.return_value = mock_agent_instance

        mock_context.check_cancelled = AsyncMock()

        await agentic_code_agent.execute("write function", mock_context)

        mock_context.check_cancelled.assert_called()


@pytest.mark.asyncio
async def test_execute_handles_errors(agentic_code_agent, mock_context):
    """execute() returns error result on exception."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        MockAgent.side_effect = Exception("Code generation failed")

        result = await agentic_code_agent.execute("write function", mock_context)

        assert "error" in result.metadata
        assert "Code generation failed" in result.content


@pytest.mark.asyncio
async def test_execute_uses_interface_context(agentic_code_agent, mock_context):
    """execute() includes interface context in system prompt."""
    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        await agentic_code_agent.execute("write function", mock_context)

        call_kwargs = MockAgent.call_args[1]
        assert "{interface_context}" not in call_kwargs["system_prompt"]


@pytest.mark.asyncio
async def test_execute_uses_personalization_context(agentic_code_agent, mock_context):
    """execute() includes personalization context in system prompt."""
    mock_context.user_profile.preferences = {"code_style": "pythonic"}

    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        await agentic_code_agent.execute("write function", mock_context)

        call_kwargs = MockAgent.call_args[1]
        assert "{personalization_context}" not in call_kwargs["system_prompt"]


@pytest.mark.asyncio
async def test_execute_closes_model_on_success(agentic_code_agent, mock_context, mock_vram_orchestrator):
    """execute() closes model after successful execution."""
    mock_model = MagicMock()
    mock_model.close = AsyncMock()
    mock_vram_orchestrator.get_model.return_value = mock_model

    with patch("app.core.base_agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.stream_async = empty_stream
        MockAgent.return_value = mock_agent_instance

        await agentic_code_agent.execute("write function", mock_context)

        mock_model.close.assert_called_once()


@pytest.mark.asyncio
async def test_execute_closes_model_on_error(agentic_code_agent, mock_context, mock_vram_orchestrator):
    """execute() closes model even on error."""
    mock_model = MagicMock()
    mock_model.close = AsyncMock()
    mock_vram_orchestrator.get_model.return_value = mock_model

    with patch("app.core.base_agent.Agent") as MockAgent:
        MockAgent.side_effect = Exception("Test error")

        await agentic_code_agent.execute("write function", mock_context)

        mock_model.close.assert_called_once()


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_agentic_code_agent_factory():
    """create_agentic_code_agent() creates agent instance."""
    mock_orchestrator = AsyncMock()
    mock_tools = [MagicMock()]
    mock_composer = MockPromptComposer()

    agent = create_agentic_code_agent(mock_orchestrator, mock_tools, mock_composer)

    assert isinstance(agent, AgenticCodeAgent)
    assert agent._vram_orchestrator == mock_orchestrator


def test_create_agentic_code_agent_with_config():
    """create_agentic_code_agent() accepts config."""
    mock_orchestrator = AsyncMock()
    mock_tools = [MagicMock()]
    mock_composer = MockPromptComposer()

    agent = create_agentic_code_agent(
        mock_orchestrator,
        mock_tools,
        mock_composer,
        config={"model": "codestral:22b"},
    )

    assert agent._model_id == "codestral:22b"
