"""DynamoDB adapter for troise_web_chunks table.

Handles web page chunks with embeddings for RAG operations.
Provides cache-based storage with configurable TTL.

Table Design:
    PK patterns:
    - URL#{sha256_hash} - URL identifier

    SK patterns:
    - META - URL metadata (title, domain, chunk_count, fetched_at, ttl)
    - CHUNK#{chunk_index:04d} - Individual text chunks with embeddings
"""
import hashlib
import logging
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from boto3.dynamodb.conditions import Key

from .base import DynamoDBClient
from app.core.config import RAGConfig

logger = logging.getLogger(__name__)

TABLE_NAME = "troise_web_chunks"


def url_to_hash(url: str) -> str:
    """Convert a URL to SHA256 hash for consistent partition keys."""
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


def extract_domain(url: str) -> str:
    """Extract domain from URL for TTL lookup."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""


def embedding_to_binary(embedding: List[float]) -> bytes:
    """Convert embedding list to binary format for storage."""
    return struct.pack(f'{len(embedding)}f', *embedding)


def binary_to_embedding(data: bytes) -> List[float]:
    """Convert binary data back to embedding list."""
    count = len(data) // 4  # 4 bytes per float
    return list(struct.unpack(f'{count}f', data))


@dataclass
class WebMetaItem:
    """URL metadata item."""
    source_url: str  # Original URL
    title: str  # Page title
    domain: str  # Extracted domain
    chunk_count: int  # Number of chunks
    total_tokens: int  # Sum of all chunk tokens
    fetched_at: str  # ISO8601 timestamp
    ttl: int  # Unix timestamp for DynamoDB TTL
    ttl_hours: int  # Original TTL config (for debugging)

    @property
    def url_hash(self) -> str:
        return url_to_hash(self.source_url)

    @property
    def pk(self) -> str:
        return f"URL#{self.url_hash}"

    @property
    def sk(self) -> str:
        return "META"

    def to_dynamo_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            'PK': self.pk,
            'SK': self.sk,
            'entity_type': 'URL_META',
            'source_url': self.source_url,
            'url_hash': self.url_hash,
            'title': self.title,
            'domain': self.domain,
            'chunk_count': self.chunk_count,
            'total_tokens': self.total_tokens,
            'fetched_at': self.fetched_at,
            'ttl': self.ttl,
            'ttl_hours': self.ttl_hours,
        }

    @classmethod
    def from_dynamo_item(cls, item: Dict[str, Any]) -> "WebMetaItem":
        """Create from DynamoDB item."""
        return cls(
            source_url=item['source_url'],
            title=item.get('title', ''),
            domain=item.get('domain', ''),
            chunk_count=item.get('chunk_count', 0),
            total_tokens=item.get('total_tokens', 0),
            fetched_at=item.get('fetched_at', ''),
            ttl=item.get('ttl', 0),
            ttl_hours=item.get('ttl_hours', 0),
        )


@dataclass
class WebChunkItem:
    """Individual chunk of a web page with embedding."""
    chunk_id: str  # UUID
    chunk_text: str  # The actual text content
    chunk_index: int  # Position in document (0-based)
    token_count: int  # Tokens in this chunk
    source_url: str  # Original URL
    start_char: int  # Start position in original text
    end_char: int  # End position in original text
    ttl: int  # Unix timestamp for TTL
    embedding: Optional[List[float]] = None  # Vector embedding

    @property
    def url_hash(self) -> str:
        return url_to_hash(self.source_url)

    @property
    def pk(self) -> str:
        return f"URL#{self.url_hash}"

    @property
    def sk(self) -> str:
        return f"CHUNK#{self.chunk_index:04d}"

    def to_dynamo_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            'PK': self.pk,
            'SK': self.sk,
            'entity_type': 'URL_CHUNK',
            'chunk_id': self.chunk_id,
            'chunk_text': self.chunk_text,
            'chunk_index': self.chunk_index,
            'token_count': self.token_count,
            'source_url': self.source_url,
            'url_hash': self.url_hash,
            'start_char': self.start_char,
            'end_char': self.end_char,
            'ttl': self.ttl,
        }
        if self.embedding:
            item['embedding'] = embedding_to_binary(self.embedding)
        return item

    @classmethod
    def from_dynamo_item(cls, item: Dict[str, Any]) -> "WebChunkItem":
        """Create from DynamoDB item."""
        embedding = None
        if 'embedding' in item and item['embedding']:
            embedding_data = item['embedding']
            if isinstance(embedding_data, bytes):
                embedding = binary_to_embedding(embedding_data)
            elif hasattr(embedding_data, 'value'):
                # boto3 Binary type
                embedding = binary_to_embedding(embedding_data.value)

        return cls(
            chunk_id=item.get('chunk_id', ''),
            chunk_text=item.get('chunk_text', ''),
            chunk_index=item.get('chunk_index', 0),
            token_count=item.get('token_count', 0),
            source_url=item.get('source_url', ''),
            start_char=item.get('start_char', 0),
            end_char=item.get('end_char', 0),
            ttl=item.get('ttl', 0),
            embedding=embedding,
        )


class TroiseWebChunksAdapter:
    """
    Adapter for the troise_web_chunks DynamoDB table.

    Provides methods for storing and retrieving web page chunks
    with embeddings for RAG operations.

    Supports:
    - Domain-specific TTL configuration
    - Per-call TTL override
    - Efficient cache lookup
    - Similarity search (client-side)

    Example:
        client = DynamoDBClient()
        adapter = TroiseWebChunksAdapter(client, config)

        # Store chunks
        await adapter.store_chunks(
            url="https://docs.python.org/3/tutorial/",
            title="Python Tutorial",
            chunks=[{"chunk_id": "...", "chunk_text": "...", ...}],
            embeddings=[[0.1, 0.2, ...], ...],
        )

        # Check cache
        if await adapter.is_cached(url):
            chunks = await adapter.get_chunks_by_url(url)

        # Delete URL
        await adapter.delete_url(url)
    """

    def __init__(
        self,
        client: DynamoDBClient,
        config: Optional[RAGConfig] = None,
    ):
        """
        Initialize the adapter.

        Args:
            client: DynamoDBClient instance.
            config: RAGConfig for TTL settings.
        """
        self._client = client
        self._table_name = TABLE_NAME
        self._config = config

    def _get_ttl_for_url(self, url: str, ttl_hours_override: Optional[int] = None) -> int:
        """
        Resolve TTL for a URL.

        Priority:
        1. Per-call override
        2. Domain-specific config
        3. Default fallback

        Args:
            url: URL to get TTL for.
            ttl_hours_override: Per-call TTL override.

        Returns:
            TTL in hours.
        """
        # 1. Per-call override
        if ttl_hours_override is not None:
            return ttl_hours_override

        # 2. Domain-specific config
        if self._config and self._config.ttl_by_domain:
            domain = extract_domain(url)
            if domain in self._config.ttl_by_domain:
                return self._config.ttl_by_domain[domain]

        # 3. Default fallback
        if self._config:
            return self._config.web_cache_ttl_hours
        return 2  # Default 2 hours

    def _calculate_ttl_timestamp(self, ttl_hours: int) -> int:
        """Convert TTL hours to Unix timestamp."""
        return int(time.time()) + (ttl_hours * 3600)

    # ========== Store Operations ==========

    async def store_chunks(
        self,
        url: str,
        title: str,
        chunks: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None,
        ttl_hours: Optional[int] = None,
    ) -> int:
        """
        Store web page chunks with embeddings and TTL.

        Args:
            url: Source URL.
            title: Page title.
            chunks: List of chunk dicts with keys:
                    chunk_id, chunk_text, chunk_index, token_count, start_char, end_char
            embeddings: Pre-computed embeddings for each chunk (optional).
            ttl_hours: Override TTL in hours (uses domain/default if None).

        Returns:
            Number of chunks stored.

        Raises:
            ValueError: If url or chunks are invalid.
        """
        if not url:
            raise ValueError("URL is required")

        if not chunks:
            raise ValueError("Chunks list cannot be empty")

        # Verify embedding count matches if provided
        if embeddings and len(embeddings) != len(chunks):
            logger.warning(
                f"Embedding count mismatch for {url}: "
                f"{len(embeddings)} embeddings for {len(chunks)} chunks"
            )

        # Resolve TTL
        resolved_ttl_hours = self._get_ttl_for_url(url, ttl_hours)
        ttl_timestamp = self._calculate_ttl_timestamp(resolved_ttl_hours)

        # Extract domain
        domain = extract_domain(url)

        # Calculate total tokens
        total_tokens = sum(c.get('token_count', 0) for c in chunks)

        # Create metadata
        now = datetime.now().isoformat()
        meta = WebMetaItem(
            source_url=url,
            title=title,
            domain=domain,
            chunk_count=len(chunks),
            total_tokens=total_tokens,
            fetched_at=now,
            ttl=ttl_timestamp,
            ttl_hours=resolved_ttl_hours,
        )

        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            # Delete existing chunks first (refresh cache)
            await self._delete_url_items(table, url)

            # Store metadata
            await table.put_item(Item=meta.to_dynamo_item())

            # Store chunks
            for i, chunk_dict in enumerate(chunks):
                embedding = None
                if embeddings and i < len(embeddings):
                    embedding = embeddings[i]

                chunk = WebChunkItem(
                    chunk_id=chunk_dict['chunk_id'],
                    chunk_text=chunk_dict['chunk_text'],
                    chunk_index=chunk_dict.get('chunk_index', i),
                    token_count=chunk_dict.get('token_count', 0),
                    source_url=url,
                    start_char=chunk_dict.get('start_char', 0),
                    end_char=chunk_dict.get('end_char', 0),
                    ttl=ttl_timestamp,
                    embedding=embedding,
                )
                await table.put_item(Item=chunk.to_dynamo_item())

        logger.info(
            f"Stored {len(chunks)} chunks for {url} "
            f"(domain={domain}, ttl={resolved_ttl_hours}h)"
        )
        return len(chunks)

    async def _delete_url_items(self, table, url: str) -> int:
        """Delete all items for a URL (internal helper)."""
        pk = f"URL#{url_to_hash(url)}"

        response = await table.query(
            KeyConditionExpression=Key('PK').eq(pk),
        )

        count = 0
        for item in response.get('Items', []):
            await table.delete_item(
                Key={'PK': item['PK'], 'SK': item['SK']}
            )
            count += 1

        return count

    # ========== Retrieval Operations ==========

    async def get_meta(self, url: str) -> Optional[WebMetaItem]:
        """
        Get metadata for a URL.

        Args:
            url: Source URL.

        Returns:
            WebMetaItem or None if not found/expired.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            response = await table.get_item(
                Key={
                    'PK': f"URL#{url_to_hash(url)}",
                    'SK': "META",
                }
            )

            item = response.get('Item')
            if item:
                meta = WebMetaItem.from_dynamo_item(item)
                # Check if expired
                if meta.ttl < int(time.time()):
                    logger.debug(f"Cache expired for {url}")
                    return None
                return meta
            return None

    async def is_cached(self, url: str) -> bool:
        """
        Quick check if URL is in cache and not expired.

        Args:
            url: URL to check.

        Returns:
            True if cached and valid.
        """
        meta = await self.get_meta(url)
        return meta is not None

    async def get_chunks_by_url(
        self,
        url: str,
        include_embeddings: bool = True,
    ) -> Optional[List[WebChunkItem]]:
        """
        Retrieve all chunks for a URL.

        Args:
            url: Source URL.
            include_embeddings: If False, skip loading embeddings.

        Returns:
            List of WebChunkItem objects if found and not expired, None otherwise.
        """
        # First check if valid cache exists
        meta = await self.get_meta(url)
        if not meta:
            return None

        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            pk = f"URL#{url_to_hash(url)}"

            # Build query params
            params = {
                'KeyConditionExpression': Key('PK').eq(pk) &
                                          Key('SK').begins_with("CHUNK#"),
                'ScanIndexForward': True,  # Ascending order
            }

            if not include_embeddings:
                params['ProjectionExpression'] = (
                    "PK, SK, chunk_id, chunk_text, chunk_index, token_count, "
                    "source_url, start_char, end_char, #ttl"
                )
                params['ExpressionAttributeNames'] = {'#ttl': 'ttl'}

            response = await table.query(**params)

            chunks = [
                WebChunkItem.from_dynamo_item(item)
                for item in response.get('Items', [])
            ]

            logger.debug(f"Retrieved {len(chunks)} chunks for {url}")
            return chunks

    async def delete_url(self, url: str) -> int:
        """
        Force delete URL and all its chunks.

        Args:
            url: URL to delete.

        Returns:
            Number of items deleted.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)
            count = await self._delete_url_items(table, url)

        logger.info(f"Deleted {count} items for {url}")
        return count

    # ========== Search Operations ==========

    async def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[WebChunkItem]:
        """
        Search for most similar chunks using cosine similarity.

        Note: This performs a full scan - use sparingly.
        For production scale, consider Pinecone/Weaviate/pgvector.

        Args:
            query_embedding: Query vector to compare against.
            top_k: Number of top results to return.

        Returns:
            List of WebChunkItem objects sorted by similarity (highest first).
        """
        import math

        def cosine_similarity(a: List[float], b: List[float]) -> float:
            """Calculate cosine similarity between two vectors."""
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        current_time = int(time.time())
        results = []

        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            # Scan for all CHUNK items
            response = await table.scan(
                FilterExpression="begins_with(#sk, :chunk_prefix) AND #ttl > :now",
                ExpressionAttributeNames={
                    "#sk": "SK",
                    "#ttl": "ttl",
                },
                ExpressionAttributeValues={
                    ":chunk_prefix": "CHUNK#",
                    ":now": current_time,
                },
            )

            for item in response.get('Items', []):
                chunk = WebChunkItem.from_dynamo_item(item)
                if chunk.embedding:
                    score = cosine_similarity(query_embedding, chunk.embedding)
                    results.append((score, chunk))

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = await table.scan(
                    FilterExpression="begins_with(#sk, :chunk_prefix) AND #ttl > :now",
                    ExpressionAttributeNames={
                        "#sk": "SK",
                        "#ttl": "ttl",
                    },
                    ExpressionAttributeValues={
                        ":chunk_prefix": "CHUNK#",
                        ":now": current_time,
                    },
                    ExclusiveStartKey=response['LastEvaluatedKey'],
                )
                for item in response.get('Items', []):
                    chunk = WebChunkItem.from_dynamo_item(item)
                    if chunk.embedding:
                        score = cosine_similarity(query_embedding, chunk.embedding)
                        results.append((score, chunk))

        # Sort by similarity and return top_k
        results.sort(key=lambda x: x[0], reverse=True)
        return [chunk for score, chunk in results[:top_k]]

    # ========== Utility ==========

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the web cache.

        Returns:
            Dict with cache statistics.
        """
        current_time = int(time.time())
        urls_count = 0
        chunks_count = 0
        expired_count = 0
        domains = {}

        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            # Scan for all META items
            response = await table.scan(
                FilterExpression="#sk = :meta",
                ExpressionAttributeNames={"#sk": "SK"},
                ExpressionAttributeValues={":meta": "META"},
            )

            for item in response.get('Items', []):
                meta = WebMetaItem.from_dynamo_item(item)
                urls_count += 1
                chunks_count += meta.chunk_count

                if meta.ttl < current_time:
                    expired_count += 1

                domain = meta.domain or "(unknown)"
                domains[domain] = domains.get(domain, 0) + 1

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = await table.scan(
                    FilterExpression="#sk = :meta",
                    ExpressionAttributeNames={"#sk": "SK"},
                    ExpressionAttributeValues={":meta": "META"},
                    ExclusiveStartKey=response['LastEvaluatedKey'],
                )
                for item in response.get('Items', []):
                    meta = WebMetaItem.from_dynamo_item(item)
                    urls_count += 1
                    chunks_count += meta.chunk_count

                    if meta.ttl < current_time:
                        expired_count += 1

                    domain = meta.domain or "(unknown)"
                    domains[domain] = domains.get(domain, 0) + 1

        return {
            "total_urls": urls_count,
            "total_chunks": chunks_count,
            "expired_urls": expired_count,
            "active_urls": urls_count - expired_count,
            "domains": domains,
        }
