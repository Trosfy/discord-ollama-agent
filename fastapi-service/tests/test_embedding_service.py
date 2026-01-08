"""Tests for Ollama embedding service."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.embedding_service import OllamaEmbeddingService


@pytest.fixture
def embedding_service():
    """Create embedding service instance."""
    return OllamaEmbeddingService(
        model="qwen3-embedding:4b",
        base_url="http://localhost:11434",
        timeout=60
    )


@pytest.fixture
def mock_embedding_response():
    """Mock Ollama API response."""
    return {
        "embedding": [0.1, 0.2, 0.3] * 341 + [0.4]  # 1024 dimensions
    }


@pytest.mark.asyncio
async def test_embed_text_success(embedding_service, mock_embedding_response):
    """Test successful text embedding."""
    text = "This is a test sentence."

    with patch('httpx.AsyncClient') as mock_client:
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = mock_embedding_response
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = AsyncMock()
        mock_client.return_value = mock_instance

        # Call embed_text
        result = await embedding_service.embed_text(text)

        # Verify result
        assert result.text == text
        assert result.model == "qwen3-embedding:4b"
        assert result.dimension == 1024
        assert len(result.vector) == 1024
        assert result.vector[0] == 0.1

        # Verify API was called correctly
        mock_instance.post.assert_called_once()
        call_args = mock_instance.post.call_args
        assert call_args[0][0] == "http://localhost:11434/api/embeddings"
        assert call_args[1]["json"]["model"] == "qwen3-embedding:4b"
        assert call_args[1]["json"]["prompt"] == text


@pytest.mark.asyncio
async def test_embed_text_empty_raises_error(embedding_service):
    """Test that empty text raises ValueError."""
    with pytest.raises(ValueError, match="Text cannot be empty"):
        await embedding_service.embed_text("")

    with pytest.raises(ValueError, match="Text cannot be empty"):
        await embedding_service.embed_text("   ")


@pytest.mark.asyncio
async def test_embed_text_http_error(embedding_service):
    """Test handling of HTTP errors."""
    import httpx

    with patch('httpx.AsyncClient') as mock_client_class:
        # Setup mock to raise HTTP error from post method directly
        mock_response = MagicMock()
        mock_response.status_code = 500

        http_error = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )

        mock_instance = AsyncMock()
        # Make post raise HTTPStatusError directly
        mock_instance.post = AsyncMock(side_effect=http_error)
        mock_instance.__aenter__.return_value = mock_instance
        # __aexit__ must return None to not suppress exceptions
        mock_instance.__aexit__.return_value = None
        # Use MagicMock for the class to return instance synchronously
        mock_client_class.return_value = mock_instance

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Failed to generate embedding"):
            await embedding_service.embed_text("Test text")


@pytest.mark.asyncio
async def test_embed_text_no_embedding_in_response(embedding_service):
    """Test handling when API returns no embedding."""
    with patch('httpx.AsyncClient') as mock_client_class:
        # Setup mock with empty response
        mock_response = MagicMock()
        # Explicitly create a Mock for json() method
        mock_response.json = MagicMock(return_value={"error": "No embedding"})
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        # __aexit__ must return None to not suppress exceptions
        mock_instance.__aexit__.return_value = None
        mock_client_class.return_value = mock_instance

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="No embedding returned"):
            await embedding_service.embed_text("Test text")


@pytest.mark.asyncio
async def test_embed_batch_success(embedding_service, mock_embedding_response):
    """Test successful batch embedding."""
    texts = ["First text", "Second text", "Third text"]

    with patch('httpx.AsyncClient') as mock_client:
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = mock_embedding_response
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = AsyncMock()
        mock_client.return_value = mock_instance

        # Call embed_batch
        results = await embedding_service.embed_batch(texts)

        # Verify results
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.text == texts[i]
            assert result.model == "qwen3-embedding:4b"
            assert len(result.vector) == 1024

        # Verify API was called 3 times (once per text)
        assert mock_instance.post.call_count == 3


@pytest.mark.asyncio
async def test_embed_batch_empty_list_raises_error(embedding_service):
    """Test that empty texts list raises ValueError."""
    with pytest.raises(ValueError, match="Texts list cannot be empty"):
        await embedding_service.embed_batch([])


@pytest.mark.asyncio
async def test_embed_batch_partial_failure(embedding_service, mock_embedding_response):
    """Test batch embedding with partial failures."""
    import httpx

    texts = ["First text", "Second text", "Third text"]

    with patch('httpx.AsyncClient') as mock_client_class:
        # Setup mock to fail on second call
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                # Second call fails by raising exception
                raise httpx.HTTPStatusError(
                    "Server error", request=MagicMock(), response=MagicMock(status_code=500)
                )
            else:
                # Other calls succeed
                mock_response = MagicMock()
                mock_response.json = MagicMock(return_value=mock_embedding_response)
                mock_response.raise_for_status = MagicMock()
                return mock_response

        mock_instance = AsyncMock()
        mock_instance.post = side_effect
        mock_instance.__aenter__.return_value = mock_instance
        # __aexit__ must return None to not suppress exceptions
        mock_instance.__aexit__.return_value = None
        mock_client_class.return_value = mock_instance

        # Should raise RuntimeError on second embedding
        with pytest.raises(RuntimeError):
            await embedding_service.embed_batch(texts)


@pytest.mark.asyncio
async def test_embed_text_long_text(embedding_service, mock_embedding_response):
    """Test embedding of long text."""
    long_text = "This is a very long text. " * 1000  # ~10k tokens

    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_embedding_response
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = AsyncMock()
        mock_client.return_value = mock_instance

        # Should handle long text without errors
        result = await embedding_service.embed_text(long_text)
        assert len(result.vector) == 1024


@pytest.mark.asyncio
async def test_embed_text_special_characters(embedding_service, mock_embedding_response):
    """Test embedding with special characters and unicode."""
    special_text = "Test @#$%^&*() 你好世界 🌍 émojis ∫x²dx"

    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_embedding_response
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = AsyncMock()
        mock_client.return_value = mock_instance

        # Should handle special characters
        result = await embedding_service.embed_text(special_text)
        assert result.text == special_text
        assert len(result.vector) == 1024


def test_embedding_service_initialization():
    """Test embedding service initialization."""
    # Default initialization
    service1 = OllamaEmbeddingService()
    assert service1.model == "qwen3-embedding:4b"  # From settings
    assert service1.timeout == 60

    # Custom initialization
    service2 = OllamaEmbeddingService(
        model="custom-model",
        base_url="http://custom:8000",
        timeout=120
    )
    assert service2.model == "custom-model"
    assert service2.base_url == "http://custom:8000"
    assert service2.timeout == 120


@pytest.mark.asyncio
async def test_embed_batch_large_batch(embedding_service, mock_embedding_response):
    """Test batch embedding with large number of texts."""
    texts = [f"Text number {i}" for i in range(50)]

    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_embedding_response
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = AsyncMock()
        mock_client.return_value = mock_instance

        # Should handle large batch
        results = await embedding_service.embed_batch(texts)
        assert len(results) == 50
        assert mock_instance.post.call_count == 50


@pytest.mark.asyncio
async def test_embed_text_timeout(embedding_service):
    """Test handling of timeout errors."""
    import httpx

    with patch('httpx.AsyncClient') as mock_client_class:
        # Setup mock to raise timeout - need to create a proper TimeoutException
        timeout_exception = httpx.TimeoutException("Timeout")

        mock_instance = AsyncMock()
        # Explicitly set side_effect to raise the exception
        mock_instance.post = AsyncMock(side_effect=timeout_exception)
        mock_instance.__aenter__.return_value = mock_instance
        # __aexit__ must return None to not suppress exceptions
        mock_instance.__aexit__.return_value = None
        mock_client_class.return_value = mock_instance

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Failed to generate embedding"):
            await embedding_service.embed_text("Test text")


@pytest.mark.asyncio
async def test_embed_text_connection_error(embedding_service):
    """Test handling of connection errors."""
    import httpx

    with patch('httpx.AsyncClient') as mock_client_class:
        # Setup mock to raise connection error - need to create a proper ConnectError
        connect_exception = httpx.ConnectError("Connection failed")

        mock_instance = AsyncMock()
        # Explicitly set side_effect to raise the exception
        mock_instance.post = AsyncMock(side_effect=connect_exception)
        mock_instance.__aenter__.return_value = mock_instance
        # __aexit__ must return None to not suppress exceptions
        mock_instance.__aexit__.return_value = None
        mock_client_class.return_value = mock_instance

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Failed to generate embedding"):
            await embedding_service.embed_text("Test text")
