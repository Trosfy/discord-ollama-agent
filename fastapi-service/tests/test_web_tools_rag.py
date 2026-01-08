"""Integration tests for RAG-enhanced web tools."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta


@pytest.fixture
def mock_html_response():
    """Mock HTML response from web fetch."""
    return """
    <html>
        <head><title>Test Page</title></head>
        <body>
            <nav>Navigation menu (should be removed)</nav>
            <article>
                <h1>Main Content</h1>
                <p>This is the first paragraph with important information.</p>
                <p>This is the second paragraph with more details about the topic.</p>
                <p>This is the third paragraph concluding the article.</p>
            </article>
            <footer>Footer content (should be removed)</footer>
        </body>
    </html>
    """


@pytest.fixture
def mock_embedding_response():
    """Mock Ollama embedding response."""
    return {"embedding": [0.1, 0.2, 0.3] * 341 + [0.4]}  # 1024 dimensions


@pytest.mark.asyncio
async def test_fetch_webpage_cache_miss_full_pipeline(mock_html_response, mock_embedding_response):
    """Test full RAG pipeline on cache miss."""
    from app.tools.web_tools import fetch_webpage

    url = "https://example.com/test"

    with patch('app.tools.web_tools._fetch_with_retry') as mock_fetch, \
         patch('httpx.AsyncClient') as mock_embedding_client, \
         patch('aioboto3.Session') as mock_session:

        # Setup HTTP fetch mock
        mock_response = MagicMock()
        mock_response.content = mock_html_response.encode('utf-8')
        mock_fetch.return_value = mock_response

        # Setup embedding service mock
        mock_embed_response = MagicMock()
        mock_embed_response.json.return_value = mock_embedding_response
        mock_embed_response.raise_for_status = MagicMock()

        mock_embed_instance = AsyncMock()
        mock_embed_instance.post.return_value = mock_embed_response
        mock_embed_instance.__aenter__.return_value = mock_embed_instance
        mock_embed_instance.__aexit__.return_value = AsyncMock()
        mock_embedding_client.return_value = mock_embed_instance

        # Setup DynamoDB mocks
        # Cache check (miss)
        mock_table_get = AsyncMock()
        mock_table_get.query = AsyncMock(return_value={"Items": []})

        # Cache store
        mock_batch = AsyncMock()
        mock_batch.put_item = AsyncMock()
        mock_batch.__aenter__ = AsyncMock(return_value=mock_batch)
        mock_batch.__aexit__ = AsyncMock()
        mock_table_get.batch_writer = MagicMock(return_value=mock_batch)

        mock_dynamodb = AsyncMock()
        mock_dynamodb.Table = AsyncMock(return_value=mock_table_get)
        mock_dynamodb.__aenter__ = AsyncMock(return_value=mock_dynamodb)
        mock_dynamodb.__aexit__ = AsyncMock()

        mock_session_instance = MagicMock()
        mock_session_instance.resource = MagicMock(return_value=mock_dynamodb)
        mock_session.return_value = mock_session_instance

        # Call fetch_webpage
        result = await fetch_webpage(url)

        # Verify result structure
        assert "url" in result
        assert result["url"] == url
        assert "title" in result
        assert result["title"] == "Test Page"
        assert "cached" in result
        assert result["cached"] is False
        assert "chunks" in result
        assert len(result["chunks"]) > 0
        assert "total_chunks" in result
        assert "embedding_model" in result

        # Verify chunks have expected fields
        for chunk in result["chunks"]:
            assert "chunk_id" in chunk
            assert "text" in chunk
            assert "chunk_index" in chunk
            assert "token_count" in chunk


@pytest.mark.asyncio
async def test_fetch_webpage_cache_hit(mock_embedding_response):
    """Test fetch_webpage with cache hit."""
    from app.tools.web_tools import fetch_webpage

    url = "https://example.com/cached"

    # Create cached chunks
    future_ttl = int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    cached_items = [
        {
            "url_hash": "somehash",
            "chunk_id": "chunk-1",
            "chunk_text": "Cached chunk 1",
            "embedding_vector": [0.1] * 1024,
            "chunk_index": 0,
            "token_count": 3,
            "source_url": url,
            "created_at": datetime.utcnow().isoformat(),
            "ttl": future_ttl
        },
        {
            "url_hash": "somehash",
            "chunk_id": "chunk-2",
            "chunk_text": "Cached chunk 2",
            "embedding_vector": [0.2] * 1024,
            "chunk_index": 1,
            "token_count": 3,
            "source_url": url,
            "created_at": datetime.utcnow().isoformat(),
            "ttl": future_ttl
        }
    ]

    with patch('aioboto3.Session') as mock_session:
        # Setup DynamoDB mock (cache hit)
        mock_table = AsyncMock()
        mock_table.query = AsyncMock(return_value={"Items": cached_items})

        mock_dynamodb = AsyncMock()
        mock_dynamodb.Table = AsyncMock(return_value=mock_table)
        mock_dynamodb.__aenter__ = AsyncMock(return_value=mock_dynamodb)
        mock_dynamodb.__aexit__ = AsyncMock()

        mock_session_instance = MagicMock()
        mock_session_instance.resource = MagicMock(return_value=mock_dynamodb)
        mock_session.return_value = mock_session_instance

        # Call fetch_webpage
        result = await fetch_webpage(url, use_cache=True)

        # Verify cache hit
        assert result["cached"] is True
        assert len(result["chunks"]) == 2
        assert result["chunks"][0]["chunk_id"] == "chunk-1"
        assert result["chunks"][0]["text"] == "Cached chunk 1"


@pytest.mark.asyncio
async def test_fetch_webpage_cache_disabled(mock_html_response, mock_embedding_response):
    """Test fetch_webpage with cache disabled."""
    from app.tools.web_tools import fetch_webpage

    url = "https://example.com/nocache"

    with patch('app.tools.web_tools._fetch_with_retry') as mock_fetch, \
         patch('httpx.AsyncClient') as mock_embedding_client, \
         patch('aioboto3.Session') as mock_session:

        # Setup mocks
        mock_response = MagicMock()
        mock_response.content = mock_html_response.encode('utf-8')
        mock_fetch.return_value = mock_response

        mock_embed_response = MagicMock()
        mock_embed_response.json.return_value = mock_embedding_response
        mock_embed_response.raise_for_status = MagicMock()

        mock_embed_instance = AsyncMock()
        mock_embed_instance.post.return_value = mock_embed_response
        mock_embed_instance.__aenter__.return_value = mock_embed_instance
        mock_embed_instance.__aexit__.return_value = AsyncMock()
        mock_embedding_client.return_value = mock_embed_instance

        mock_batch = AsyncMock()
        mock_batch.put_item = AsyncMock()
        mock_batch.__aenter__ = AsyncMock(return_value=mock_batch)
        mock_batch.__aexit__ = AsyncMock()

        mock_table = AsyncMock()
        mock_table.batch_writer = MagicMock(return_value=mock_batch)

        mock_dynamodb = AsyncMock()
        mock_dynamodb.Table = AsyncMock(return_value=mock_table)
        mock_dynamodb.__aenter__ = AsyncMock(return_value=mock_dynamodb)
        mock_dynamodb.__aexit__ = AsyncMock()

        mock_session_instance = MagicMock()
        mock_session_instance.resource = MagicMock(return_value=mock_dynamodb)
        mock_session.return_value = mock_session_instance

        # Call fetch_webpage with cache disabled
        result = await fetch_webpage(url, use_cache=False)

        # Verify no cache check was performed
        assert result["cached"] is False
        # Web fetch should have occurred
        mock_fetch.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_webpage_http_error():
    """Test fetch_webpage handling HTTP errors."""
    from app.tools.web_tools import fetch_webpage
    import httpx

    url = "https://example.com/error"

    with patch('app.tools.web_tools._fetch_with_retry') as mock_fetch, \
         patch('aioboto3.Session') as mock_session:

        # Setup cache miss
        mock_table = AsyncMock()
        mock_table.query = AsyncMock(return_value={"Items": []})

        mock_dynamodb = AsyncMock()
        mock_dynamodb.Table = AsyncMock(return_value=mock_table)
        mock_dynamodb.__aenter__ = AsyncMock(return_value=mock_dynamodb)
        mock_dynamodb.__aexit__ = AsyncMock()

        mock_session_instance = MagicMock()
        mock_session_instance.resource = MagicMock(return_value=mock_dynamodb)
        mock_session.return_value = mock_session_instance

        # Setup fetch to raise HTTP error
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_fetch.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        # Call fetch_webpage
        result = await fetch_webpage(url)

        # Should return error dict
        assert "error" in result
        assert "404" in result["error"]


@pytest.mark.asyncio
async def test_fetch_webpage_timeout():
    """Test fetch_webpage handling timeout."""
    from app.tools.web_tools import fetch_webpage
    import httpx

    url = "https://example.com/timeout"

    with patch('app.tools.web_tools._fetch_with_retry') as mock_fetch, \
         patch('aioboto3.Session') as mock_session:

        # Setup cache miss
        mock_table = AsyncMock()
        mock_table.query = AsyncMock(return_value={"Items": []})

        mock_dynamodb = AsyncMock()
        mock_dynamodb.Table = AsyncMock(return_value=mock_table)
        mock_dynamodb.__aenter__ = AsyncMock(return_value=mock_dynamodb)
        mock_dynamodb.__aexit__ = AsyncMock()

        mock_session_instance = MagicMock()
        mock_session_instance.resource = MagicMock(return_value=mock_dynamodb)
        mock_session.return_value = mock_session_instance

        # Setup fetch to raise timeout
        mock_fetch.side_effect = httpx.TimeoutException("Timeout")

        # Call fetch_webpage
        result = await fetch_webpage(url, max_retries=2)

        # Should return error dict
        assert "error" in result
        assert "Timeout" in result["error"]


@pytest.mark.asyncio
async def test_fetch_webpage_insufficient_content(mock_embedding_response):
    """Test fetch_webpage with very short content."""
    from app.tools.web_tools import fetch_webpage

    url = "https://example.com/short"

    # HTML with very little content
    short_html = "<html><head><title>Short</title></head><body><p>Hi</p></body></html>"

    with patch('app.tools.web_tools._fetch_with_retry') as mock_fetch, \
         patch('aioboto3.Session') as mock_session:

        # Setup cache miss
        mock_table = AsyncMock()
        mock_table.query = AsyncMock(return_value={"Items": []})

        mock_dynamodb = AsyncMock()
        mock_dynamodb.Table = AsyncMock(return_value=mock_table)
        mock_dynamodb.__aenter__ = AsyncMock(return_value=mock_dynamodb)
        mock_dynamodb.__aexit__ = AsyncMock()

        mock_session_instance = MagicMock()
        mock_session_instance.resource = MagicMock(return_value=mock_dynamodb)
        mock_session.return_value = mock_session_instance

        # Setup fetch
        mock_response = MagicMock()
        mock_response.content = short_html.encode('utf-8')
        mock_fetch.return_value = mock_response

        # Call fetch_webpage
        result = await fetch_webpage(url)

        # Should return error for insufficient content
        assert "error" in result
        assert "Insufficient content" in result["error"]


def test_get_realistic_headers():
    """Test realistic header generation."""
    from app.tools.web_tools import _get_realistic_headers

    headers = _get_realistic_headers()

    # Verify required headers
    assert "User-Agent" in headers
    assert "Accept" in headers
    assert "Accept-Language" in headers
    assert "DNT" in headers

    # User-Agent should be from the pool
    from app.tools.web_tools import USER_AGENTS
    assert headers["User-Agent"] in USER_AGENTS

    # Headers should vary (due to random User-Agent)
    headers1 = _get_realistic_headers()
    headers2 = _get_realistic_headers()
    # May or may not differ, but should be valid
    assert "User-Agent" in headers1
    assert "User-Agent" in headers2


@pytest.mark.asyncio
async def test_fetch_with_retry_success():
    """Test successful fetch with retry mechanism."""
    from app.tools.web_tools import _fetch_with_retry

    url = "https://example.com/test"

    with patch('app.tools.web_tools._get_or_create_session') as mock_session:
        # Setup mock
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_session.return_value = mock_client

        # Call fetch_with_retry
        result = await _fetch_with_retry(url, max_retries=3)

        # Verify success
        assert result == mock_response
        mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_with_retry_rate_limit_retry():
    """Test retry on 429 rate limit."""
    from app.tools.web_tools import _fetch_with_retry
    import httpx

    url = "https://example.com/ratelimit"

    with patch('app.tools.web_tools._get_or_create_session') as mock_session, \
         patch('asyncio.sleep') as mock_sleep:

        # Setup mock to fail first 2 times, succeed 3rd time
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # Return 429
                mock_response = MagicMock()
                mock_response.status_code = 429
                mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "Rate limited", request=MagicMock(), response=mock_response
                )
                return mock_response
            else:
                # Success
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                return mock_response

        mock_client = AsyncMock()
        mock_client.get.side_effect = side_effect
        mock_session.return_value = mock_client
        mock_sleep.return_value = None

        # Call fetch_with_retry
        result = await _fetch_with_retry(url, max_retries=3)

        # Verify success after retries
        assert result is not None
        assert call_count == 3
        # Should have called sleep twice (for 2 retries)
        assert mock_sleep.call_count == 2


@pytest.mark.asyncio
async def test_fetch_with_retry_exhausted():
    """Test retry exhaustion."""
    from app.tools.web_tools import _fetch_with_retry
    import httpx

    url = "https://example.com/alwaysfails"

    with patch('app.tools.web_tools._get_or_create_session') as mock_session, \
         patch('asyncio.sleep') as mock_sleep:

        # Setup mock to always fail
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service unavailable", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_session.return_value = mock_client
        mock_sleep.return_value = None

        # Should raise after exhausting retries
        with pytest.raises(httpx.HTTPStatusError):
            await _fetch_with_retry(url, max_retries=3)

        # Should have tried 3 times
        assert mock_client.get.call_count == 3
        # Should have slept 2 times (not after last failure)
        assert mock_sleep.call_count == 2


def test_user_agent_pool():
    """Test User-Agent pool configuration."""
    from app.tools.web_tools import USER_AGENTS

    # Should have 6 agents
    assert len(USER_AGENTS) == 6

    # All should be strings
    assert all(isinstance(ua, str) for ua in USER_AGENTS)

    # All should be unique
    assert len(USER_AGENTS) == len(set(USER_AGENTS))

    # All should contain "Mozilla" (standard browser identifier)
    assert all("Mozilla" in ua for ua in USER_AGENTS)
