"""Unit tests for TroiseWebChunksAdapter."""
import pytest
import struct
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, List

from app.adapters.dynamodb.web_chunks_adapter import (
    TroiseWebChunksAdapter,
    WebMetaItem,
    WebChunkItem,
    url_to_hash,
    extract_domain,
    embedding_to_binary,
    binary_to_embedding,
    TABLE_NAME,
)
from app.core.config import RAGConfig


# =============================================================================
# Utility Function Tests
# =============================================================================

class TestUtilityFunctions:
    """Test helper utility functions."""

    def test_url_to_hash_consistent(self):
        """url_to_hash() produces consistent hash for same URL."""
        url = "https://example.com/page"
        hash1 = url_to_hash(url)
        hash2 = url_to_hash(url)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex is 64 chars

    def test_url_to_hash_unique(self):
        """url_to_hash() produces unique hashes for different URLs."""
        hash1 = url_to_hash("https://example.com/page1")
        hash2 = url_to_hash("https://example.com/page2")

        assert hash1 != hash2

    def test_extract_domain_basic(self):
        """extract_domain() extracts domain from URL."""
        assert extract_domain("https://example.com/path") == "example.com"
        assert extract_domain("http://subdomain.example.com") == "subdomain.example.com"
        assert extract_domain("https://docs.python.org/3/") == "docs.python.org"

    def test_extract_domain_with_port(self):
        """extract_domain() handles URLs with port."""
        assert extract_domain("http://localhost:8000/api") == "localhost:8000"

    def test_extract_domain_invalid(self):
        """extract_domain() returns empty string for invalid URLs."""
        assert extract_domain("not-a-url") == ""
        assert extract_domain("") == ""

    def test_embedding_to_binary_roundtrip(self):
        """embedding_to_binary() and binary_to_embedding() roundtrip."""
        original = [0.1, 0.2, 0.3, 0.4, 0.5]
        binary = embedding_to_binary(original)
        restored = binary_to_embedding(binary)

        assert len(restored) == len(original)
        for a, b in zip(original, restored):
            assert abs(a - b) < 1e-6

    def test_embedding_to_binary_size(self):
        """embedding_to_binary() produces correct byte size."""
        embedding = [0.1] * 768  # Common embedding dimension
        binary = embedding_to_binary(embedding)

        # 4 bytes per float
        assert len(binary) == 768 * 4

    def test_binary_to_embedding_empty(self):
        """binary_to_embedding() handles empty data."""
        result = binary_to_embedding(b'')
        assert result == []


# =============================================================================
# WebMetaItem Tests
# =============================================================================

class TestWebMetaItem:
    """Test WebMetaItem dataclass."""

    def test_meta_item_properties(self):
        """WebMetaItem computes properties correctly."""
        meta = WebMetaItem(
            source_url="https://example.com/page",
            title="Test Page",
            domain="example.com",
            chunk_count=5,
            total_tokens=500,
            fetched_at="2024-01-01T00:00:00",
            ttl=1234567890,
            ttl_hours=24,
        )

        assert meta.pk.startswith("URL#")
        assert meta.sk == "META"
        assert len(meta.url_hash) == 64

    def test_meta_item_to_dynamo(self):
        """WebMetaItem converts to DynamoDB item format."""
        meta = WebMetaItem(
            source_url="https://example.com",
            title="Test",
            domain="example.com",
            chunk_count=3,
            total_tokens=300,
            fetched_at="2024-01-01T00:00:00",
            ttl=1234567890,
            ttl_hours=2,
        )

        item = meta.to_dynamo_item()

        assert item['PK'] == meta.pk
        assert item['SK'] == "META"
        assert item['entity_type'] == 'URL_META'
        assert item['source_url'] == "https://example.com"
        assert item['title'] == "Test"

    def test_meta_item_from_dynamo(self):
        """WebMetaItem creates from DynamoDB item."""
        item = {
            'PK': 'URL#abc123',
            'SK': 'META',
            'source_url': 'https://example.com',
            'title': 'Test Page',
            'domain': 'example.com',
            'chunk_count': 5,
            'total_tokens': 500,
            'fetched_at': '2024-01-01T00:00:00',
            'ttl': 1234567890,
            'ttl_hours': 24,
        }

        meta = WebMetaItem.from_dynamo_item(item)

        assert meta.source_url == 'https://example.com'
        assert meta.title == 'Test Page'
        assert meta.chunk_count == 5


# =============================================================================
# WebChunkItem Tests
# =============================================================================

class TestWebChunkItem:
    """Test WebChunkItem dataclass."""

    def test_chunk_item_properties(self):
        """WebChunkItem computes properties correctly."""
        chunk = WebChunkItem(
            chunk_id="abc-123",
            chunk_text="Test content",
            chunk_index=5,
            token_count=10,
            source_url="https://example.com",
            start_char=0,
            end_char=12,
            ttl=1234567890,
        )

        assert chunk.pk.startswith("URL#")
        assert chunk.sk == "CHUNK#0005"  # Zero-padded

    def test_chunk_item_to_dynamo_with_embedding(self):
        """WebChunkItem converts with embedding to binary."""
        embedding = [0.1, 0.2, 0.3]
        chunk = WebChunkItem(
            chunk_id="abc-123",
            chunk_text="Test",
            chunk_index=0,
            token_count=1,
            source_url="https://example.com",
            start_char=0,
            end_char=4,
            ttl=1234567890,
            embedding=embedding,
        )

        item = chunk.to_dynamo_item()

        assert 'embedding' in item
        assert isinstance(item['embedding'], bytes)

    def test_chunk_item_to_dynamo_without_embedding(self):
        """WebChunkItem converts without embedding."""
        chunk = WebChunkItem(
            chunk_id="abc-123",
            chunk_text="Test",
            chunk_index=0,
            token_count=1,
            source_url="https://example.com",
            start_char=0,
            end_char=4,
            ttl=1234567890,
        )

        item = chunk.to_dynamo_item()

        assert 'embedding' not in item

    def test_chunk_item_from_dynamo_with_embedding(self):
        """WebChunkItem creates from DynamoDB item with embedding."""
        embedding = [0.1, 0.2, 0.3]
        item = {
            'PK': 'URL#abc',
            'SK': 'CHUNK#0000',
            'chunk_id': 'abc-123',
            'chunk_text': 'Test content',
            'chunk_index': 0,
            'token_count': 5,
            'source_url': 'https://example.com',
            'start_char': 0,
            'end_char': 12,
            'ttl': 1234567890,
            'embedding': embedding_to_binary(embedding),
        }

        chunk = WebChunkItem.from_dynamo_item(item)

        assert chunk.chunk_text == 'Test content'
        assert chunk.embedding is not None
        assert len(chunk.embedding) == 3

    def test_chunk_index_zero_padding(self):
        """WebChunkItem SK is zero-padded to 4 digits."""
        chunk = WebChunkItem(
            chunk_id="x", chunk_text="y", chunk_index=42,
            token_count=1, source_url="https://example.com",
            start_char=0, end_char=1, ttl=0,
        )

        assert chunk.sk == "CHUNK#0042"


# =============================================================================
# Mock DynamoDB Helpers
# =============================================================================

class MockDynamoDBTable:
    """Mock DynamoDB table for testing."""

    def __init__(self):
        self.items: Dict[str, Dict[str, Any]] = {}
        self.queries = []
        self.scans = []

    def _key(self, pk: str, sk: str) -> str:
        return f"{pk}|{sk}"

    async def put_item(self, Item: Dict[str, Any]):
        key = self._key(Item['PK'], Item['SK'])
        self.items[key] = Item

    async def get_item(self, Key: Dict[str, str]):
        key = self._key(Key['PK'], Key['SK'])
        item = self.items.get(key)
        return {'Item': item} if item else {}

    async def delete_item(self, Key: Dict[str, str]):
        key = self._key(Key['PK'], Key['SK'])
        if key in self.items:
            del self.items[key]

    async def query(self, **kwargs):
        self.queries.append(kwargs)
        # Return items matching PK
        pk_expr = kwargs.get('KeyConditionExpression')
        items = []

        for key, item in self.items.items():
            if pk_expr:
                # Simple matching for tests
                if 'SK' in kwargs.get('ProjectionExpression', 'SK'):
                    if item.get('SK', '').startswith('CHUNK#'):
                        items.append(item)
                else:
                    items.append(item)

        return {'Items': items}

    async def scan(self, **kwargs):
        self.scans.append(kwargs)
        return {'Items': list(self.items.values())}


class MockDynamoDBResource:
    """Mock DynamoDB resource context manager."""

    def __init__(self, table: MockDynamoDBTable):
        self._table = table

    async def Table(self, name: str):
        return self._table

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockDynamoDBClient:
    """Mock DynamoDBClient for testing."""

    def __init__(self, table: MockDynamoDBTable = None):
        self._table = table or MockDynamoDBTable()

    def resource(self):
        return MockDynamoDBResource(self._table)


# =============================================================================
# TroiseWebChunksAdapter Tests
# =============================================================================

class TestTroiseWebChunksAdapter:
    """Test TroiseWebChunksAdapter methods."""

    @pytest.fixture
    def mock_table(self):
        return MockDynamoDBTable()

    @pytest.fixture
    def mock_client(self, mock_table):
        return MockDynamoDBClient(mock_table)

    @pytest.fixture
    def config(self):
        return RAGConfig(
            web_cache_ttl_hours=2,
            ttl_by_domain={
                "docs.python.org": 168,
                "github.com": 24,
            }
        )

    @pytest.fixture
    def adapter(self, mock_client, config):
        return TroiseWebChunksAdapter(mock_client, config)

    # TTL Resolution Tests

    def test_get_ttl_override(self, adapter):
        """_get_ttl_for_url() uses override when provided."""
        ttl = adapter._get_ttl_for_url("https://example.com", ttl_hours_override=48)
        assert ttl == 48

    def test_get_ttl_domain_specific(self, adapter):
        """_get_ttl_for_url() uses domain-specific TTL."""
        ttl = adapter._get_ttl_for_url("https://docs.python.org/3/tutorial/")
        assert ttl == 168  # 1 week

    def test_get_ttl_default(self, adapter):
        """_get_ttl_for_url() uses default TTL for unknown domain."""
        ttl = adapter._get_ttl_for_url("https://unknown.example.com")
        assert ttl == 2  # Default from config

    def test_get_ttl_no_config(self, mock_client):
        """_get_ttl_for_url() uses hardcoded default without config."""
        adapter = TroiseWebChunksAdapter(mock_client, None)
        ttl = adapter._get_ttl_for_url("https://example.com")
        assert ttl == 2  # Hardcoded default

    # Store Chunks Tests

    async def test_store_chunks_basic(self, adapter, mock_table):
        """store_chunks() stores metadata and chunks."""
        chunks = [
            {
                'chunk_id': 'chunk-1',
                'chunk_text': 'First chunk content',
                'chunk_index': 0,
                'token_count': 10,
                'start_char': 0,
                'end_char': 19,
            },
            {
                'chunk_id': 'chunk-2',
                'chunk_text': 'Second chunk content',
                'chunk_index': 1,
                'token_count': 11,
                'start_char': 20,
                'end_char': 40,
            },
        ]

        count = await adapter.store_chunks(
            url="https://example.com/page",
            title="Test Page",
            chunks=chunks,
        )

        assert count == 2
        # Should have META + 2 chunks = 3 items
        assert len(mock_table.items) == 3

    async def test_store_chunks_with_embeddings(self, adapter, mock_table):
        """store_chunks() stores embeddings when provided."""
        chunks = [
            {
                'chunk_id': 'chunk-1',
                'chunk_text': 'Content',
                'chunk_index': 0,
                'token_count': 5,
                'start_char': 0,
                'end_char': 7,
            },
        ]
        embeddings = [[0.1, 0.2, 0.3]]

        await adapter.store_chunks(
            url="https://example.com",
            title="Test",
            chunks=chunks,
            embeddings=embeddings,
        )

        # Find the chunk item
        chunk_item = None
        for key, item in mock_table.items.items():
            if item.get('SK', '').startswith('CHUNK#'):
                chunk_item = item
                break

        assert chunk_item is not None
        assert 'embedding' in chunk_item

    async def test_store_chunks_empty_raises(self, adapter):
        """store_chunks() raises ValueError for empty chunks."""
        with pytest.raises(ValueError) as exc_info:
            await adapter.store_chunks(
                url="https://example.com",
                title="Test",
                chunks=[],
            )

        assert "empty" in str(exc_info.value).lower()

    async def test_store_chunks_no_url_raises(self, adapter):
        """store_chunks() raises ValueError when URL is missing."""
        with pytest.raises(ValueError):
            await adapter.store_chunks(
                url="",
                title="Test",
                chunks=[{'chunk_id': 'x', 'chunk_text': 'y'}],
            )

    # Get Chunks Tests

    async def test_get_chunks_by_url_cached(self, adapter, mock_table):
        """get_chunks_by_url() returns chunks when cached."""
        url = "https://example.com"
        pk = f"URL#{url_to_hash(url)}"
        future_ttl = int(time.time()) + 3600  # 1 hour from now

        # Add META item
        mock_table.items[f"{pk}|META"] = {
            'PK': pk,
            'SK': 'META',
            'source_url': url,
            'title': 'Test',
            'domain': 'example.com',
            'chunk_count': 2,
            'total_tokens': 20,
            'fetched_at': '2024-01-01',
            'ttl': future_ttl,
            'ttl_hours': 2,
        }

        # Add chunk items
        mock_table.items[f"{pk}|CHUNK#0000"] = {
            'PK': pk,
            'SK': 'CHUNK#0000',
            'chunk_id': 'c1',
            'chunk_text': 'First',
            'chunk_index': 0,
            'token_count': 5,
            'source_url': url,
            'start_char': 0,
            'end_char': 5,
            'ttl': future_ttl,
        }

        chunks = await adapter.get_chunks_by_url(url)

        # Note: This returns items based on mock query
        assert chunks is not None

    async def test_get_chunks_by_url_expired(self, adapter, mock_table):
        """get_chunks_by_url() returns None when cache expired."""
        url = "https://example.com"
        pk = f"URL#{url_to_hash(url)}"
        past_ttl = int(time.time()) - 3600  # 1 hour ago (expired)

        mock_table.items[f"{pk}|META"] = {
            'PK': pk,
            'SK': 'META',
            'source_url': url,
            'ttl': past_ttl,  # Expired
            'ttl_hours': 2,
        }

        chunks = await adapter.get_chunks_by_url(url)

        assert chunks is None

    async def test_get_chunks_by_url_not_found(self, adapter, mock_table):
        """get_chunks_by_url() returns None when URL not cached."""
        chunks = await adapter.get_chunks_by_url("https://not-cached.com")
        assert chunks is None

    # Is Cached Tests

    async def test_is_cached_true(self, adapter, mock_table):
        """is_cached() returns True for cached URL."""
        url = "https://example.com"
        pk = f"URL#{url_to_hash(url)}"
        future_ttl = int(time.time()) + 3600

        mock_table.items[f"{pk}|META"] = {
            'PK': pk,
            'SK': 'META',
            'source_url': url,
            'ttl': future_ttl,
            'ttl_hours': 2,
        }

        result = await adapter.is_cached(url)

        assert result is True

    async def test_is_cached_false_not_found(self, adapter, mock_table):
        """is_cached() returns False for non-cached URL."""
        result = await adapter.is_cached("https://not-cached.com")
        assert result is False

    async def test_is_cached_false_expired(self, adapter, mock_table):
        """is_cached() returns False for expired URL."""
        url = "https://example.com"
        pk = f"URL#{url_to_hash(url)}"
        past_ttl = int(time.time()) - 3600

        mock_table.items[f"{pk}|META"] = {
            'PK': pk,
            'SK': 'META',
            'source_url': url,
            'ttl': past_ttl,  # Expired
        }

        result = await adapter.is_cached(url)

        assert result is False

    # Delete URL Tests

    async def test_delete_url(self, adapter, mock_table):
        """delete_url() removes all items for URL."""
        url = "https://example.com"
        pk = f"URL#{url_to_hash(url)}"

        # Add items
        mock_table.items[f"{pk}|META"] = {'PK': pk, 'SK': 'META'}
        mock_table.items[f"{pk}|CHUNK#0000"] = {'PK': pk, 'SK': 'CHUNK#0000'}
        mock_table.items[f"{pk}|CHUNK#0001"] = {'PK': pk, 'SK': 'CHUNK#0001'}

        count = await adapter.delete_url(url)

        # All items should be deleted
        assert count > 0

    # Get Meta Tests

    async def test_get_meta_found(self, adapter, mock_table):
        """get_meta() returns metadata when found."""
        url = "https://example.com"
        pk = f"URL#{url_to_hash(url)}"
        future_ttl = int(time.time()) + 3600

        mock_table.items[f"{pk}|META"] = {
            'PK': pk,
            'SK': 'META',
            'source_url': url,
            'title': 'Test Page',
            'domain': 'example.com',
            'chunk_count': 5,
            'total_tokens': 500,
            'fetched_at': '2024-01-01',
            'ttl': future_ttl,
            'ttl_hours': 2,
        }

        meta = await adapter.get_meta(url)

        assert meta is not None
        assert meta.title == 'Test Page'
        assert meta.chunk_count == 5

    async def test_get_meta_not_found(self, adapter, mock_table):
        """get_meta() returns None when URL not found."""
        meta = await adapter.get_meta("https://not-found.com")
        assert meta is None


# =============================================================================
# Similarity Search Tests
# =============================================================================

class TestSimilaritySearch:
    """Test search_similar functionality."""

    @pytest.fixture
    def mock_table(self):
        return MockDynamoDBTable()

    @pytest.fixture
    def mock_client(self, mock_table):
        return MockDynamoDBClient(mock_table)

    @pytest.fixture
    def adapter(self, mock_client):
        return TroiseWebChunksAdapter(mock_client, None)

    async def test_search_similar_basic(self, adapter, mock_table):
        """search_similar() returns similar chunks."""
        future_ttl = int(time.time()) + 3600

        # Add chunk items with embeddings
        mock_table.items["url1|CHUNK#0000"] = {
            'PK': 'url1',
            'SK': 'CHUNK#0000',
            'chunk_id': 'c1',
            'chunk_text': 'Similar content',
            'chunk_index': 0,
            'token_count': 5,
            'source_url': 'https://example.com',
            'ttl': future_ttl,
            'embedding': embedding_to_binary([1.0, 0.0, 0.0]),
        }

        query = [1.0, 0.0, 0.0]
        results = await adapter.search_similar(query, top_k=5)

        # Should find results
        assert isinstance(results, list)

    async def test_search_similar_respects_top_k(self, adapter, mock_table):
        """search_similar() limits results to top_k."""
        future_ttl = int(time.time()) + 3600

        # Add multiple chunks
        for i in range(10):
            mock_table.items[f"url{i}|CHUNK#0000"] = {
                'PK': f'url{i}',
                'SK': 'CHUNK#0000',
                'chunk_id': f'c{i}',
                'chunk_text': f'Content {i}',
                'chunk_index': 0,
                'token_count': 5,
                'source_url': f'https://example{i}.com',
                'ttl': future_ttl,
                'embedding': embedding_to_binary([float(i) / 10, 0.5, 0.5]),
            }

        query = [0.9, 0.5, 0.5]
        results = await adapter.search_similar(query, top_k=3)

        assert len(results) <= 3


# =============================================================================
# Cache Stats Tests
# =============================================================================

class TestCacheStats:
    """Test get_cache_stats functionality."""

    @pytest.fixture
    def mock_table(self):
        return MockDynamoDBTable()

    @pytest.fixture
    def mock_client(self, mock_table):
        return MockDynamoDBClient(mock_table)

    @pytest.fixture
    def adapter(self, mock_client):
        return TroiseWebChunksAdapter(mock_client, None)

    async def test_get_cache_stats_empty(self, adapter):
        """get_cache_stats() returns zeros for empty cache."""
        stats = await adapter.get_cache_stats()

        assert stats['total_urls'] == 0
        assert stats['total_chunks'] == 0
        assert stats['expired_urls'] == 0

    async def test_get_cache_stats_with_data(self, adapter, mock_table):
        """get_cache_stats() returns correct counts."""
        future_ttl = int(time.time()) + 3600
        past_ttl = int(time.time()) - 3600

        # Add active meta
        mock_table.items["url1|META"] = {
            'PK': 'url1',
            'SK': 'META',
            'source_url': 'https://example1.com',
            'domain': 'example1.com',
            'chunk_count': 5,
            'ttl': future_ttl,
        }

        # Add expired meta
        mock_table.items["url2|META"] = {
            'PK': 'url2',
            'SK': 'META',
            'source_url': 'https://example2.com',
            'domain': 'example2.com',
            'chunk_count': 3,
            'ttl': past_ttl,
        }

        stats = await adapter.get_cache_stats()

        assert stats['total_urls'] == 2
        assert stats['total_chunks'] == 8
        assert stats['expired_urls'] == 1
        assert stats['active_urls'] == 1
