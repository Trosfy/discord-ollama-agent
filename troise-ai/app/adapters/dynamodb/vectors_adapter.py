"""DynamoDB adapter for troise_vectors table.

Caches text embeddings to avoid redundant API calls.
Embeddings are keyed by text hash and model name.

Table Design:
    PK: TEXT#{text_hash} - SHA256 hash of the text being embedded
    SK: MODEL#{model_name} - Embedding model identifier

    TTL: 30-day cache expiry to handle model updates
"""
import hashlib
import logging
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .base import DynamoDBClient

logger = logging.getLogger(__name__)

TABLE_NAME = "troise_vectors"

# TTL duration for cached embeddings (30 days)
TTL_CACHE_SECONDS = 86400 * 30


def text_to_hash(text: str) -> str:
    """Generate SHA256 hash of text for cache key."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def embedding_to_binary(embedding: List[float]) -> bytes:
    """Convert embedding list to compact binary format."""
    return struct.pack(f'{len(embedding)}f', *embedding)


def binary_to_embedding(data: bytes) -> List[float]:
    """Convert binary data back to embedding list."""
    count = len(data) // 4  # 4 bytes per float
    return list(struct.unpack(f'{count}f', data))


@dataclass
class EmbeddingCacheItem:
    """Cached embedding item."""
    text_hash: str
    model: str
    dimensions: int
    embedding: List[float]
    text_preview: str  # First 100 chars for debugging
    created_at: str  # ISO8601
    ttl: int  # Unix timestamp for expiry

    @property
    def pk(self) -> str:
        return f"TEXT#{self.text_hash}"

    @property
    def sk(self) -> str:
        return f"MODEL#{self.model}"

    def to_dynamo_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            'PK': self.pk,
            'SK': self.sk,
            'text_hash': self.text_hash,
            'model': self.model,
            'dimensions': self.dimensions,
            'embedding': embedding_to_binary(self.embedding),
            'text_preview': self.text_preview,
            'created_at': self.created_at,
            'ttl': self.ttl,
        }

    @classmethod
    def from_dynamo_item(cls, item: Dict[str, Any]) -> "EmbeddingCacheItem":
        """Create from DynamoDB item."""
        embedding_data = item.get('embedding', b'')
        if isinstance(embedding_data, bytes):
            embedding = binary_to_embedding(embedding_data)
        elif hasattr(embedding_data, 'value'):
            # boto3 Binary type
            embedding = binary_to_embedding(embedding_data.value)
        else:
            embedding = []

        return cls(
            text_hash=item.get('text_hash', ''),
            model=item.get('model', ''),
            dimensions=item.get('dimensions', 0),
            embedding=embedding,
            text_preview=item.get('text_preview', ''),
            created_at=item.get('created_at', ''),
            ttl=item.get('ttl', 0),
        )


class TroiseVectorsAdapter:
    """
    Adapter for the troise_vectors DynamoDB table.

    Provides embedding caching to avoid redundant calls to embedding APIs.
    Embeddings are cached by (text_hash, model) with 30-day TTL.

    Example:
        client = DynamoDBClient()
        adapter = TroiseVectorsAdapter(client)

        # Check cache first
        cached = await adapter.get_cached_embedding(
            text="Hello world",
            model="nomic-embed-text"
        )

        if cached is None:
            # Generate embedding and cache it
            embedding = await some_embedding_api(text)
            await adapter.cache_embedding(
                text="Hello world",
                model="nomic-embed-text",
                embedding=embedding
            )
    """

    def __init__(
        self,
        client: DynamoDBClient,
        default_model: str = "nomic-embed-text",
    ):
        """
        Initialize the adapter.

        Args:
            client: DynamoDBClient instance.
            default_model: Default embedding model name.
        """
        self._client = client
        self._table_name = TABLE_NAME
        self._default_model = default_model

    async def get_cached_embedding(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> Optional[List[float]]:
        """
        Get a cached embedding if available.

        Args:
            text: The text that was embedded.
            model: Embedding model name (uses default if not specified).

        Returns:
            Embedding vector or None if not cached/expired.
        """
        model = model or self._default_model
        text_hash = text_to_hash(text)

        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            response = await table.get_item(
                Key={
                    'PK': f"TEXT#{text_hash}",
                    'SK': f"MODEL#{model}",
                }
            )

            item = response.get('Item')
            if not item:
                return None

            # Check if expired (TTL might not be immediately enforced)
            ttl = item.get('ttl', 0)
            if ttl and int(time.time()) > ttl:
                logger.debug(f"Cache hit but expired for {text[:50]}...")
                return None

            cache_item = EmbeddingCacheItem.from_dynamo_item(item)
            logger.debug(f"Cache hit for {text[:50]}... ({len(cache_item.embedding)} dims)")
            return cache_item.embedding

    async def cache_embedding(
        self,
        text: str,
        embedding: List[float],
        model: Optional[str] = None,
        ttl_seconds: int = TTL_CACHE_SECONDS,
    ) -> EmbeddingCacheItem:
        """
        Cache an embedding.

        Args:
            text: The text that was embedded.
            embedding: The embedding vector.
            model: Embedding model name (uses default if not specified).
            ttl_seconds: Time-to-live in seconds.

        Returns:
            Created EmbeddingCacheItem.
        """
        model = model or self._default_model
        text_hash = text_to_hash(text)

        cache_item = EmbeddingCacheItem(
            text_hash=text_hash,
            model=model,
            dimensions=len(embedding),
            embedding=embedding,
            text_preview=text[:100],
            created_at=datetime.now().isoformat(),
            ttl=int(time.time()) + ttl_seconds,
        )

        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)
            await table.put_item(Item=cache_item.to_dynamo_item())

        logger.debug(f"Cached embedding for {text[:50]}... ({len(embedding)} dims)")
        return cache_item

    async def get_or_compute(
        self,
        text: str,
        compute_fn,
        model: Optional[str] = None,
    ) -> List[float]:
        """
        Get cached embedding or compute and cache it.

        This is the primary interface for caching embeddings.
        If the embedding is not in cache, it will call compute_fn
        to generate it and then cache the result.

        Args:
            text: The text to embed.
            compute_fn: Async function that takes text and returns embedding.
            model: Embedding model name (uses default if not specified).

        Returns:
            Embedding vector.

        Example:
            async def embed(text: str) -> List[float]:
                return await ollama.embed(text, model="nomic-embed-text")

            embedding = await adapter.get_or_compute(
                text="Hello world",
                compute_fn=embed
            )
        """
        # Try cache first
        cached = await self.get_cached_embedding(text, model)
        if cached is not None:
            return cached

        # Compute embedding
        embedding = await compute_fn(text)

        # Cache it
        await self.cache_embedding(text, embedding, model)

        return embedding

    async def get_batch_cached(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> Tuple[List[Optional[List[float]]], List[int]]:
        """
        Get cached embeddings for multiple texts.

        Args:
            texts: List of texts to look up.
            model: Embedding model name.

        Returns:
            Tuple of (embeddings list, indices of uncached texts).
            Embeddings list has None for uncached texts.
        """
        model = model or self._default_model
        embeddings = [None] * len(texts)
        uncached_indices = []

        for i, text in enumerate(texts):
            cached = await self.get_cached_embedding(text, model)
            if cached is not None:
                embeddings[i] = cached
            else:
                uncached_indices.append(i)

        return embeddings, uncached_indices

    async def cache_batch(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        model: Optional[str] = None,
    ) -> int:
        """
        Cache multiple embeddings at once.

        Args:
            texts: List of texts.
            embeddings: List of corresponding embeddings.
            model: Embedding model name.

        Returns:
            Number of items cached.
        """
        if len(texts) != len(embeddings):
            raise ValueError("texts and embeddings must have same length")

        model = model or self._default_model
        count = 0

        for text, embedding in zip(texts, embeddings):
            await self.cache_embedding(text, embedding, model)
            count += 1

        logger.info(f"Cached batch of {count} embeddings for model {model}")
        return count

    async def invalidate(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> bool:
        """
        Invalidate (delete) a cached embedding.

        Args:
            text: The text whose embedding should be invalidated.
            model: Embedding model name (uses default if not specified).

        Returns:
            True if deleted, False if not found.
        """
        model = model or self._default_model
        text_hash = text_to_hash(text)

        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            try:
                await table.delete_item(
                    Key={
                        'PK': f"TEXT#{text_hash}",
                        'SK': f"MODEL#{model}",
                    },
                    ConditionExpression="attribute_exists(PK)",
                )
                logger.debug(f"Invalidated cache for {text[:50]}...")
                return True
            except Exception as e:
                if 'ConditionalCheckFailedException' in str(type(e).__name__):
                    return False
                raise

    async def invalidate_model(self, model: str) -> int:
        """
        Invalidate all cached embeddings for a specific model.

        Use this when a model is updated and embeddings need to be regenerated.

        Args:
            model: Embedding model name.

        Returns:
            Number of items deleted.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            # Scan for all items with this model
            response = await table.scan(
                FilterExpression="#sk = :model",
                ExpressionAttributeNames={"#sk": "SK"},
                ExpressionAttributeValues={":model": f"MODEL#{model}"},
            )

            count = 0
            for item in response.get('Items', []):
                await table.delete_item(
                    Key={'PK': item['PK'], 'SK': item['SK']}
                )
                count += 1

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = await table.scan(
                    FilterExpression="#sk = :model",
                    ExpressionAttributeNames={"#sk": "SK"},
                    ExpressionAttributeValues={":model": f"MODEL#{model}"},
                    ExclusiveStartKey=response['LastEvaluatedKey'],
                )
                for item in response.get('Items', []):
                    await table.delete_item(
                        Key={'PK': item['PK'], 'SK': item['SK']}
                    )
                    count += 1

            logger.info(f"Invalidated {count} cached embeddings for model {model}")
            return count

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache statistics.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            # Scan for all items
            response = await table.scan(
                ProjectionExpression="#pk, #sk, dimensions, created_at, #ttl",
                ExpressionAttributeNames={
                    "#pk": "PK",
                    "#sk": "SK",
                    "#ttl": "ttl",
                },
            )

            items = response.get('Items', [])

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = await table.scan(
                    ProjectionExpression="#pk, #sk, dimensions, created_at, #ttl",
                    ExpressionAttributeNames={
                        "#pk": "PK",
                        "#sk": "SK",
                        "#ttl": "ttl",
                    },
                    ExclusiveStartKey=response['LastEvaluatedKey'],
                )
                items.extend(response.get('Items', []))

            # Count by model
            models = {}
            expired_count = 0
            current_time = int(time.time())

            for item in items:
                sk = item.get('SK', '')
                model = sk.replace('MODEL#', '') if sk.startswith('MODEL#') else 'unknown'
                models[model] = models.get(model, 0) + 1

                ttl = item.get('ttl', 0)
                if ttl and current_time > ttl:
                    expired_count += 1

            return {
                "total_cached": len(items),
                "expired_count": expired_count,
                "models": models,
                "unique_texts": len(set(item.get('PK') for item in items)),
            }

    async def cleanup_expired(self) -> int:
        """
        Manually clean up expired cache entries.

        Note: DynamoDB TTL eventually deletes expired items automatically,
        but this can be used for immediate cleanup.

        Returns:
            Number of items deleted.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            current_time = int(time.time())

            # Scan for expired items
            response = await table.scan(
                FilterExpression="#ttl < :now",
                ExpressionAttributeNames={"#ttl": "ttl"},
                ExpressionAttributeValues={":now": current_time},
                ProjectionExpression="PK, SK",
            )

            count = 0
            for item in response.get('Items', []):
                await table.delete_item(
                    Key={'PK': item['PK'], 'SK': item['SK']}
                )
                count += 1

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = await table.scan(
                    FilterExpression="#ttl < :now",
                    ExpressionAttributeNames={"#ttl": "ttl"},
                    ExpressionAttributeValues={":now": current_time},
                    ProjectionExpression="PK, SK",
                    ExclusiveStartKey=response['LastEvaluatedKey'],
                )
                for item in response.get('Items', []):
                    await table.delete_item(
                        Key={'PK': item['PK'], 'SK': item['SK']}
                    )
                    count += 1

            if count > 0:
                logger.info(f"Cleaned up {count} expired cache entries")

            return count
