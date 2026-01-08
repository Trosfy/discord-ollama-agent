"""Tests for DynamoDB vector storage."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from app.implementations.vector_storage import DynamoDBVectorStorage
from app.interfaces.storage import VectorChunk


@pytest.fixture
def vector_storage():
    """Create vector storage instance."""
    return DynamoDBVectorStorage()


@pytest.fixture
def sample_chunks():
    """Sample chunks for testing."""
    return [
        {
            "chunk_id": "chunk-1",
            "chunk_text": "First chunk of text",
            "embedding_vector": [0.1, 0.2, 0.3] * 341 + [0.4],  # 1024 dimensions
            "chunk_index": 0,
            "token_count": 5
        },
        {
            "chunk_id": "chunk-2",
            "chunk_text": "Second chunk of text",
            "embedding_vector": [0.2, 0.3, 0.4] * 341 + [0.5],
            "chunk_index": 1,
            "token_count": 5
        },
        {
            "chunk_id": "chunk-3",
            "chunk_text": "Third chunk of text",
            "embedding_vector": [0.3, 0.4, 0.5] * 341 + [0.6],
            "chunk_index": 2,
            "token_count": 5
        }
    ]


def test_hash_url():
    """Test URL hashing."""
    url1 = "https://example.com/page1"
    url2 = "https://example.com/page2"

    hash1 = DynamoDBVectorStorage._hash_url(url1)
    hash2 = DynamoDBVectorStorage._hash_url(url2)

    # Hashes should be different for different URLs
    assert hash1 != hash2

    # Hash should be consistent
    assert hash1 == DynamoDBVectorStorage._hash_url(url1)

    # Hash should be 64 characters (SHA256 hex)
    assert len(hash1) == 64


def test_cosine_similarity():
    """Test cosine similarity calculation."""
    # Identical vectors
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0, 0.0]
    assert DynamoDBVectorStorage._cosine_similarity(vec1, vec2) == pytest.approx(1.0)

    # Orthogonal vectors
    vec3 = [1.0, 0.0, 0.0]
    vec4 = [0.0, 1.0, 0.0]
    assert DynamoDBVectorStorage._cosine_similarity(vec3, vec4) == pytest.approx(0.0)

    # Opposite vectors
    vec5 = [1.0, 0.0, 0.0]
    vec6 = [-1.0, 0.0, 0.0]
    assert DynamoDBVectorStorage._cosine_similarity(vec5, vec6) == pytest.approx(-1.0)

    # Similar vectors
    vec7 = [1.0, 1.0, 1.0]
    vec8 = [1.0, 1.0, 0.9]
    similarity = DynamoDBVectorStorage._cosine_similarity(vec7, vec8)
    assert 0.9 < similarity < 1.0


def test_cosine_similarity_dimension_mismatch():
    """Test that dimension mismatch raises error."""
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0]

    with pytest.raises(ValueError, match="Vector dimensions must match"):
        DynamoDBVectorStorage._cosine_similarity(vec1, vec2)


def test_cosine_similarity_zero_vectors():
    """Test cosine similarity with zero vectors."""
    vec1 = [0.0, 0.0, 0.0]
    vec2 = [1.0, 1.0, 1.0]

    # Should return 0.0 for zero vector
    assert DynamoDBVectorStorage._cosine_similarity(vec1, vec2) == 0.0


@pytest.mark.asyncio
@pytest.mark.skip(reason="Integration test - requires DynamoDB running at dynamodb-local:8000")
async def test_initialize_table(vector_storage):
    """Test table initialization."""
    with patch('aioboto3.Session') as mock_session:
        # Setup mock
        mock_table = AsyncMock()
        mock_table.wait_until_exists = AsyncMock()

        mock_dynamodb = AsyncMock()
        mock_dynamodb.create_table = AsyncMock(return_value=mock_table)
        mock_dynamodb.__aenter__ = AsyncMock(return_value=mock_dynamodb)
        mock_dynamodb.__aexit__ = AsyncMock()

        mock_client = AsyncMock()
        mock_client.update_time_to_live = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        mock_resource = MagicMock(return_value=mock_dynamodb)
        mock_client_func = MagicMock(return_value=mock_client)

        mock_session_instance = MagicMock()
        mock_session_instance.resource = mock_resource
        mock_session_instance.client = mock_client_func
        mock_session.return_value = mock_session_instance

        # Call initialize_table
        await vector_storage.initialize_table()

        # Verify table was created
        mock_dynamodb.create_table.assert_called_once()
        call_args = mock_dynamodb.create_table.call_args
        assert call_args[1]["TableName"] == "webpage_chunks"
        assert call_args[1]["BillingMode"] == "PAY_PER_REQUEST"

        # Verify TTL was enabled
        mock_client.update_time_to_live.assert_called_once()
        ttl_args = mock_client.update_time_to_live.call_args
        assert ttl_args[1]["TableName"] == "webpage_chunks"
        assert ttl_args[1]["TimeToLiveSpecification"]["Enabled"] is True


@pytest.mark.asyncio
@pytest.mark.skip(reason="Integration test - requires DynamoDB running at dynamodb-local:8000")
async def test_store_chunks_success(vector_storage, sample_chunks):
    """Test successful chunk storage."""
    url = "https://example.com/test"
    ttl_hours = 2

    with patch('aioboto3.Session') as mock_session:
        # Setup mock
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

        # Call store_chunks
        count = await vector_storage.store_chunks(url, sample_chunks, ttl_hours)

        # Verify result
        assert count == 3

        # Verify batch writer was called
        assert mock_batch.put_item.call_count == 3


@pytest.mark.asyncio
async def test_store_chunks_empty_url_raises_error(vector_storage, sample_chunks):
    """Test that empty URL raises ValueError."""
    with pytest.raises(ValueError, match="URL cannot be empty"):
        await vector_storage.store_chunks("", sample_chunks, 2)


@pytest.mark.asyncio
async def test_store_chunks_empty_chunks_raises_error(vector_storage):
    """Test that empty chunks list raises ValueError."""
    with pytest.raises(ValueError, match="Chunks list cannot be empty"):
        await vector_storage.store_chunks("https://example.com", [], 2)


@pytest.mark.asyncio
@pytest.mark.skip(reason="Integration test - requires DynamoDB running at dynamodb-local:8000")
async def test_get_chunks_by_url_success(vector_storage):
    """Test successful chunk retrieval."""
    url = "https://example.com/test"
    url_hash = DynamoDBVectorStorage._hash_url(url)

    # Create mock items (not expired)
    future_ttl = int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    mock_items = [
        {
            "url_hash": url_hash,
            "chunk_id": "chunk-1",
            "chunk_text": "First chunk",
            "embedding_vector": [0.1, 0.2, 0.3] * 341 + [0.4],
            "chunk_index": 0,
            "token_count": 3,
            "source_url": url,
            "created_at": datetime.utcnow().isoformat(),
            "ttl": future_ttl
        },
        {
            "url_hash": url_hash,
            "chunk_id": "chunk-2",
            "chunk_text": "Second chunk",
            "embedding_vector": [0.2, 0.3, 0.4] * 341 + [0.5],
            "chunk_index": 1,
            "token_count": 3,
            "source_url": url,
            "created_at": datetime.utcnow().isoformat(),
            "ttl": future_ttl
        }
    ]

    with patch('aioboto3.Session') as mock_session:
        # Setup mock
        mock_table = AsyncMock()
        mock_table.query = AsyncMock(return_value={"Items": mock_items})

        mock_dynamodb = AsyncMock()
        mock_dynamodb.Table = AsyncMock(return_value=mock_table)
        mock_dynamodb.__aenter__ = AsyncMock(return_value=mock_dynamodb)
        mock_dynamodb.__aexit__ = AsyncMock()

        mock_session_instance = MagicMock()
        mock_session_instance.resource = MagicMock(return_value=mock_dynamodb)
        mock_session.return_value = mock_session_instance

        # Call get_chunks_by_url
        chunks = await vector_storage.get_chunks_by_url(url)

        # Verify result
        assert chunks is not None
        assert len(chunks) == 2
        assert all(isinstance(chunk, VectorChunk) for chunk in chunks)
        assert chunks[0].chunk_id == "chunk-1"
        assert chunks[1].chunk_id == "chunk-2"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Integration test - requires DynamoDB running at dynamodb-local:8000")
async def test_get_chunks_by_url_expired_chunks(vector_storage):
    """Test that expired chunks are filtered out."""
    url = "https://example.com/test"
    url_hash = DynamoDBVectorStorage._hash_url(url)

    # Create mock items (expired)
    past_ttl = int((datetime.utcnow() - timedelta(hours=1)).timestamp())
    mock_items = [
        {
            "url_hash": url_hash,
            "chunk_id": "chunk-1",
            "chunk_text": "Expired chunk",
            "embedding_vector": [0.1] * 1024,
            "chunk_index": 0,
            "token_count": 2,
            "source_url": url,
            "created_at": datetime.utcnow().isoformat(),
            "ttl": past_ttl  # Expired
        }
    ]

    with patch('aioboto3.Session') as mock_session:
        mock_table = AsyncMock()
        mock_table.query = AsyncMock(return_value={"Items": mock_items})

        mock_dynamodb = AsyncMock()
        mock_dynamodb.Table = AsyncMock(return_value=mock_table)
        mock_dynamodb.__aenter__ = AsyncMock(return_value=mock_dynamodb)
        mock_dynamodb.__aexit__ = AsyncMock()

        mock_session_instance = MagicMock()
        mock_session_instance.resource = MagicMock(return_value=mock_dynamodb)
        mock_session.return_value = mock_session_instance

        # Call get_chunks_by_url
        chunks = await vector_storage.get_chunks_by_url(url)

        # Should return None (all chunks expired)
        assert chunks is None


@pytest.mark.asyncio
@pytest.mark.skip(reason="Integration test - requires DynamoDB running at dynamodb-local:8000")
async def test_get_chunks_by_url_not_found(vector_storage):
    """Test retrieval when URL not found."""
    url = "https://example.com/notfound"

    with patch('aioboto3.Session') as mock_session:
        # Setup mock with empty results
        mock_table = AsyncMock()
        mock_table.query = AsyncMock(return_value={"Items": []})

        mock_dynamodb = AsyncMock()
        mock_dynamodb.Table = AsyncMock(return_value=mock_table)
        mock_dynamodb.__aenter__ = AsyncMock(return_value=mock_dynamodb)
        mock_dynamodb.__aexit__ = AsyncMock()

        mock_session_instance = MagicMock()
        mock_session_instance.resource = MagicMock(return_value=mock_dynamodb)
        mock_session.return_value = mock_session_instance

        # Call get_chunks_by_url
        chunks = await vector_storage.get_chunks_by_url(url)

        # Should return None
        assert chunks is None


@pytest.mark.asyncio
@pytest.mark.skip(reason="Integration test - requires DynamoDB running at dynamodb-local:8000")
async def test_search_similar_success(vector_storage):
    """Test similar chunk search."""
    query_embedding = [0.15, 0.25, 0.35] * 341 + [0.45]  # Close to first chunk

    # Create mock items
    future_ttl = int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    mock_items = [
        {
            "url_hash": "hash1",
            "chunk_id": "chunk-1",
            "chunk_text": "First chunk",
            "embedding_vector": [0.1, 0.2, 0.3] * 341 + [0.4],  # Most similar
            "chunk_index": 0,
            "token_count": 3,
            "source_url": "https://example.com/1",
            "created_at": datetime.utcnow().isoformat(),
            "ttl": future_ttl
        },
        {
            "url_hash": "hash2",
            "chunk_id": "chunk-2",
            "chunk_text": "Second chunk",
            "embedding_vector": [0.9, 0.8, 0.7] * 341 + [0.6],  # Less similar
            "chunk_index": 0,
            "token_count": 3,
            "source_url": "https://example.com/2",
            "created_at": datetime.utcnow().isoformat(),
            "ttl": future_ttl
        }
    ]

    with patch('aioboto3.Session') as mock_session:
        # Setup mock
        mock_table = AsyncMock()
        mock_table.scan = AsyncMock(return_value={"Items": mock_items})

        mock_dynamodb = AsyncMock()
        mock_dynamodb.Table = AsyncMock(return_value=mock_table)
        mock_dynamodb.__aenter__ = AsyncMock(return_value=mock_dynamodb)
        mock_dynamodb.__aexit__ = AsyncMock()

        mock_session_instance = MagicMock()
        mock_session_instance.resource = MagicMock(return_value=mock_dynamodb)
        mock_session.return_value = mock_session_instance

        # Call search_similar
        results = await vector_storage.search_similar(query_embedding, top_k=2)

        # Verify results are sorted by similarity
        assert len(results) == 2
        assert results[0].chunk_id == "chunk-1"  # Most similar first


@pytest.mark.asyncio
async def test_search_similar_empty_embedding_raises_error(vector_storage):
    """Test that empty embedding raises ValueError."""
    with pytest.raises(ValueError, match="Query embedding cannot be empty"):
        await vector_storage.search_similar([], top_k=5)


@pytest.mark.asyncio
async def test_search_similar_invalid_top_k_raises_error(vector_storage):
    """Test that invalid top_k raises ValueError."""
    query_embedding = [0.1] * 1024

    with pytest.raises(ValueError, match="top_k must be positive"):
        await vector_storage.search_similar(query_embedding, top_k=0)

    with pytest.raises(ValueError, match="top_k must be positive"):
        await vector_storage.search_similar(query_embedding, top_k=-1)


@pytest.mark.asyncio
@pytest.mark.skip(reason="Integration test - requires DynamoDB running at dynamodb-local:8000")
async def test_search_similar_filters_expired(vector_storage):
    """Test that search filters expired chunks."""
    query_embedding = [0.1] * 1024

    # Create mix of valid and expired items
    future_ttl = int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    past_ttl = int((datetime.utcnow() - timedelta(hours=1)).timestamp())

    mock_items = [
        {
            "url_hash": "hash1",
            "chunk_id": "chunk-valid",
            "chunk_text": "Valid chunk",
            "embedding_vector": [0.1] * 1024,
            "chunk_index": 0,
            "token_count": 2,
            "source_url": "https://example.com/1",
            "created_at": datetime.utcnow().isoformat(),
            "ttl": future_ttl  # Valid
        },
        {
            "url_hash": "hash2",
            "chunk_id": "chunk-expired",
            "chunk_text": "Expired chunk",
            "embedding_vector": [0.2] * 1024,
            "chunk_index": 0,
            "token_count": 2,
            "source_url": "https://example.com/2",
            "created_at": datetime.utcnow().isoformat(),
            "ttl": past_ttl  # Expired
        }
    ]

    with patch('aioboto3.Session') as mock_session:
        mock_table = AsyncMock()
        mock_table.scan = AsyncMock(return_value={"Items": mock_items})

        mock_dynamodb = AsyncMock()
        mock_dynamodb.Table = AsyncMock(return_value=mock_table)
        mock_dynamodb.__aenter__ = AsyncMock(return_value=mock_dynamodb)
        mock_dynamodb.__aexit__ = AsyncMock()

        mock_session_instance = MagicMock()
        mock_session_instance.resource = MagicMock(return_value=mock_dynamodb)
        mock_session.return_value = mock_session_instance

        # Call search_similar
        results = await vector_storage.search_similar(query_embedding, top_k=5)

        # Should only return valid chunk
        assert len(results) == 1
        assert results[0].chunk_id == "chunk-valid"
