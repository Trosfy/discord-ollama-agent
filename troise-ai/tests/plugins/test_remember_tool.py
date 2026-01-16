"""Unit tests for Remember Tool."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.plugins.tools.remember import RememberTool, create_remember_tool
from app.core.context import ExecutionContext, UserProfile
from app.core.container import Container


# =============================================================================
# Mock Memory Service
# =============================================================================

class MockUserMemory:
    """Mock memory service implementing IUserMemory."""

    def __init__(self):
        self._memories: Dict[str, Dict] = {}
        self._put_calls: List[Dict] = []

    async def put(
        self,
        user_id: str,
        category: str,
        key: str,
        value: str,
        confidence: float = 0.5,
        source: str = "learned",
        learned_by: str = None,
        ttl: int = None,
    ) -> None:
        self._put_calls.append({
            "user_id": user_id,
            "category": category,
            "key": key,
            "value": value,
            "confidence": confidence,
            "source": source,
            "learned_by": learned_by,
        })
        mem_key = f"{user_id}:{category}:{key}"
        self._memories[mem_key] = {
            "user_id": user_id,
            "category": category,
            "key": key,
            "value": value,
            "confidence": confidence,
        }

    async def get(self, user_id: str, category: str, key: str) -> Optional[Dict]:
        return self._memories.get(f"{user_id}:{category}:{key}")


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_context():
    """Create mock execution context."""
    return ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
        user_profile=UserProfile(user_id="test-user"),
        agent_name="test-agent",
    )


@pytest.fixture
def mock_container():
    """Create mock DI container."""
    return Container()


@pytest.fixture
def mock_memory():
    """Create mock memory service."""
    return MockUserMemory()


@pytest.fixture
def remember_tool(mock_context, mock_container, mock_memory):
    """Create remember tool with mock dependencies."""
    return RememberTool(
        context=mock_context,
        container=mock_container,
        memory_service=mock_memory,
    )


# =============================================================================
# Successful Storage Tests
# =============================================================================

async def test_execute_stores_memory(remember_tool, mock_memory, mock_context):
    """execute() stores memory with all parameters."""
    params = {
        "category": "expertise",
        "key": "python",
        "value": "User is proficient in Python",
        "confidence": 0.8,
        "evidence": "Mentioned in conversation",
    }

    result = await remember_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["stored"] is True
    assert content["category"] == "expertise"
    assert content["key"] == "python"
    assert content["confidence"] == 0.8

    # Check memory service was called
    assert len(mock_memory._put_calls) == 1
    call = mock_memory._put_calls[0]
    assert call["category"] == "expertise"
    assert call["key"] == "python"
    assert call["value"] == "User is proficient in Python"
    assert call["confidence"] == 0.8


async def test_execute_default_confidence(remember_tool, mock_memory, mock_context):
    """execute() uses default confidence 0.5."""
    params = {
        "category": "fact",
        "key": "timezone",
        "value": "UTC",
    }

    result = await remember_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["confidence"] == 0.5


async def test_execute_high_confidence_hint(remember_tool, mock_memory, mock_context):
    """execute() gives promotion hint for high confidence."""
    params = {
        "category": "expertise",
        "key": "rust",
        "value": "Expert Rust developer",
        "confidence": 0.95,
    }

    result = await remember_tool.execute(params, mock_context)

    content = json.loads(result.content)
    assert "promotion" in content["hint"].lower() or "permanent" in content["hint"].lower()


async def test_execute_medium_confidence_hint(remember_tool, mock_memory, mock_context):
    """execute() gives evidence hint for medium confidence."""
    params = {
        "category": "expertise",
        "key": "go",
        "value": "Knows Go",
        "confidence": 0.75,
    }

    result = await remember_tool.execute(params, mock_context)

    content = json.loads(result.content)
    assert "evidence" in content["hint"].lower() or "increase" in content["hint"].lower()


async def test_execute_tracks_agent_name(remember_tool, mock_memory, mock_context):
    """execute() stores agent name in learned_by."""
    params = {
        "category": "preference",
        "key": "concise",
        "value": "Prefers brief answers",
    }

    await remember_tool.execute(params, mock_context)

    call = mock_memory._put_calls[0]
    assert call["learned_by"] == "test-agent"


# =============================================================================
# Validation Tests
# =============================================================================

async def test_execute_missing_category(remember_tool, mock_context):
    """execute() returns error for missing category."""
    params = {
        "key": "test",
        "value": "test value",
    }

    result = await remember_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert content["stored"] is False
    assert "required" in content["error"].lower()


async def test_execute_missing_key(remember_tool, mock_context):
    """execute() returns error for missing key."""
    params = {
        "category": "expertise",
        "value": "test value",
    }

    result = await remember_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert content["stored"] is False


async def test_execute_missing_value(remember_tool, mock_context):
    """execute() returns error for missing value."""
    params = {
        "category": "expertise",
        "key": "test",
    }

    result = await remember_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert content["stored"] is False


async def test_execute_invalid_category(remember_tool, mock_context):
    """execute() returns error for invalid category."""
    params = {
        "category": "invalid_category",
        "key": "test",
        "value": "test value",
    }

    result = await remember_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "invalid category" in content["error"].lower()


async def test_execute_confidence_too_low(remember_tool, mock_context):
    """execute() returns error for confidence < 0."""
    params = {
        "category": "expertise",
        "key": "test",
        "value": "test value",
        "confidence": -0.1,
    }

    result = await remember_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "confidence" in content["error"].lower()


async def test_execute_confidence_too_high(remember_tool, mock_context):
    """execute() returns error for confidence > 1."""
    params = {
        "category": "expertise",
        "key": "test",
        "value": "test value",
        "confidence": 1.5,
    }

    result = await remember_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "confidence" in content["error"].lower()


# =============================================================================
# Valid Categories Tests
# =============================================================================

@pytest.mark.parametrize("category", ["expertise", "preference", "project", "fact"])
async def test_execute_valid_categories(remember_tool, mock_memory, mock_context, category):
    """execute() accepts all valid categories."""
    params = {
        "category": category,
        "key": "test_key",
        "value": "test value",
    }

    result = await remember_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["stored"] is True
    assert content["category"] == category


# =============================================================================
# Memory Service Error Tests
# =============================================================================

async def test_execute_no_memory_service(mock_context, mock_container):
    """execute() returns error when no memory service."""
    tool = RememberTool(
        context=mock_context,
        container=mock_container,
        memory_service=None,
    )

    params = {
        "category": "expertise",
        "key": "test",
        "value": "test value",
    }

    result = await tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "not available" in content["error"].lower()


async def test_execute_memory_service_error(mock_context, mock_container):
    """execute() handles memory service errors."""
    error_memory = AsyncMock()
    error_memory.put = AsyncMock(side_effect=Exception("Database error"))

    tool = RememberTool(
        context=mock_context,
        container=mock_container,
        memory_service=error_memory,
    )

    params = {
        "category": "expertise",
        "key": "test",
        "value": "test value",
    }

    result = await tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "error" in content


# =============================================================================
# User Context Tests
# =============================================================================

async def test_execute_uses_user_id_from_profile(mock_context, mock_container, mock_memory):
    """execute() uses user_id from user profile."""
    mock_context.user_profile = UserProfile(user_id="specific-user-123")

    tool = RememberTool(
        context=mock_context,
        container=mock_container,
        memory_service=mock_memory,
    )

    params = {
        "category": "fact",
        "key": "test",
        "value": "value",
    }

    await tool.execute(params, mock_context)

    call = mock_memory._put_calls[0]
    assert call["user_id"] == "specific-user-123"


async def test_execute_default_user_id(mock_context, mock_container, mock_memory):
    """execute() uses 'default' when no user profile."""
    mock_context.user_profile = None

    tool = RememberTool(
        context=mock_context,
        container=mock_container,
        memory_service=mock_memory,
    )

    params = {
        "category": "fact",
        "key": "test",
        "value": "value",
    }

    await tool.execute(params, mock_context)

    call = mock_memory._put_calls[0]
    assert call["user_id"] == "default"


# =============================================================================
# Schema Tests
# =============================================================================

def test_to_schema(remember_tool):
    """to_schema() returns correct tool schema."""
    schema = remember_tool.to_schema()

    assert schema["name"] == "remember"
    assert "description" in schema
    assert "parameters" in schema
    assert schema["parameters"]["type"] == "object"

    props = schema["parameters"]["properties"]
    assert "category" in props
    assert "key" in props
    assert "value" in props
    assert "confidence" in props
    assert "evidence" in props

    # Check required fields
    assert "category" in schema["parameters"]["required"]
    assert "key" in schema["parameters"]["required"]
    assert "value" in schema["parameters"]["required"]


def test_tool_name():
    """Tool has correct name attribute."""
    assert RememberTool.name == "remember"


def test_tool_description():
    """Tool has description."""
    assert RememberTool.description
    assert "remember" in RememberTool.description.lower() or "store" in RememberTool.description.lower()


def test_tool_parameters_schema():
    """Tool parameters schema is valid."""
    params = RememberTool.parameters

    assert params["type"] == "object"
    assert "properties" in params
    assert "category" in params["properties"]
    assert "enum" in params["properties"]["category"]


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_remember_tool_factory():
    """create_remember_tool() creates tool instance."""
    context = ExecutionContext(
        user_id="test",
        session_id="test",
        interface="web",
    )
    container = Container()

    tool = create_remember_tool(context, container)

    assert isinstance(tool, RememberTool)
    assert tool._context == context
    assert tool._container == container


def test_create_remember_tool_resolves_memory():
    """create_remember_tool() tries to resolve memory service."""
    context = ExecutionContext(
        user_id="test",
        session_id="test",
        interface="web",
    )
    container = Container()

    # Register mock memory service
    from app.core.interfaces.services import IUserMemory
    mock_memory = MockUserMemory()
    container.register(IUserMemory, mock_memory)

    tool = create_remember_tool(context, container)

    assert tool._memory_service == mock_memory
