"""Unit tests for Tool Factory."""
import pytest
import json
from typing import Any, Dict
from unittest.mock import MagicMock, AsyncMock

from app.core.tool_factory import ToolFactory, create_simple_tool
from app.core.registry import PluginRegistry
from app.core.container import Container
from app.core.context import ExecutionContext
from app.core.interfaces.tool import ToolResult


# =============================================================================
# Mock Tool
# =============================================================================

class MockTool:
    """Mock tool for testing."""
    name = "mock_tool"
    description = "A mock tool for testing"
    parameters = {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "Test input"},
        },
        "required": ["input"],
    }

    def __init__(self, context: ExecutionContext, container: Container):
        self._context = context
        self._container = container

    async def execute(
        self,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        return ToolResult(
            content=f"Mock result: {params.get('input', '')}",
            success=True,
        )

    def to_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class MockToolThatFails:
    """Mock tool that raises an exception."""
    name = "failing_tool"
    description = "A tool that fails"
    parameters = {"type": "object", "properties": {}}

    def __init__(self, context: ExecutionContext, container: Container):
        pass

    async def execute(self, params, context) -> ToolResult:
        raise RuntimeError("Tool execution failed!")

    def to_schema(self):
        return {"name": self.name, "description": self.description}


def mock_tool_factory(context: ExecutionContext, container: Container) -> MockTool:
    """Factory function for mock tool."""
    return MockTool(context, container)


def create_mock_context() -> ExecutionContext:
    """Create a mock execution context."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="test",
        websocket=None,
    )
    # Mock check_cancelled to be a coroutine that does nothing
    context.check_cancelled = AsyncMock()
    return context


def create_test_registry() -> PluginRegistry:
    """Create a registry with mock tools."""
    registry = PluginRegistry()

    # Tool with factory
    registry._tools["mock_tool"] = {
        "type": "tool",
        "name": "mock_tool",
        "factory": mock_tool_factory,
        "description": "Mock tool for testing",
    }

    # Tool with class
    registry._tools["class_tool"] = {
        "type": "tool",
        "name": "class_tool",
        "class": MockTool,
        "description": "Tool using class pattern",
    }

    # Tool that fails
    registry._tools["failing_tool"] = {
        "type": "tool",
        "name": "failing_tool",
        "class": MockToolThatFails,
        "description": "Tool that fails",
    }

    # Agent with tools configured
    registry._agents["test_agent"] = {
        "type": "agent",
        "name": "test_agent",
        "config": {
            "tools": ["mock_tool", "class_tool"],
        },
    }

    return registry


# =============================================================================
# Create Tools for Agent Tests
# =============================================================================

def test_create_tools_for_agent():
    """Creates tools for agent from registry configuration."""
    registry = create_test_registry()
    container = Container()
    context = create_mock_context()

    factory = ToolFactory(registry, container)
    tools = factory.create_tools_for_agent("test_agent", context)

    assert len(tools) == 2

    # Each tool should have Strands format
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "parameters" in tool
        assert "handler" in tool
        assert callable(tool["handler"])


def test_create_tools_for_agent_no_tools():
    """Returns empty list when agent has no tools."""
    registry = PluginRegistry()
    registry._agents["no_tools"] = {"type": "agent", "name": "no_tools", "config": {}}
    container = Container()
    context = create_mock_context()

    factory = ToolFactory(registry, container)
    tools = factory.create_tools_for_agent("no_tools", context)

    assert tools == []


def test_create_tools_for_agent_unknown_agent():
    """Returns empty list for unknown agent."""
    registry = PluginRegistry()
    container = Container()
    context = create_mock_context()

    factory = ToolFactory(registry, container)
    tools = factory.create_tools_for_agent("nonexistent", context)

    assert tools == []


# =============================================================================
# Create Single Tool Tests
# =============================================================================

def test_create_single_tool():
    """Creates a single tool by name."""
    registry = create_test_registry()
    container = Container()
    context = create_mock_context()

    factory = ToolFactory(registry, container)
    tool = factory.create_tool("mock_tool", context)

    assert tool is not None
    assert tool["name"] == "mock_tool"
    assert callable(tool["handler"])


def test_create_single_tool_not_found():
    """Returns None for unknown tool."""
    registry = PluginRegistry()
    container = Container()
    context = create_mock_context()

    factory = ToolFactory(registry, container)
    tool = factory.create_tool("nonexistent", context)

    assert tool is None


def test_create_tool_with_class_pattern():
    """Creates tool using class pattern (not factory)."""
    registry = create_test_registry()
    container = Container()
    context = create_mock_context()

    factory = ToolFactory(registry, container)
    tool = factory.create_tool("class_tool", context)

    assert tool is not None
    # Same interface as factory-created tools
    assert tool["name"] == "mock_tool"  # Uses MockTool.name
    assert callable(tool["handler"])


# =============================================================================
# Strands Tool Format Tests
# =============================================================================

def test_strands_tool_format():
    """Tools have correct Strands format."""
    registry = create_test_registry()
    container = Container()
    context = create_mock_context()

    factory = ToolFactory(registry, container)
    tool = factory.create_tool("mock_tool", context)

    assert "name" in tool
    assert "description" in tool
    assert "parameters" in tool
    assert "handler" in tool

    # Parameters should be JSON Schema
    assert tool["parameters"]["type"] == "object"
    assert "properties" in tool["parameters"]


async def test_tool_handler_returns_json():
    """Tool handler returns JSON string."""
    registry = create_test_registry()
    container = Container()
    context = create_mock_context()

    factory = ToolFactory(registry, container)
    tool = factory.create_tool("mock_tool", context)

    result = await tool["handler"]({"input": "test"})

    # Result should be JSON string
    parsed = json.loads(result)
    assert parsed["success"] is True
    assert "Mock result: test" in parsed["content"]


async def test_tool_handler_error_returns_json():
    """Tool handler returns error as JSON."""
    registry = create_test_registry()
    container = Container()
    context = create_mock_context()

    factory = ToolFactory(registry, container)
    tool = factory.create_tool("failing_tool", context)

    result = await tool["handler"]({})

    parsed = json.loads(result)
    assert parsed["success"] is False
    assert "Tool execution failed" in parsed["error"]


async def test_tool_handler_checks_cancellation():
    """Tool handler checks context.check_cancelled before execution."""
    registry = create_test_registry()
    container = Container()
    context = create_mock_context()

    factory = ToolFactory(registry, container)
    tool = factory.create_tool("mock_tool", context)

    await tool["handler"]({"input": "test"})

    # check_cancelled should have been called
    context.check_cancelled.assert_called_once()


# =============================================================================
# Create Simple Tool Helper Tests
# =============================================================================

async def test_create_simple_tool_helper():
    """create_simple_tool helper creates valid factory."""
    async def my_handler(params: Dict[str, Any], context: ExecutionContext) -> str:
        return f"Hello, {params.get('name', 'World')}!"

    factory_func = create_simple_tool(
        name="greet",
        description="Greet someone",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
        },
        handler=my_handler,
    )

    context = create_mock_context()
    container = Container()

    # Use factory to create tool instance
    tool_instance = factory_func(context, container)

    assert tool_instance.name == "greet"
    assert tool_instance.description == "Greet someone"

    # Execute should work
    result = await tool_instance.execute({"name": "Alice"}, context)
    assert result.success is True
    assert "Hello, Alice!" in result.content


async def test_create_simple_tool_returns_tool_result():
    """create_simple_tool handles handler returning ToolResult."""
    async def handler_with_result(params, context) -> ToolResult:
        return ToolResult(content="Direct result", success=True, error=None)

    factory_func = create_simple_tool(
        name="direct",
        description="Direct result handler",
        parameters={"type": "object", "properties": {}},
        handler=handler_with_result,
    )

    context = create_mock_context()
    container = Container()
    tool = factory_func(context, container)

    result = await tool.execute({}, context)
    assert result.content == "Direct result"
    assert result.success is True


async def test_create_simple_tool_handles_error():
    """create_simple_tool catches handler exceptions."""
    async def failing_handler(params, context):
        raise ValueError("Handler failed!")

    factory_func = create_simple_tool(
        name="failing",
        description="Failing handler",
        parameters={"type": "object", "properties": {}},
        handler=failing_handler,
    )

    context = create_mock_context()
    container = Container()
    tool = factory_func(context, container)

    result = await tool.execute({}, context)
    assert result.success is False
    assert "Handler failed!" in result.error


# =============================================================================
# Utility Method Tests
# =============================================================================

def test_list_available_tools():
    """list_available_tools returns all tool names."""
    registry = create_test_registry()
    container = Container()

    factory = ToolFactory(registry, container)
    tools = factory.list_available_tools()

    assert "mock_tool" in tools
    assert "class_tool" in tools


def test_get_tool_info():
    """get_tool_info returns tool plugin definition."""
    registry = create_test_registry()
    container = Container()

    factory = ToolFactory(registry, container)
    info = factory.get_tool_info("mock_tool")

    assert info is not None
    assert info["name"] == "mock_tool"
    assert "factory" in info


def test_get_tool_info_not_found():
    """get_tool_info returns None for unknown tool."""
    registry = PluginRegistry()
    container = Container()

    factory = ToolFactory(registry, container)
    info = factory.get_tool_info("nonexistent")

    assert info is None


# =============================================================================
# Error Handling Tests
# =============================================================================

def test_create_tool_missing_factory_and_class():
    """Handles plugin missing both factory and class."""
    registry = PluginRegistry()
    registry._tools["broken"] = {
        "type": "tool",
        "name": "broken",
        "description": "Missing factory and class",
    }
    container = Container()
    context = create_mock_context()

    factory = ToolFactory(registry, container)
    tool = factory.create_tool("broken", context)

    # Should return None, not crash
    assert tool is None
