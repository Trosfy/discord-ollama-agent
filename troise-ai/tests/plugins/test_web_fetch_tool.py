"""Unit tests for Web Fetch Tool with RAG pipeline."""
import json
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, List, Optional

from app.plugins.tools.web_fetch import WebFetchTool, create_web_fetch_tool
from app.core.context import ExecutionContext, UserProfile
from app.core.container import Container
from app.core.config import Config, RAGConfig, FetchConfig, ParsingConfig


# =============================================================================
# Mock Configuration
# =============================================================================

class MockRAGConfig:
    """Mock RAG configuration."""

    def __init__(self):
        self.chunk_size = 1000
        self.chunk_overlap = 200
        self.tokenizer_encoding = "cl100k_base"
        self.separators = ["\n\n", "\n", ". ", " ", ""]
        self.vector_top_k = 7
        self.max_fetch_tokens = 7000
        self.web_cache_ttl_hours = 2
        self.ttl_by_domain = {}
        self.fetch = FetchConfig()
        self.parsing = ParsingConfig()


class MockConfig:
    """Mock application config."""

    def __init__(self):
        self.rag = MockRAGConfig()
        self.backends = {
            'ollama': MagicMock(host='http://localhost:11434')
        }


# =============================================================================
# Mock Services
# =============================================================================

class MockWebChunk:
    """Mock web chunk from cache."""

    def __init__(self, chunk_index: int, text: str, token_count: int):
        self.chunk_index = chunk_index
        self.chunk_text = text
        self.token_count = token_count


class MockWebMeta:
    """Mock web metadata."""

    def __init__(self, title: str = "Test Page"):
        self.title = title


class MockWebChunksAdapter:
    """Mock TroiseWebChunksAdapter."""

    def __init__(self):
        self.cached_urls: Dict[str, List[MockWebChunk]] = {}
        self.stored_chunks: List[Dict] = []
        self.meta: Dict[str, MockWebMeta] = {}

    async def get_chunks_by_url(self, url: str) -> Optional[List[MockWebChunk]]:
        return self.cached_urls.get(url)

    async def get_meta(self, url: str) -> Optional[MockWebMeta]:
        return self.meta.get(url)

    async def store_chunks(
        self,
        url: str,
        title: str,
        chunks: List[Dict],
        embeddings: List[List[float]],
        ttl_hours: Optional[int] = None,
    ) -> int:
        self.stored_chunks = chunks
        return len(chunks)

    async def is_cached(self, url: str) -> bool:
        return url in self.cached_urls


class MockChunkingService:
    """Mock LangChainChunkingService."""

    def __init__(self):
        self.chunks_to_return = []

    async def chunk_text(self, text: str, source_url: str) -> List:
        if self.chunks_to_return:
            return self.chunks_to_return

        # Create mock TextChunks
        from app.core.interfaces import TextChunk
        return [
            TextChunk(
                chunk_id="chunk-1",
                text=text[:500] if len(text) > 500 else text,
                chunk_index=0,
                token_count=100,
                source_url=source_url,
                start_char=0,
                end_char=min(500, len(text)),
            )
        ]


class MockEmbeddingService:
    """Mock EmbeddingService."""

    async def embed(self, text: str) -> List[float]:
        return [0.1] * 768


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
    """Create mock DI container with services registered."""
    container = Container()
    container.register(Config, MockConfig())
    return container


@pytest.fixture
def web_fetch_tool(mock_context, mock_container):
    """Create web fetch tool with mock dependencies."""
    tool = WebFetchTool(
        context=mock_context,
        container=mock_container,
    )
    # Set up mock services
    tool._chunking_service = MockChunkingService()
    tool._embedding_service = MockEmbeddingService()
    tool._web_chunks_adapter = MockWebChunksAdapter()
    return tool


def _mock_html_response(html: str, status: int = 200, content_type: str = "text/html", content_length: int = None):
    """Create mock aiohttp response with HTML content."""
    mock_response = MagicMock()
    mock_response.status = status
    mock_response.headers = {"Content-Type": content_type}
    mock_response.content_length = content_length
    mock_response.text = AsyncMock(return_value=html)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock()
    return mock_response


# =============================================================================
# Input Validation Tests
# =============================================================================

async def test_execute_missing_url(web_fetch_tool, mock_context):
    """execute() returns error when no URL provided."""
    params = {}

    result = await web_fetch_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "required" in content["error"].lower()


async def test_execute_empty_url(web_fetch_tool, mock_context):
    """execute() returns error for empty URL."""
    params = {"url": "   "}

    result = await web_fetch_tool.execute(params, mock_context)

    assert result.success is False


async def test_execute_invalid_url_format(web_fetch_tool, mock_context):
    """execute() returns error for invalid URL format."""
    params = {"url": "not-a-valid-url"}

    result = await web_fetch_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "invalid" in content["error"].lower()


async def test_execute_non_http_url(web_fetch_tool, mock_context):
    """execute() returns error for non-http URLs."""
    params = {"url": "ftp://example.com/file.txt"}

    result = await web_fetch_tool.execute(params, mock_context)

    assert result.success is False


# =============================================================================
# URL Validation Tests
# =============================================================================

def test_validate_url_http(web_fetch_tool):
    """_validate_url() accepts http URLs."""
    assert web_fetch_tool._validate_url("http://example.com") is True


def test_validate_url_https(web_fetch_tool):
    """_validate_url() accepts https URLs."""
    assert web_fetch_tool._validate_url("https://example.com/path") is True


def test_validate_url_rejects_ftp(web_fetch_tool):
    """_validate_url() rejects ftp URLs."""
    assert web_fetch_tool._validate_url("ftp://example.com") is False


def test_validate_url_rejects_file(web_fetch_tool):
    """_validate_url() rejects file URLs."""
    assert web_fetch_tool._validate_url("file:///etc/passwd") is False


def test_validate_url_rejects_invalid(web_fetch_tool):
    """_validate_url() rejects invalid URLs."""
    assert web_fetch_tool._validate_url("not-a-url") is False


# =============================================================================
# Cache Hit Tests
# =============================================================================

async def test_execute_returns_cached_content(web_fetch_tool, mock_context):
    """execute() returns cached content when available."""
    url = "https://example.com/cached"

    # Set up cache with mock chunks
    web_fetch_tool._web_chunks_adapter.cached_urls[url] = [
        MockWebChunk(0, "Cached chunk 1", 50),
        MockWebChunk(1, "Cached chunk 2", 50),
    ]
    web_fetch_tool._web_chunks_adapter.meta[url] = MockWebMeta("Cached Page")

    params = {"url": url}
    result = await web_fetch_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["cached"] is True
    assert content["url"] == url
    assert content["title"] == "Cached Page"
    assert len(content["chunks"]) == 2


async def test_execute_force_refresh_bypasses_cache(web_fetch_tool, mock_context):
    """execute() bypasses cache when force_refresh=True."""
    url = "https://example.com/cached"

    # Set up cache
    web_fetch_tool._web_chunks_adapter.cached_urls[url] = [
        MockWebChunk(0, "Cached content", 50),
    ]
    web_fetch_tool._web_chunks_adapter.meta[url] = MockWebMeta("Cached")

    # Set up mock HTTP response for fresh fetch (must have >50 chars of content)
    html = """<html><head><title>Fresh Page</title></head><body>
        <p>Fresh content that is long enough to pass the minimum character threshold.
        This paragraph contains additional text to ensure we have more than 50 characters.</p>
    </body></html>"""
    mock_response = _mock_html_response(html)
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.closed = False
    web_fetch_tool._session = mock_session

    params = {"url": url, "force_refresh": True}
    result = await web_fetch_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["cached"] is False  # Should be fresh fetch


# =============================================================================
# Fetch and Parse Tests
# =============================================================================

async def test_execute_fetches_and_parses_html(web_fetch_tool, mock_context):
    """execute() fetches and parses HTML content."""
    html = """
    <html>
    <head><title>Test Page Title</title></head>
    <body>
        <article>
            <h1>Main Heading</h1>
            <p>This is the main content of the page with enough text to pass the minimum threshold.</p>
            <p>Another paragraph with more details about the topic being discussed.</p>
        </article>
    </body>
    </html>
    """

    mock_response = _mock_html_response(html)
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.closed = False
    web_fetch_tool._session = mock_session

    params = {"url": "https://example.com/article"}
    result = await web_fetch_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["url"] == "https://example.com/article"
    assert content["title"] == "Test Page Title"
    assert content["cached"] is False


async def test_execute_removes_script_tags(web_fetch_tool, mock_context):
    """execute() removes script tags during parsing."""
    html = """
    <html>
    <head><title>Test</title><script>alert('bad');</script></head>
    <body>
        <p>Main content that is visible to users and should be included.</p>
        <script>document.write('malicious');</script>
    </body>
    </html>
    """

    mock_response = _mock_html_response(html)
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.closed = False
    web_fetch_tool._session = mock_session

    params = {"url": "https://example.com"}
    result = await web_fetch_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)

    # Scripts should not be in output
    all_text = "".join(c["text"] for c in content["chunks"])
    assert "alert" not in all_text
    assert "malicious" not in all_text


async def test_execute_handles_no_content(web_fetch_tool, mock_context):
    """execute() handles pages with no extractable content."""
    html = "<html><head></head><body></body></html>"

    mock_response = _mock_html_response(html)
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.closed = False
    web_fetch_tool._session = mock_session

    params = {"url": "https://example.com/empty"}
    result = await web_fetch_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "no readable content" in content["error"].lower()


# =============================================================================
# Error Handling Tests
# =============================================================================

async def test_execute_handles_http_error(web_fetch_tool, mock_context):
    """execute() handles HTTP errors gracefully."""
    mock_response = _mock_html_response("", status=404)
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.closed = False
    web_fetch_tool._session = mock_session

    params = {"url": "https://example.com/notfound"}
    result = await web_fetch_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "failed" in content["error"].lower()


async def test_execute_handles_connection_error(web_fetch_tool, mock_context):
    """execute() handles connection errors gracefully."""
    import aiohttp

    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=aiohttp.ClientError("Connection failed"))
    mock_session.closed = False
    web_fetch_tool._session = mock_session

    params = {"url": "https://example.com"}
    result = await web_fetch_tool.execute(params, mock_context)

    assert result.success is False


async def test_execute_handles_non_html_content(web_fetch_tool, mock_context):
    """execute() rejects non-HTML content types."""
    mock_response = _mock_html_response("binary data", content_type="application/pdf")
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.closed = False
    web_fetch_tool._session = mock_session

    params = {"url": "https://example.com/file.pdf"}
    result = await web_fetch_tool.execute(params, mock_context)

    assert result.success is False


# =============================================================================
# Token Budget Tests
# =============================================================================

async def test_execute_respects_token_budget(web_fetch_tool, mock_context):
    """execute() returns chunks within token budget."""
    url = "https://example.com/large"

    # Set up cache with many chunks totaling > max_fetch_tokens
    chunks = [
        MockWebChunk(i, f"Chunk {i} content " * 10, 1000)
        for i in range(20)
    ]
    web_fetch_tool._web_chunks_adapter.cached_urls[url] = chunks
    web_fetch_tool._web_chunks_adapter.meta[url] = MockWebMeta("Large Page")

    # Config has max_fetch_tokens = 7000
    params = {"url": url}
    result = await web_fetch_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)

    # Total tokens should be <= 7000
    assert content["total_tokens"] <= 7000
    # Should not return all chunks
    assert content["returned_chunks"] < content["total_chunks"]


async def test_execute_max_chunks_parameter(web_fetch_tool, mock_context):
    """execute() respects max_chunks parameter."""
    html = """
    <html>
    <head><title>Test</title></head>
    <body>
        <p>Content paragraph one with sufficient text content.</p>
        <p>Content paragraph two with sufficient text content.</p>
        <p>Content paragraph three with sufficient text content.</p>
    </body>
    </html>
    """

    mock_response = _mock_html_response(html)
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.closed = False
    web_fetch_tool._session = mock_session

    # Set up mock chunking to return multiple chunks
    from app.core.interfaces import TextChunk
    web_fetch_tool._chunking_service.chunks_to_return = [
        TextChunk(
            chunk_id=f"c{i}",
            text=f"Chunk {i}",
            chunk_index=i,
            token_count=100,
            source_url="https://example.com",
            start_char=0,
            end_char=10,
        )
        for i in range(5)
    ]

    params = {"url": "https://example.com", "max_chunks": 2}
    result = await web_fetch_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["returned_chunks"] <= 2


# =============================================================================
# Schema Tests
# =============================================================================

def test_to_schema(web_fetch_tool):
    """to_schema() returns correct tool schema."""
    schema = web_fetch_tool.to_schema()

    assert schema["name"] == "web_fetch"
    assert "description" in schema
    assert "parameters" in schema
    assert schema["parameters"]["type"] == "object"

    props = schema["parameters"]["properties"]
    assert "url" in props
    assert "force_refresh" in props
    assert "max_chunks" in props

    assert "url" in schema["parameters"]["required"]


def test_tool_name():
    """Tool has correct name attribute."""
    assert WebFetchTool.name == "web_fetch"


def test_tool_description():
    """Tool has description."""
    assert WebFetchTool.description
    assert "fetch" in WebFetchTool.description.lower()


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_web_fetch_tool_factory():
    """create_web_fetch_tool() creates tool instance."""
    context = ExecutionContext(
        user_id="test",
        session_id="test",
        interface="web",
    )
    container = Container()
    container.register(Config, MockConfig())

    tool = create_web_fetch_tool(context, container)

    assert isinstance(tool, WebFetchTool)
    assert tool._context == context
    assert tool._container == container


# =============================================================================
# HTML Parsing Tests
# =============================================================================

def test_parse_html_extracts_title(web_fetch_tool):
    """_parse_html() extracts title from HTML."""
    html = "<html><head><title>Page Title</title></head><body><p>Content</p></body></html>"

    text, title = web_fetch_tool._parse_html(html)

    assert title == "Page Title"
    assert "Content" in text


def test_parse_html_removes_nav(web_fetch_tool):
    """_parse_html() removes navigation elements."""
    html = """
    <html>
    <body>
        <nav><a href="/">Home</a><a href="/about">About</a></nav>
        <main><p>Main content text.</p></main>
        <footer>Footer content</footer>
    </body>
    </html>
    """

    text, _ = web_fetch_tool._parse_html(html)

    assert "Main content" in text
    assert "Home" not in text  # nav should be removed
    assert "Footer" not in text  # footer should be removed


def test_parse_html_handles_empty(web_fetch_tool):
    """_parse_html() handles empty HTML."""
    html = "<html><body></body></html>"

    text, title = web_fetch_tool._parse_html(html)

    assert title is None
    assert text == "" or text.strip() == ""


# =============================================================================
# Token Budget Selection Tests
# =============================================================================

def test_select_chunks_within_budget(web_fetch_tool):
    """_select_chunks_within_budget() respects token limit."""
    chunks = [
        {"chunk_index": 0, "text": "First", "token_count": 3000},
        {"chunk_index": 1, "text": "Second", "token_count": 3000},
        {"chunk_index": 2, "text": "Third", "token_count": 3000},
    ]

    selected, total = web_fetch_tool._select_chunks_within_budget(chunks, 5000)

    # Should only select first chunk (3000 < 5000, but 3000+3000 > 5000)
    assert len(selected) == 1
    assert total == 3000


def test_select_chunks_empty_list(web_fetch_tool):
    """_select_chunks_within_budget() handles empty list."""
    selected, total = web_fetch_tool._select_chunks_within_budget([], 5000)

    assert selected == []
    assert total == 0


def test_select_chunks_all_fit(web_fetch_tool):
    """_select_chunks_within_budget() returns all if they fit."""
    chunks = [
        {"chunk_index": 0, "text": "First", "token_count": 100},
        {"chunk_index": 1, "text": "Second", "token_count": 100},
    ]

    selected, total = web_fetch_tool._select_chunks_within_budget(chunks, 5000)

    assert len(selected) == 2
    assert total == 200


# =============================================================================
# Integration-like Tests
# =============================================================================

async def test_full_rag_pipeline(web_fetch_tool, mock_context):
    """Test full RAG pipeline: fetch -> parse -> chunk -> embed -> store."""
    html = """
    <html>
    <head><title>RAG Test Page</title></head>
    <body>
        <article>
            <h1>Understanding RAG</h1>
            <p>Retrieval-Augmented Generation combines the power of large language models
               with external knowledge retrieval to provide accurate, up-to-date information.</p>
            <p>The RAG pipeline consists of several steps including fetching, chunking,
               embedding generation, and storage for later retrieval.</p>
        </article>
    </body>
    </html>
    """

    mock_response = _mock_html_response(html)
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.closed = False
    web_fetch_tool._session = mock_session

    params = {"url": "https://example.com/rag-article"}
    result = await web_fetch_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)

    # Verify response structure
    assert "url" in content
    assert "title" in content
    assert "chunks" in content
    assert "total_chunks" in content
    assert "returned_chunks" in content
    assert "total_tokens" in content
    assert "cached" in content

    # Should have processed content
    assert content["title"] == "RAG Test Page"
    assert len(content["chunks"]) > 0
