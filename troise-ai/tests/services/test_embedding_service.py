"""Unit tests for Embedding Service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, List

from app.services.embedding_service import (
    EmbeddingService,
    EmbeddingServiceError,
    DEFAULT_MODEL,
    DEFAULT_DIMENSIONS,
    create_embedding_service,
)


# =============================================================================
# Mock aiohttp Response
# =============================================================================

class MockResponse:
    """Mock aiohttp response."""
    def __init__(self, status: int, json_data: Dict[str, Any] = None, text: str = ""):
        self.status = status
        self._json_data = json_data or {}
        self._text = text

    async def json(self):
        return self._json_data

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockSession:
    """Mock aiohttp ClientSession."""
    def __init__(self, responses: Dict[str, MockResponse] = None):
        self._responses = responses or {}
        self.closed = False
        self.requests = []

    def post(self, url, json=None, timeout=None):
        self.requests.append({"method": "POST", "url": url, "json": json})
        return self._responses.get(url, MockResponse(500, {}, "Not mocked"))

    async def close(self):
        self.closed = True


class MockVectorsAdapter:
    """Mock vectors adapter for caching."""
    def __init__(self):
        self._cache = {}
        self.cache_calls = []
        self.get_calls = []

    async def get_cached_embedding(self, text: str, model: str):
        self.get_calls.append({"text": text, "model": model})
        key = f"{model}:{text}"
        return self._cache.get(key)

    async def cache_embedding(self, text: str, embedding: List[float], model: str):
        self.cache_calls.append({"text": text, "embedding": embedding, "model": model})
        key = f"{model}:{text}"
        self._cache[key] = embedding

    async def get_cache_stats(self):
        return {"total_items": len(self._cache)}

    async def invalidate_model(self, model: str):
        count = len([k for k in self._cache.keys() if k.startswith(f"{model}:")])
        self._cache = {k: v for k, v in self._cache.items() if not k.startswith(f"{model}:")}
        return count

    def set_cached(self, text: str, embedding: List[float], model: str = DEFAULT_MODEL):
        """Helper to set cached values for tests."""
        self._cache[f"{model}:{text}"] = embedding


# =============================================================================
# Embedding Generation Tests
# =============================================================================

async def test_embed_single_text():
    """embed() generates embedding for single text."""
    service = EmbeddingService(use_cache=False)

    mock_embedding = [0.1] * DEFAULT_DIMENSIONS
    mock_response = MockResponse(200, {"embeddings": [mock_embedding]})
    mock_session = MockSession({
        "http://localhost:11434/api/embed": mock_response
    })
    service._session = mock_session

    result = await service.embed("Hello world")

    assert result == mock_embedding
    assert len(mock_session.requests) == 1
    req = mock_session.requests[0]
    assert req["json"]["input"] == ["Hello world"]
    assert req["json"]["model"] == DEFAULT_MODEL


async def test_embed_empty_text_raises():
    """embed() raises error for empty text."""
    service = EmbeddingService(use_cache=False)

    with pytest.raises(EmbeddingServiceError) as exc_info:
        await service.embed("")

    assert "empty text" in str(exc_info.value).lower()


async def test_embed_whitespace_only_raises():
    """embed() raises error for whitespace-only text."""
    service = EmbeddingService(use_cache=False)

    with pytest.raises(EmbeddingServiceError):
        await service.embed("   ")


async def test_embed_batch_multiple_texts():
    """embed_batch() generates embeddings for multiple texts."""
    service = EmbeddingService(use_cache=False)

    embeddings = [[0.1] * DEFAULT_DIMENSIONS, [0.2] * DEFAULT_DIMENSIONS]
    mock_response = MockResponse(200, {"embeddings": embeddings})
    mock_session = MockSession({
        "http://localhost:11434/api/embed": mock_response
    })
    service._session = mock_session

    result = await service.embed_batch(["Hello", "World"])

    assert result == embeddings
    req = mock_session.requests[0]
    assert req["json"]["input"] == ["Hello", "World"]


async def test_embed_batch_empty_list():
    """embed_batch() returns empty list for empty input."""
    service = EmbeddingService(use_cache=False)

    result = await service.embed_batch([])

    assert result == []


async def test_embed_batch_all_empty_texts_raises():
    """embed_batch() raises for all empty texts."""
    service = EmbeddingService(use_cache=False)

    with pytest.raises(EmbeddingServiceError) as exc_info:
        await service.embed_batch(["", "  ", ""])

    assert "empty" in str(exc_info.value).lower()


async def test_embed_batch_fills_zero_for_empty():
    """embed_batch() fills zero vector for empty texts in mix."""
    service = EmbeddingService(use_cache=False)

    embedding = [0.5] * DEFAULT_DIMENSIONS
    mock_response = MockResponse(200, {"embeddings": [embedding]})
    mock_session = MockSession({
        "http://localhost:11434/api/embed": mock_response
    })
    service._session = mock_session

    result = await service.embed_batch(["", "Hello", ""])

    assert len(result) == 3
    assert result[0] == [0.0] * DEFAULT_DIMENSIONS
    assert result[1] == embedding
    assert result[2] == [0.0] * DEFAULT_DIMENSIONS


# =============================================================================
# Caching Tests
# =============================================================================

async def test_embed_cache_hit():
    """embed() returns cached embedding on cache hit."""
    mock_cache = MockVectorsAdapter()
    cached_embedding = [0.9] * DEFAULT_DIMENSIONS
    mock_cache.set_cached("Hello", cached_embedding)

    service = EmbeddingService(use_cache=True)
    service._cache = mock_cache
    service._session = MockSession()  # Should not be called

    result = await service.embed("Hello")

    assert result == cached_embedding
    assert len(mock_cache.get_calls) == 1
    assert len(service._session.requests) == 0  # No API call


async def test_embed_cache_miss_stores():
    """embed() stores embedding on cache miss."""
    mock_cache = MockVectorsAdapter()

    service = EmbeddingService(use_cache=True)
    service._cache = mock_cache

    embedding = [0.5] * DEFAULT_DIMENSIONS
    mock_response = MockResponse(200, {"embeddings": [embedding]})
    mock_session = MockSession({
        "http://localhost:11434/api/embed": mock_response
    })
    service._session = mock_session

    result = await service.embed("Hello")

    assert result == embedding
    assert len(mock_cache.cache_calls) == 1
    assert mock_cache.cache_calls[0]["text"] == "Hello"
    assert mock_cache.cache_calls[0]["embedding"] == embedding


async def test_embed_batch_uses_cache():
    """embed_batch() uses cache for individual texts."""
    mock_cache = MockVectorsAdapter()
    cached_embedding = [0.9] * DEFAULT_DIMENSIONS
    mock_cache.set_cached("cached text", cached_embedding)

    service = EmbeddingService(use_cache=True)
    service._cache = mock_cache

    new_embedding = [0.5] * DEFAULT_DIMENSIONS
    mock_response = MockResponse(200, {"embeddings": [new_embedding]})
    mock_session = MockSession({
        "http://localhost:11434/api/embed": mock_response
    })
    service._session = mock_session

    result = await service.embed_batch(["cached text", "new text"])

    assert result[0] == cached_embedding
    assert result[1] == new_embedding
    # Only one API call for uncached text
    assert len(mock_session.requests) == 1


async def test_cache_stats():
    """get_cache_stats() returns cache statistics."""
    mock_cache = MockVectorsAdapter()
    mock_cache._cache["item1"] = [0.1]
    mock_cache._cache["item2"] = [0.2]

    service = EmbeddingService(use_cache=True)
    service._cache = mock_cache

    stats = await service.get_cache_stats()

    assert stats["total_items"] == 2


async def test_cache_disabled():
    """get_cache_stats() returns None when cache disabled."""
    service = EmbeddingService(use_cache=False)

    stats = await service.get_cache_stats()

    assert stats is None


async def test_invalidate_cache():
    """invalidate_cache() clears cached embeddings."""
    mock_cache = MockVectorsAdapter()
    mock_cache._cache[f"{DEFAULT_MODEL}:text1"] = [0.1]
    mock_cache._cache[f"{DEFAULT_MODEL}:text2"] = [0.2]

    service = EmbeddingService(use_cache=True)
    service._cache = mock_cache

    count = await service.invalidate_cache()

    assert count == 2
    assert len(mock_cache._cache) == 0


# =============================================================================
# Similarity Tests
# =============================================================================

async def test_similarity_identical_vectors():
    """similarity() returns 1.0 for identical vectors."""
    service = EmbeddingService(use_cache=False)

    vec = [1.0, 2.0, 3.0]
    result = await service.similarity(vec, vec)

    assert abs(result - 1.0) < 0.001


async def test_similarity_orthogonal_vectors():
    """similarity() returns 0.0 for orthogonal vectors."""
    service = EmbeddingService(use_cache=False)

    vec1 = [1.0, 0.0, 0.0]
    vec2 = [0.0, 1.0, 0.0]
    result = await service.similarity(vec1, vec2)

    assert abs(result - 0.0) < 0.001


async def test_similarity_opposite_vectors():
    """similarity() returns -1.0 for opposite vectors."""
    service = EmbeddingService(use_cache=False)

    vec1 = [1.0, 0.0, 0.0]
    vec2 = [-1.0, 0.0, 0.0]
    result = await service.similarity(vec1, vec2)

    assert abs(result - (-1.0)) < 0.001


async def test_similarity_different_dimensions_raises():
    """similarity() raises for different dimension vectors."""
    service = EmbeddingService(use_cache=False)

    vec1 = [1.0, 2.0, 3.0]
    vec2 = [1.0, 2.0]

    with pytest.raises(ValueError):
        await service.similarity(vec1, vec2)


async def test_similarity_zero_vector():
    """similarity() returns 0.0 when one vector is zero."""
    service = EmbeddingService(use_cache=False)

    vec1 = [1.0, 2.0, 3.0]
    vec2 = [0.0, 0.0, 0.0]
    result = await service.similarity(vec1, vec2)

    assert result == 0.0


# =============================================================================
# find_most_similar Tests
# =============================================================================

async def test_find_most_similar():
    """find_most_similar() returns top-k results sorted by similarity."""
    service = EmbeddingService(use_cache=False)

    query = [1.0, 0.0, 0.0]
    candidates = [
        [0.5, 0.5, 0.0],   # Some similarity
        [1.0, 0.0, 0.0],   # Perfect match
        [0.0, 1.0, 0.0],   # Orthogonal
    ]

    result = await service.find_most_similar(query, candidates, top_k=2)

    assert len(result) == 2
    assert result[0][0] == 1  # Perfect match at index 1
    assert abs(result[0][1] - 1.0) < 0.001


async def test_find_most_similar_respects_top_k():
    """find_most_similar() limits results to top_k."""
    service = EmbeddingService(use_cache=False)

    query = [1.0, 0.0, 0.0]
    candidates = [[1.0, 0.0, 0.0]] * 10

    result = await service.find_most_similar(query, candidates, top_k=3)

    assert len(result) == 3


# =============================================================================
# Model Availability Tests
# =============================================================================

async def test_is_model_available_true():
    """is_model_available() returns True when model exists."""
    service = EmbeddingService(use_cache=False)

    mock_response = MockResponse(200, {"name": DEFAULT_MODEL})
    mock_session = MockSession({
        "http://localhost:11434/api/show": mock_response
    })
    service._session = mock_session

    result = await service.is_model_available()

    assert result is True


async def test_is_model_available_false():
    """is_model_available() returns False when model doesn't exist."""
    service = EmbeddingService(use_cache=False)

    mock_response = MockResponse(404)
    mock_session = MockSession({
        "http://localhost:11434/api/show": mock_response
    })
    service._session = mock_session

    result = await service.is_model_available()

    assert result is False


async def test_get_model_info():
    """get_model_info() returns model information."""
    service = EmbeddingService(use_cache=False)

    model_info = {"name": DEFAULT_MODEL, "size": 1234}
    mock_response = MockResponse(200, model_info)
    mock_session = MockSession({
        "http://localhost:11434/api/show": mock_response
    })
    service._session = mock_session

    result = await service.get_model_info()

    assert result == model_info


async def test_get_model_info_not_found():
    """get_model_info() returns None when model not found."""
    service = EmbeddingService(use_cache=False)

    mock_response = MockResponse(404)
    mock_session = MockSession({
        "http://localhost:11434/api/show": mock_response
    })
    service._session = mock_session

    result = await service.get_model_info()

    assert result is None


# =============================================================================
# Error Handling Tests
# =============================================================================

async def test_embed_api_error():
    """embed() raises EmbeddingServiceError on API error."""
    service = EmbeddingService(use_cache=False)

    mock_response = MockResponse(500, text="Internal Server Error")
    mock_session = MockSession({
        "http://localhost:11434/api/embed": mock_response
    })
    service._session = mock_session

    with pytest.raises(EmbeddingServiceError) as exc_info:
        await service.embed("Hello")

    assert "500" in str(exc_info.value)


async def test_embed_wrong_embedding_count():
    """embed() raises error when API returns wrong count."""
    service = EmbeddingService(use_cache=False)

    # Return 2 embeddings for 1 text
    mock_response = MockResponse(200, {"embeddings": [[0.1], [0.2]]})
    mock_session = MockSession({
        "http://localhost:11434/api/embed": mock_response
    })
    service._session = mock_session

    with pytest.raises(EmbeddingServiceError) as exc_info:
        await service.embed("Hello")

    assert "expected" in str(exc_info.value).lower()


# =============================================================================
# Session Management Tests
# =============================================================================

async def test_close_session():
    """close() closes the HTTP session."""
    service = EmbeddingService(use_cache=False)

    mock_session = MockSession()
    service._session = mock_session

    await service.close()

    assert mock_session.closed is True


async def test_session_created_lazily():
    """Session is not created until first use."""
    service = EmbeddingService(use_cache=False)

    assert service._session is None


# =============================================================================
# Property Tests
# =============================================================================

def test_model_property():
    """model property returns current model name."""
    service = EmbeddingService(model="custom-model", use_cache=False)

    assert service.model == "custom-model"


def test_dimensions_property():
    """dimensions property returns expected dimensions."""
    service = EmbeddingService(use_cache=False)

    assert service.dimensions == DEFAULT_DIMENSIONS


def test_repr():
    """__repr__ returns descriptive string."""
    service = EmbeddingService(model="test-model", use_cache=False)

    result = repr(service)

    assert "test-model" in result
    assert "disabled" in result


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_embedding_service():
    """create_embedding_service() creates configured instance."""
    service = create_embedding_service(
        ollama_host="http://custom:11434",
        model="custom-model",
        use_cache=False,
    )

    assert service.model == "custom-model"
    assert service._ollama_host == "http://custom:11434"
    assert service._cache is None
