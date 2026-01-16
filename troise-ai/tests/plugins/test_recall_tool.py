"""Unit tests for Recall Tool."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.plugins.tools.recall import RecallTool, create_recall_tool
from app.core.context import ExecutionContext, UserProfile
from app.core.container import Container


# =============================================================================
# Mock Memory Service
# =============================================================================

class MockUserMemory:
    """Mock memory service implementing IUserMemory."""

    def __init__(self):
        self._memories: List[Dict] = []

    async def get(self, user_id: str, category: str, key: str) -> Optional[Dict]:
        for m in self._memories:
            if m["user_id"] == user_id and m["category"] == category and m["key"] == key:
                return m
        return None

    async def query(self, user_id: str, category: str = None) -> List[Dict]:
        result = [m for m in self._memories if m["user_id"] == user_id]
        if category:
            result = [m for m in result if m["category"] == category]
        return result

    async def get_all(self, user_id: str) -> List[Dict]:
        return [m for m in self._memories if m["user_id"] == user_id]

    def add_memory(
        self,
        user_id: str,
        category: str,
        key: str,
        value: str,
        confidence: float = 0.5,
        source: str = "learned",
        learned_by: str = None,
        updated_at: str = None,
    ):
        """Helper to add test memories."""
        self._memories.append({
            "user_id": user_id,
            "category": category,
            "key": key,
            "value": value,
            "confidence": confidence,
            "source": source,
            "learned_by": learned_by,
            "updated_at": updated_at,
        })


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
    )


@pytest.fixture
def mock_container():
    """Create mock DI container."""
    return Container()


@pytest.fixture
def mock_memory():
    """Create mock memory service with test data."""
    memory = MockUserMemory()
    memory.add_memory(
        user_id="test-user",
        category="expertise",
        key="python",
        value="Expert Python developer",
        confidence=0.9,
        learned_by="chat-agent",
    )
    memory.add_memory(
        user_id="test-user",
        category="expertise",
        key="rust",
        value="Learning Rust",
        confidence=0.5,
        learned_by="code-agent",
    )
    memory.add_memory(
        user_id="test-user",
        category="preference",
        key="concise",
        value="Prefers brief answers",
        confidence=0.8,
    )
    memory.add_memory(
        user_id="test-user",
        category="fact",
        key="timezone",
        value="UTC",
        confidence=0.95,
    )
    return memory


@pytest.fixture
def recall_tool(mock_context, mock_container, mock_memory):
    """Create recall tool with mock dependencies."""
    return RecallTool(
        context=mock_context,
        container=mock_container,
        memory_service=mock_memory,
    )


# =============================================================================
# Retrieve All Memories Tests
# =============================================================================

async def test_execute_all_memories(recall_tool, mock_context):
    """execute() returns all memories when no filter."""
    params = {}

    result = await recall_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["count"] == 4
    assert len(content["memories"]) == 4
    # Should be grouped by category
    assert "by_category" in content


async def test_execute_returns_sorted_by_confidence(recall_tool, mock_context):
    """execute() returns memories sorted by confidence (highest first)."""
    params = {}

    result = await recall_tool.execute(params, mock_context)

    content = json.loads(result.content)
    memories = content["memories"]

    # Check descending confidence order
    confidences = [m["confidence"] for m in memories]
    assert confidences == sorted(confidences, reverse=True)


async def test_execute_groups_by_category(recall_tool, mock_context):
    """execute() groups memories by category."""
    params = {}

    result = await recall_tool.execute(params, mock_context)

    content = json.loads(result.content)
    by_category = content["by_category"]

    assert "expertise" in by_category
    assert "preference" in by_category
    assert "fact" in by_category
    assert len(by_category["expertise"]) == 2  # python, rust


# =============================================================================
# Filter by Category Tests
# =============================================================================

async def test_execute_filter_by_category(recall_tool, mock_context):
    """execute() filters by category."""
    params = {"category": "expertise"}

    result = await recall_tool.execute(params, mock_context)

    content = json.loads(result.content)
    assert content["count"] == 2
    for mem in content["memories"]:
        assert mem["category"] == "expertise"


async def test_execute_filter_preference(recall_tool, mock_context):
    """execute() filters preference category."""
    params = {"category": "preference"}

    result = await recall_tool.execute(params, mock_context)

    content = json.loads(result.content)
    assert content["count"] == 1
    assert content["memories"][0]["key"] == "concise"


async def test_execute_invalid_category(recall_tool, mock_context):
    """execute() returns error for invalid category."""
    params = {"category": "invalid_category"}

    result = await recall_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "invalid category" in content["error"].lower()
    assert content["memories"] == []


# =============================================================================
# Filter by Key Tests
# =============================================================================

async def test_execute_filter_by_category_and_key(recall_tool, mock_context):
    """execute() gets specific memory by category and key."""
    params = {
        "category": "expertise",
        "key": "python",
    }

    result = await recall_tool.execute(params, mock_context)

    content = json.loads(result.content)
    assert content["count"] == 1
    assert content["memories"][0]["key"] == "python"
    assert content["memories"][0]["value"] == "Expert Python developer"


async def test_execute_key_not_found(recall_tool, mock_context):
    """execute() returns empty list for missing key."""
    params = {
        "category": "expertise",
        "key": "nonexistent",
    }

    result = await recall_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["count"] == 0
    assert content["memories"] == []


# =============================================================================
# Minimum Confidence Filter Tests
# =============================================================================

async def test_execute_min_confidence_filter(recall_tool, mock_context):
    """execute() filters by minimum confidence."""
    params = {"min_confidence": 0.8}

    result = await recall_tool.execute(params, mock_context)

    content = json.loads(result.content)
    # Should exclude rust (0.5)
    for mem in content["memories"]:
        assert mem["confidence"] >= 0.8


async def test_execute_high_min_confidence(recall_tool, mock_context):
    """execute() with high min_confidence returns few results."""
    params = {"min_confidence": 0.95}

    result = await recall_tool.execute(params, mock_context)

    content = json.loads(result.content)
    assert content["count"] == 1  # Only timezone has 0.95


async def test_execute_min_confidence_zero(recall_tool, mock_context):
    """execute() with min_confidence=0 returns all."""
    params = {"min_confidence": 0.0}

    result = await recall_tool.execute(params, mock_context)

    content = json.loads(result.content)
    assert content["count"] == 4


async def test_execute_category_and_min_confidence(recall_tool, mock_context):
    """execute() combines category and min_confidence filters."""
    params = {
        "category": "expertise",
        "min_confidence": 0.7,
    }

    result = await recall_tool.execute(params, mock_context)

    content = json.loads(result.content)
    assert content["count"] == 1  # Only python (0.9)
    assert content["memories"][0]["key"] == "python"


# =============================================================================
# Memory Format Tests
# =============================================================================

async def test_execute_memory_format(recall_tool, mock_context):
    """execute() returns properly formatted memories."""
    params = {"category": "expertise", "key": "python"}

    result = await recall_tool.execute(params, mock_context)

    content = json.loads(result.content)
    memory = content["memories"][0]

    assert "category" in memory
    assert "key" in memory
    assert "value" in memory
    assert "confidence" in memory
    assert "source" in memory
    assert "learned_by" in memory


async def test_execute_response_includes_filter(recall_tool, mock_context):
    """execute() includes filter info in response."""
    params = {
        "category": "expertise",
        "min_confidence": 0.5,
    }

    result = await recall_tool.execute(params, mock_context)

    content = json.loads(result.content)
    assert content["filter"]["category"] == "expertise"
    assert content["filter"]["min_confidence"] == 0.5


# =============================================================================
# No Memory Service Tests
# =============================================================================

async def test_execute_no_memory_service(mock_context, mock_container):
    """execute() returns error when no memory service."""
    tool = RecallTool(
        context=mock_context,
        container=mock_container,
        memory_service=None,
    )

    params = {}

    result = await tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "not available" in content["error"].lower()
    assert content["memories"] == []


async def test_execute_memory_service_error(mock_context, mock_container):
    """execute() handles memory service errors."""
    error_memory = AsyncMock()
    error_memory.get_all = AsyncMock(side_effect=Exception("Database error"))

    tool = RecallTool(
        context=mock_context,
        container=mock_container,
        memory_service=error_memory,
    )

    params = {}

    result = await tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "error" in content


# =============================================================================
# Empty Results Tests
# =============================================================================

async def test_execute_empty_category(mock_context, mock_container):
    """execute() returns empty for category with no memories."""
    memory = MockUserMemory()
    memory.add_memory(
        user_id="test-user",
        category="expertise",
        key="python",
        value="test",
        confidence=0.5,
    )

    tool = RecallTool(
        context=mock_context,
        container=mock_container,
        memory_service=memory,
    )

    params = {"category": "project"}  # No project memories

    result = await tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["count"] == 0
    assert content["memories"] == []


async def test_execute_no_memories_for_user(mock_context, mock_container):
    """execute() returns empty when user has no memories."""
    memory = MockUserMemory()  # Empty

    tool = RecallTool(
        context=mock_context,
        container=mock_container,
        memory_service=memory,
    )

    params = {}

    result = await tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["count"] == 0


# =============================================================================
# User Context Tests
# =============================================================================

async def test_execute_uses_user_id_from_profile(mock_context, mock_container):
    """execute() uses user_id from user profile."""
    memory = MockUserMemory()
    memory.add_memory(
        user_id="specific-user-123",
        category="fact",
        key="test",
        value="value",
        confidence=0.5,
    )

    mock_context.user_profile = UserProfile(user_id="specific-user-123")

    tool = RecallTool(
        context=mock_context,
        container=mock_container,
        memory_service=memory,
    )

    params = {}

    result = await tool.execute(params, mock_context)

    content = json.loads(result.content)
    assert content["count"] == 1


async def test_execute_default_user_id(mock_context, mock_container):
    """execute() uses 'default' when no user profile."""
    memory = MockUserMemory()
    memory.add_memory(
        user_id="default",
        category="fact",
        key="test",
        value="value",
        confidence=0.5,
    )

    mock_context.user_profile = None

    tool = RecallTool(
        context=mock_context,
        container=mock_container,
        memory_service=memory,
    )

    params = {}

    result = await tool.execute(params, mock_context)

    content = json.loads(result.content)
    assert content["count"] == 1


# =============================================================================
# Valid Categories Tests
# =============================================================================

@pytest.mark.parametrize("category", ["expertise", "preference", "project", "fact"])
async def test_execute_valid_categories(mock_context, mock_container, category):
    """execute() accepts all valid categories."""
    memory = MockUserMemory()
    memory.add_memory(
        user_id="test-user",
        category=category,
        key="test",
        value="value",
        confidence=0.5,
    )

    tool = RecallTool(
        context=mock_context,
        container=mock_container,
        memory_service=memory,
    )

    params = {"category": category}

    result = await tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["count"] == 1


# =============================================================================
# Schema Tests
# =============================================================================

def test_to_schema(recall_tool):
    """to_schema() returns correct tool schema."""
    schema = recall_tool.to_schema()

    assert schema["name"] == "recall"
    assert "description" in schema
    assert "parameters" in schema
    assert schema["parameters"]["type"] == "object"

    props = schema["parameters"]["properties"]
    assert "category" in props
    assert "key" in props
    assert "min_confidence" in props

    # Required should be empty (all optional)
    assert schema["parameters"]["required"] == []


def test_tool_name():
    """Tool has correct name attribute."""
    assert RecallTool.name == "recall"


def test_tool_description():
    """Tool has description."""
    assert RecallTool.description
    assert "recall" in RecallTool.description.lower() or "retrieve" in RecallTool.description.lower()


def test_tool_parameters_schema():
    """Tool parameters schema is valid."""
    params = RecallTool.parameters

    assert params["type"] == "object"
    assert "properties" in params
    assert "category" in params["properties"]
    # Category is optional, should have enum
    assert "enum" in params["properties"]["category"]


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_recall_tool_factory():
    """create_recall_tool() creates tool instance."""
    context = ExecutionContext(
        user_id="test",
        session_id="test",
        interface="web",
    )
    container = Container()

    tool = create_recall_tool(context, container)

    assert isinstance(tool, RecallTool)
    assert tool._context == context
    assert tool._container == container


def test_create_recall_tool_resolves_memory():
    """create_recall_tool() tries to resolve memory service."""
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

    tool = create_recall_tool(context, container)

    assert tool._memory_service == mock_memory
