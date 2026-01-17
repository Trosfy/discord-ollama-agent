"""Unit tests for Web Search Tool (SearXNG)."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.plugins.tools.web_search import WebSearchTool, create_web_search_tool
from app.core.context import ExecutionContext, UserProfile
from app.core.container import Container


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
def web_search_tool(mock_context, mock_container):
    """Create web search tool with mock dependencies."""
    return WebSearchTool(
        context=mock_context,
        container=mock_container,
        searxng_host="http://localhost:8080",
    )


def _mock_searxng_response(results: list):
    """Create mock SearXNG JSON response."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"results": results})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock()
    return mock_response


def _mock_instant_answer_response(data: dict):
    """Create mock DuckDuckGo instant answer response."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=data)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock()
    return mock_response


# =============================================================================
# Input Validation Tests
# =============================================================================

async def test_execute_missing_query(web_search_tool, mock_context):
    """execute() returns error when no query provided."""
    params = {}

    result = await web_search_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "required" in content["error"].lower()


async def test_execute_empty_query(web_search_tool, mock_context):
    """execute() returns error for empty query."""
    params = {"query": "   "}

    result = await web_search_tool.execute(params, mock_context)

    assert result.success is False


# =============================================================================
# SearXNG Search Tests
# =============================================================================

async def test_execute_returns_results(web_search_tool, mock_context):
    """execute() returns search results from SearXNG."""
    searxng_results = [
        {"title": "Example Page 1", "url": "https://example.com/page1", "content": "First result snippet", "engine": "google"},
        {"title": "Example Page 2", "url": "https://example.com/page2", "content": "Second result snippet", "engine": "bing"},
    ]

    mock_searxng = _mock_searxng_response(searxng_results)

    mock_session = MagicMock()
    # SearXNG is called first; DuckDuckGo not called when SearXNG succeeds
    mock_session.get = MagicMock(return_value=mock_searxng)
    mock_session.closed = False
    web_search_tool._session = mock_session

    params = {"query": "test search"}

    result = await web_search_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["query"] == "test search"
    assert content["count"] == 2
    assert len(content["results"]) == 2
    assert content["results"][0]["title"] == "Example Page 1"
    assert content["results"][0]["engine"] == "google"
    # DuckDuckGo not called when SearXNG returns results
    assert content["instant_answer"] is None


async def test_execute_with_instant_answer(web_search_tool, mock_context):
    """execute() falls back to DuckDuckGo instant answer when SearXNG returns no results."""
    mock_searxng = _mock_searxng_response([])  # Empty results triggers fallback
    mock_instant = _mock_instant_answer_response({
        "Heading": "Python",
        "Abstract": "Python is a programming language.",
        "AbstractSource": "Wikipedia",
        "AbstractURL": "https://en.wikipedia.org/wiki/Python",
    })

    mock_session = MagicMock()
    # SearXNG called first (returns empty), then DuckDuckGo fallback
    mock_session.get = MagicMock(side_effect=[mock_searxng, mock_instant])
    mock_session.closed = False
    web_search_tool._session = mock_session

    params = {"query": "Python programming"}

    result = await web_search_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["instant_answer"] is not None
    assert "Python" in content["instant_answer"]["title"]
    assert "programming language" in content["instant_answer"]["text"]


async def test_execute_no_results(web_search_tool, mock_context):
    """execute() handles no results gracefully."""
    mock_searxng = _mock_searxng_response([])
    mock_instant = _mock_instant_answer_response({})

    mock_session = MagicMock()
    # SearXNG first (empty), then DuckDuckGo fallback (also empty)
    mock_session.get = MagicMock(side_effect=[mock_searxng, mock_instant])
    mock_session.closed = False
    web_search_tool._session = mock_session

    params = {"query": "xyznonexistentquery123"}

    result = await web_search_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["count"] == 0
    assert "No results found" in content.get("message", "")


async def test_execute_includes_engine_info(web_search_tool, mock_context):
    """execute() includes search engine info in results."""
    searxng_results = [
        {"title": "Result 1", "url": "https://ex1.com", "content": "Snippet", "engine": "google"},
        {"title": "Result 2", "url": "https://ex2.com", "content": "Snippet", "engine": "duckduckgo"},
    ]

    mock_searxng = _mock_searxng_response(searxng_results)

    mock_session = MagicMock()
    # SearXNG succeeds, no DuckDuckGo fallback needed
    mock_session.get = MagicMock(return_value=mock_searxng)
    mock_session.closed = False
    web_search_tool._session = mock_session

    params = {"query": "test"}

    result = await web_search_tool.execute(params, mock_context)

    content = json.loads(result.content)
    assert content["results"][0]["engine"] == "google"
    assert content["results"][1]["engine"] == "duckduckgo"


# =============================================================================
# Parameter Tests
# =============================================================================

async def test_execute_respects_num_results(web_search_tool, mock_context):
    """execute() respects num_results parameter."""
    searxng_results = [
        {"title": f"Result {i}", "url": f"https://ex{i}.com", "content": f"Snippet {i}", "engine": "google"}
        for i in range(5)
    ]

    mock_searxng = _mock_searxng_response(searxng_results)

    mock_session = MagicMock()
    # SearXNG succeeds, no DuckDuckGo fallback
    mock_session.get = MagicMock(return_value=mock_searxng)
    mock_session.closed = False
    web_search_tool._session = mock_session

    params = {"query": "test", "num_results": 2}

    result = await web_search_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["count"] <= 2


async def test_execute_max_num_results_capped(web_search_tool, mock_context):
    """execute() caps num_results at 10."""
    mock_searxng = _mock_searxng_response([])
    mock_instant = _mock_instant_answer_response({})

    mock_session = MagicMock()
    # SearXNG first (empty), then DuckDuckGo fallback (empty)
    mock_session.get = MagicMock(side_effect=[mock_searxng, mock_instant])
    mock_session.closed = False
    web_search_tool._session = mock_session

    # Request 100, should be capped at 10
    params = {"query": "test", "num_results": 100}

    result = await web_search_tool.execute(params, mock_context)

    assert result.success is True


async def test_execute_with_categories(web_search_tool, mock_context):
    """execute() accepts categories parameter."""
    mock_searxng = _mock_searxng_response([])
    mock_instant = _mock_instant_answer_response({})

    mock_session = MagicMock()
    # SearXNG first (empty), then DuckDuckGo fallback (empty)
    mock_session.get = MagicMock(side_effect=[mock_searxng, mock_instant])
    mock_session.closed = False
    web_search_tool._session = mock_session

    params = {"query": "test", "categories": "science"}

    result = await web_search_tool.execute(params, mock_context)

    assert result.success is True


# =============================================================================
# Error Handling Tests
# =============================================================================

async def test_execute_handles_api_error(web_search_tool, mock_context):
    """execute() handles API errors gracefully."""
    mock_error_response = MagicMock()
    mock_error_response.status = 500
    mock_error_response.__aenter__ = AsyncMock(return_value=mock_error_response)
    mock_error_response.__aexit__ = AsyncMock()

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_error_response)
    mock_session.closed = False
    web_search_tool._session = mock_session

    params = {"query": "test"}

    result = await web_search_tool.execute(params, mock_context)

    # Should return success=True with empty results, not fail
    assert result.success is True
    content = json.loads(result.content)
    assert content["count"] == 0


async def test_execute_handles_connection_error(web_search_tool, mock_context):
    """execute() handles connection errors gracefully."""
    import aiohttp

    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=aiohttp.ClientError("Connection failed"))
    mock_session.closed = False
    web_search_tool._session = mock_session

    params = {"query": "test"}

    result = await web_search_tool.execute(params, mock_context)

    # Should return success=True with empty results (searches failed, not error)
    assert result.success is True
    content = json.loads(result.content)
    assert content["count"] == 0


# =============================================================================
# Schema Tests
# =============================================================================

def test_to_schema(web_search_tool):
    """to_schema() returns correct tool schema."""
    schema = web_search_tool.to_schema()

    assert schema["name"] == "web_search"
    assert "description" in schema
    assert "parameters" in schema
    assert schema["parameters"]["type"] == "object"

    props = schema["parameters"]["properties"]
    assert "query" in props
    assert "num_results" in props
    assert "categories" in props

    assert "query" in schema["parameters"]["required"]


def test_tool_name():
    """Tool has correct name attribute."""
    assert WebSearchTool.name == "web_search"


def test_tool_description():
    """Tool has description."""
    assert WebSearchTool.description
    assert "search" in WebSearchTool.description.lower()


# =============================================================================
# Initialization Tests
# =============================================================================

def test_init_default_host(mock_context, mock_container):
    """__init__() uses default SearXNG host."""
    tool = WebSearchTool(context=mock_context, container=mock_container)
    assert tool._searxng_host == "http://localhost:8080"


def test_init_custom_host(mock_context, mock_container):
    """__init__() accepts custom SearXNG host."""
    tool = WebSearchTool(
        context=mock_context,
        container=mock_container,
        searxng_host="http://searxng.local:9090",
    )
    assert tool._searxng_host == "http://searxng.local:9090"


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_web_search_tool_factory():
    """create_web_search_tool() creates tool instance."""
    context = ExecutionContext(
        user_id="test",
        session_id="test",
        interface="web",
    )
    container = Container()

    tool = create_web_search_tool(context, container)

    assert isinstance(tool, WebSearchTool)
    assert tool._context == context
    assert tool._container == container
