"""
Embedding Service for TROISE AI.

Provides text embedding generation using Ollama's embedding API.
Integrates with the TroiseVectorsAdapter for caching.

Features:
- Async embedding generation via Ollama
- Automatic caching with 30-day TTL
- Batch embedding support
- Configurable model selection
- Implements IEmbeddingService interface

Default Model: nomic-embed-text (768 dimensions)
"""

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from app.core.interfaces import IEmbeddingService
from app.adapters.dynamodb import DynamoDBClient, TroiseVectorsAdapter

logger = logging.getLogger(__name__)

# Default embedding model
DEFAULT_MODEL = "nomic-embed-text"
DEFAULT_DIMENSIONS = 768

# Ollama embedding endpoint
OLLAMA_EMBED_ENDPOINT = "/api/embed"


class EmbeddingServiceError(Exception):
    """Raised when embedding generation fails."""
    pass


class EmbeddingService:
    """
    Service for generating and caching text embeddings.

    Uses Ollama's embedding API with caching via DynamoDB.
    Implements the IEmbeddingService protocol.

    Example:
        service = EmbeddingService(
            ollama_host="http://localhost:11434",
            dynamo_client=DynamoDBClient()
        )

        # Single embedding
        embedding = await service.embed("Hello world")

        # Batch embedding
        embeddings = await service.embed_batch([
            "Hello world",
            "Goodbye world"
        ])
    """

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        dynamo_client: Optional[DynamoDBClient] = None,
        model: str = DEFAULT_MODEL,
        use_cache: bool = True,
    ):
        """
        Initialize the embedding service.

        Args:
            ollama_host: Ollama server URL.
            dynamo_client: DynamoDB client for caching (optional).
            model: Embedding model to use.
            use_cache: Whether to use the embedding cache.
        """
        self._ollama_host = ollama_host.rstrip('/')
        self._model = model
        self._use_cache = use_cache and dynamo_client is not None

        # Initialize cache adapter if enabled
        self._cache: Optional[TroiseVectorsAdapter] = None
        if use_cache and dynamo_client:
            self._cache = TroiseVectorsAdapter(dynamo_client, default_model=model)
            logger.info(f"Embedding cache enabled for model {model}")
        else:
            logger.info(f"Embedding cache disabled")

        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60)
            )
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _call_ollama_embed(
        self,
        texts: List[str],
    ) -> List[List[float]]:
        """
        Call Ollama's embedding API.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.

        Raises:
            EmbeddingServiceError: If the API call fails.
        """
        session = await self._get_session()
        url = f"{self._ollama_host}{OLLAMA_EMBED_ENDPOINT}"

        try:
            async with session.post(
                url,
                json={
                    "model": self._model,
                    "input": texts,
                }
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise EmbeddingServiceError(
                        f"Ollama embedding failed ({response.status}): {error_text}"
                    )

                data = await response.json()

                # Ollama returns embeddings in 'embeddings' key
                embeddings = data.get('embeddings', [])

                if len(embeddings) != len(texts):
                    raise EmbeddingServiceError(
                        f"Expected {len(texts)} embeddings, got {len(embeddings)}"
                    )

                return embeddings

        except aiohttp.ClientError as e:
            raise EmbeddingServiceError(f"Failed to connect to Ollama: {e}")

    async def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector (list of floats).

        Raises:
            EmbeddingServiceError: If embedding generation fails.
        """
        if not text.strip():
            raise EmbeddingServiceError("Cannot embed empty text")

        # Check cache first
        if self._cache:
            cached = await self._cache.get_cached_embedding(text, self._model)
            if cached is not None:
                logger.debug(f"Cache hit for embedding ({len(text)} chars)")
                return cached

        # Generate embedding
        embeddings = await self._call_ollama_embed([text])
        embedding = embeddings[0]

        # Cache it
        if self._cache:
            await self._cache.cache_embedding(text, embedding, self._model)
            logger.debug(f"Cached embedding for text ({len(text)} chars)")

        return embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Uses caching to avoid regenerating embeddings for previously seen texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.

        Raises:
            EmbeddingServiceError: If embedding generation fails.
        """
        if not texts:
            return []

        # Filter out empty texts
        valid_texts = [(i, t) for i, t in enumerate(texts) if t.strip()]
        if not valid_texts:
            raise EmbeddingServiceError("All texts are empty")

        # Initialize result array
        results = [None] * len(texts)

        # Check cache for all texts
        texts_to_embed = []
        text_indices = []

        if self._cache:
            for orig_idx, text in valid_texts:
                cached = await self._cache.get_cached_embedding(text, self._model)
                if cached is not None:
                    results[orig_idx] = cached
                else:
                    texts_to_embed.append(text)
                    text_indices.append(orig_idx)

            logger.debug(
                f"Batch embed: {len(valid_texts) - len(texts_to_embed)} cache hits, "
                f"{len(texts_to_embed)} to generate"
            )
        else:
            texts_to_embed = [t for _, t in valid_texts]
            text_indices = [i for i, _ in valid_texts]

        # Generate embeddings for uncached texts
        if texts_to_embed:
            embeddings = await self._call_ollama_embed(texts_to_embed)

            for i, embedding in enumerate(embeddings):
                orig_idx = text_indices[i]
                results[orig_idx] = embedding

                # Cache the embedding
                if self._cache:
                    await self._cache.cache_embedding(
                        texts_to_embed[i],
                        embedding,
                        self._model
                    )

        # Fill in empty texts with zero vectors
        for i, text in enumerate(texts):
            if not text.strip():
                results[i] = [0.0] * DEFAULT_DIMENSIONS

        return results

    async def is_model_available(self) -> bool:
        """
        Check if the embedding model is available in Ollama.

        Returns:
            True if the model is available.
        """
        session = await self._get_session()
        url = f"{self._ollama_host}/api/show"

        try:
            async with session.post(
                url,
                json={"model": self._model}
            ) as response:
                return response.status == 200
        except aiohttp.ClientError:
            return False

    async def get_model_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the embedding model.

        Returns:
            Model info dict or None if not available.
        """
        session = await self._get_session()
        url = f"{self._ollama_host}/api/show"

        try:
            async with session.post(
                url,
                json={"model": self._model}
            ) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except aiohttp.ClientError:
            return None

    @property
    def model(self) -> str:
        """Get the current embedding model name."""
        return self._model

    @property
    def dimensions(self) -> int:
        """Get the expected embedding dimensions."""
        return DEFAULT_DIMENSIONS

    async def similarity(
        self,
        embedding1: List[float],
        embedding2: List[float],
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector.
            embedding2: Second embedding vector.

        Returns:
            Cosine similarity score (0.0 to 1.0).
        """
        import math

        if len(embedding1) != len(embedding2):
            raise ValueError("Embeddings must have same dimensions")

        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        norm1 = math.sqrt(sum(a * a for a in embedding1))
        norm2 = math.sqrt(sum(b * b for b in embedding2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    async def find_most_similar(
        self,
        query_embedding: List[float],
        candidate_embeddings: List[List[float]],
        top_k: int = 5,
    ) -> List[tuple[int, float]]:
        """
        Find most similar embeddings to a query.

        Args:
            query_embedding: The query embedding.
            candidate_embeddings: List of candidate embeddings.
            top_k: Number of top results to return.

        Returns:
            List of (index, similarity_score) tuples, sorted by similarity.
        """
        scores = []
        for i, candidate in enumerate(candidate_embeddings):
            score = await self.similarity(query_embedding, candidate)
            scores.append((i, score))

        # Sort by similarity (descending)
        scores.sort(key=lambda x: x[1], reverse=True)

        return scores[:top_k]

    async def get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get cache statistics.

        Returns:
            Cache stats dict or None if caching is disabled.
        """
        if not self._cache:
            return None
        return await self._cache.get_cache_stats()

    async def invalidate_cache(self) -> int:
        """
        Invalidate all cached embeddings for the current model.

        Returns:
            Number of items invalidated.
        """
        if not self._cache:
            return 0
        return await self._cache.invalidate_model(self._model)

    def __repr__(self) -> str:
        cache_status = "enabled" if self._cache else "disabled"
        return f"EmbeddingService(model={self._model}, cache={cache_status})"


# Factory function for DI container
def create_embedding_service(
    ollama_host: str = "http://localhost:11434",
    dynamo_client: Optional[DynamoDBClient] = None,
    model: str = DEFAULT_MODEL,
    use_cache: bool = True,
) -> EmbeddingService:
    """
    Create an EmbeddingService instance.

    This is the factory function for the DI container.

    Args:
        ollama_host: Ollama server URL.
        dynamo_client: DynamoDB client for caching.
        model: Embedding model to use.
        use_cache: Whether to use the embedding cache.

    Returns:
        Configured EmbeddingService instance.
    """
    return EmbeddingService(
        ollama_host=ollama_host,
        dynamo_client=dynamo_client,
        model=model,
        use_cache=use_cache,
    )
