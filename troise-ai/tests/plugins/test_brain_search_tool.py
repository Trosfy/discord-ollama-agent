"""Unit tests for Brain Search Tool."""
import pytest
import json
from unittest.mock import AsyncMock

from app.plugins.tools.brain_search.tool import BrainSearchTool, create_brain_search_tool
from app.core.context import ExecutionContext
from app.core.container import Container
from app.core.interfaces.services import IBrainService


# =============================================================================
# Mock Classes
# =============================================================================

class MockBrainService:
    """Mock brain service for testing."""
    def __init__(self, results: list = None):
        self._results = results or []
        self.search_calls = []

    async def search(self, query: str, limit: int = 5) -> list:
        self.search_calls.append({"query": query, "limit": limit})
        return self._results


def create_mock_context() -> ExecutionContext:
    """Create a mock execution context."""
    return ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
        websocket=None,
    )


def create_test_container(brain_service: IBrainService = None) -> Container:
    """Create a container with optional brain service."""
    container = Container()
    if brain_service:
        container.register(IBrainService, brain_service)
    return container


# =============================================================================
# Basic Execution Tests
# =============================================================================

async def test_execute_search():
    """BrainSearchTool searches using brain service."""
    brain_service = MockBrainService([
        {
            "path": "notes/test.md",
            "title": "Test Note",
            "score": 0.95,
            "snippet": "This is a test note about something important",
            "tags": ["test", "important"],
        }
    ])
    context = create_mock_context()
    container = create_test_container(brain_service)

    tool = BrainSearchTool(context=context, container=container, brain_service=brain_service)
    result = await tool.execute({"query": "test query"}, context)

    assert result.success is True
    assert brain_service.search_calls[0]["query"] == "test query"

    # Result should be JSON
    data = json.loads(result.content)
    assert data["query"] == "test query"
    assert data["count"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["title"] == "Test Note"


async def test_execute_respects_limit():
    """BrainSearchTool passes limit parameter to search."""
    brain_service = MockBrainService([])
    context = create_mock_context()
    container = create_test_container(brain_service)

    tool = BrainSearchTool(context=context, container=container, brain_service=brain_service)
    await tool.execute({"query": "test", "limit": 10}, context)

    assert brain_service.search_calls[0]["limit"] == 10


async def test_execute_default_limit():
    """BrainSearchTool uses default limit of 5."""
    brain_service = MockBrainService([])
    context = create_mock_context()
    container = create_test_container(brain_service)

    tool = BrainSearchTool(context=context, container=container, brain_service=brain_service)
    await tool.execute({"query": "test"}, context)

    assert brain_service.search_calls[0]["limit"] == 5


# =============================================================================
# Error Handling Tests
# =============================================================================

async def test_execute_missing_query():
    """BrainSearchTool returns error when query is missing."""
    brain_service = MockBrainService([])
    context = create_mock_context()
    container = create_test_container(brain_service)

    tool = BrainSearchTool(context=context, container=container, brain_service=brain_service)
    result = await tool.execute({}, context)

    assert result.success is False
    assert "required" in result.error.lower()


async def test_execute_no_brain_service():
    """BrainSearchTool returns error gracefully when no brain service."""
    context = create_mock_context()
    container = create_test_container()  # No brain service registered

    tool = BrainSearchTool(context=context, container=container, brain_service=None)
    result = await tool.execute({"query": "test"}, context)

    assert result.success is False
    data = json.loads(result.content)
    assert "not available" in data["error"].lower() or "not configured" in data["hint"].lower()


async def test_execute_search_exception():
    """BrainSearchTool handles search exceptions gracefully."""
    brain_service = MockBrainService([])
    brain_service.search = AsyncMock(side_effect=RuntimeError("Search failed"))
    context = create_mock_context()
    container = create_test_container(brain_service)

    tool = BrainSearchTool(context=context, container=container, brain_service=brain_service)
    result = await tool.execute({"query": "test"}, context)

    assert result.success is False
    data = json.loads(result.content)
    assert "Search failed" in data["error"]


# =============================================================================
# Result Formatting Tests
# =============================================================================

async def test_formats_results_correctly():
    """BrainSearchTool formats search results correctly."""
    brain_service = MockBrainService([
        {
            "path": "notes/project.md",
            "title": "Project Notes",
            "score": 0.88,
            "snippet": "Details about the project implementation...",
            "tags": ["project", "dev"],
            "extra_field": "should be ignored",  # Extra fields ignored
        }
    ])
    context = create_mock_context()
    container = create_test_container(brain_service)

    tool = BrainSearchTool(context=context, container=container, brain_service=brain_service)
    result = await tool.execute({"query": "project"}, context)

    data = json.loads(result.content)
    r = data["results"][0]

    assert r["path"] == "notes/project.md"
    assert r["title"] == "Project Notes"
    assert r["score"] == 0.88
    assert "snippet" in r
    assert r["tags"] == ["project", "dev"]
    assert "extra_field" not in r


async def test_truncates_long_snippets():
    """BrainSearchTool truncates snippets to 500 chars."""
    long_snippet = "x" * 1000
    brain_service = MockBrainService([
        {
            "path": "notes/long.md",
            "title": "Long Note",
            "score": 0.5,
            "snippet": long_snippet,
            "tags": [],
        }
    ])
    context = create_mock_context()
    container = create_test_container(brain_service)

    tool = BrainSearchTool(context=context, container=container, brain_service=brain_service)
    result = await tool.execute({"query": "test"}, context)

    data = json.loads(result.content)
    assert len(data["results"][0]["snippet"]) == 500


async def test_handles_missing_fields():
    """BrainSearchTool handles results with missing fields."""
    brain_service = MockBrainService([
        {
            "path": "notes/minimal.md",
            # Missing: title, score, snippet, tags
        }
    ])
    context = create_mock_context()
    container = create_test_container(brain_service)

    tool = BrainSearchTool(context=context, container=container, brain_service=brain_service)
    result = await tool.execute({"query": "test"}, context)

    assert result.success is True
    data = json.loads(result.content)
    r = data["results"][0]
    assert r["title"] == "Untitled"
    assert r["score"] == 0.0
    assert r["snippet"] == ""
    assert r["tags"] == []


# =============================================================================
# Tool Schema Tests
# =============================================================================

def test_tool_schema():
    """BrainSearchTool has correct schema."""
    context = create_mock_context()
    container = create_test_container()

    tool = BrainSearchTool(context=context, container=container)
    schema = tool.to_schema()

    assert schema["name"] == "brain_search"
    assert "parameters" in schema
    assert "query" in schema["parameters"]["properties"]
    assert "query" in schema["parameters"]["required"]


def test_tool_name():
    """BrainSearchTool has correct name attribute."""
    assert BrainSearchTool.name == "brain_search"


def test_tool_description():
    """BrainSearchTool has meaningful description."""
    desc = BrainSearchTool.description.lower()
    assert "search" in desc
    assert "knowledge" in desc or "obsidian" in desc


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_brain_search_tool_factory():
    """create_brain_search_tool returns configured tool instance."""
    brain_service = MockBrainService([])
    context = create_mock_context()
    container = create_test_container(brain_service)

    tool = create_brain_search_tool(context, container)

    assert isinstance(tool, BrainSearchTool)


def test_factory_resolves_brain_service():
    """Factory resolves brain service from container."""
    brain_service = MockBrainService([])
    context = create_mock_context()
    container = create_test_container(brain_service)

    tool = create_brain_search_tool(context, container)

    assert tool._brain_service is brain_service


async def test_factory_created_tool_works():
    """Tool created by factory works correctly."""
    brain_service = MockBrainService([{"path": "test.md", "title": "Test", "score": 0.9}])
    context = create_mock_context()
    container = create_test_container(brain_service)

    tool = create_brain_search_tool(context, container)
    result = await tool.execute({"query": "test"}, context)

    assert result.success is True


# =============================================================================
# Service Resolution Tests
# =============================================================================

async def test_resolves_brain_service_lazily():
    """BrainSearchTool resolves brain service lazily from container."""
    brain_service = MockBrainService([{"path": "t.md", "title": "T"}])
    context = create_mock_context()
    container = create_test_container()  # No service initially

    tool = BrainSearchTool(context=context, container=container, brain_service=None)

    # Register service after tool creation
    container.register(IBrainService, brain_service)

    result = await tool.execute({"query": "test"}, context)

    assert result.success is True
