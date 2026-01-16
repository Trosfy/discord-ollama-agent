"""Unit tests for Ask User Tool."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.plugins.tools.ask_user.tool import AskUserTool, create_ask_user_tool
from app.core.context import ExecutionContext
from app.core.container import Container


# =============================================================================
# Mock Classes
# =============================================================================

class MockWebSocket:
    """Mock WebSocket for testing."""
    def __init__(self):
        self.sent = []

    async def send_json(self, data):
        self.sent.append(data)


def create_mock_context(with_websocket: bool = True) -> ExecutionContext:
    """Create a mock execution context."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
        websocket=MockWebSocket() if with_websocket else None,
    )

    # Mock the request_user_input method
    context.request_user_input = AsyncMock(return_value="User response")

    return context


# =============================================================================
# Basic Execution Tests
# =============================================================================

async def test_execute_asks_question():
    """AskUserTool.execute sends question via context."""
    context = create_mock_context()
    container = Container()

    tool = AskUserTool(context=context, container=container)
    result = await tool.execute(
        {"question": "What color do you prefer?"},
        context,
    )

    assert result.success is True
    assert result.content == "User response"
    context.request_user_input.assert_called_once()


async def test_execute_with_options():
    """AskUserTool passes options to request_user_input."""
    context = create_mock_context()
    container = Container()

    tool = AskUserTool(context=context, container=container)
    await tool.execute(
        {
            "question": "Which framework?",
            "options": ["React", "Vue", "Angular"],
        },
        context,
    )

    context.request_user_input.assert_called_once()
    call_kwargs = context.request_user_input.call_args
    assert call_kwargs[1]["options"] == ["React", "Vue", "Angular"]


async def test_execute_with_timeout():
    """AskUserTool passes timeout to request_user_input."""
    context = create_mock_context()
    container = Container()

    tool = AskUserTool(context=context, container=container)
    await tool.execute(
        {
            "question": "Hurry up!",
            "timeout": 60,
        },
        context,
    )

    context.request_user_input.assert_called_once()
    call_kwargs = context.request_user_input.call_args
    assert call_kwargs[1]["timeout"] == 60


# =============================================================================
# Error Handling Tests
# =============================================================================

async def test_execute_missing_question():
    """AskUserTool returns error when question is missing."""
    context = create_mock_context()
    container = Container()

    tool = AskUserTool(context=context, container=container)
    result = await tool.execute({}, context)

    assert result.success is False
    assert "required" in result.error.lower()


async def test_execute_timeout_error():
    """AskUserTool handles timeout gracefully."""
    context = create_mock_context()
    context.request_user_input = AsyncMock(side_effect=TimeoutError())
    container = Container()

    tool = AskUserTool(context=context, container=container)
    result = await tool.execute(
        {"question": "Are you there?", "timeout": 5},
        context,
    )

    assert result.success is False
    assert "timeout" in result.error.lower() or "not respond" in result.error.lower()


async def test_execute_general_exception():
    """AskUserTool handles general exceptions."""
    context = create_mock_context()
    context.request_user_input = AsyncMock(side_effect=RuntimeError("Connection lost"))
    container = Container()

    tool = AskUserTool(context=context, container=container)
    result = await tool.execute(
        {"question": "Test?"},
        context,
    )

    assert result.success is False
    assert "Connection lost" in result.error


# =============================================================================
# Tool Schema Tests
# =============================================================================

def test_tool_schema():
    """AskUserTool has correct schema."""
    context = create_mock_context()
    container = Container()

    tool = AskUserTool(context=context, container=container)
    schema = tool.to_schema()

    assert schema["name"] == "ask_user"
    assert "parameters" in schema
    assert schema["parameters"]["type"] == "object"
    assert "question" in schema["parameters"]["properties"]
    assert "question" in schema["parameters"]["required"]


def test_tool_name():
    """AskUserTool has correct name attribute."""
    assert AskUserTool.name == "ask_user"


def test_tool_description():
    """AskUserTool has meaningful description."""
    assert "ask" in AskUserTool.description.lower()
    assert "user" in AskUserTool.description.lower()


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_ask_user_tool_factory():
    """create_ask_user_tool returns configured tool instance."""
    context = create_mock_context()
    container = Container()

    tool = create_ask_user_tool(context, container)

    assert isinstance(tool, AskUserTool)
    assert tool._context is context


async def test_factory_created_tool_works():
    """Tool created by factory works correctly."""
    context = create_mock_context()
    container = Container()

    tool = create_ask_user_tool(context, container)
    result = await tool.execute({"question": "Test?"}, context)

    assert result.success is True


# =============================================================================
# Default Values Tests
# =============================================================================

async def test_default_timeout():
    """AskUserTool uses default timeout when not specified."""
    context = create_mock_context()
    container = Container()

    tool = AskUserTool(context=context, container=container)
    await tool.execute({"question": "Test?"}, context)

    call_kwargs = context.request_user_input.call_args
    assert call_kwargs[1]["timeout"] == 300  # Default from tool
