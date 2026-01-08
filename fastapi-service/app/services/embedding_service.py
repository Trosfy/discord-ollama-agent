"""Embedding service using Ollama API."""
from typing import List
import httpx

from app.interfaces.embedding import EmbeddingVector, IEmbeddingService
from app.config import settings
import logging_client

logger = logging_client.setup_logger('embedding_service')


class OllamaEmbeddingService:
    """Embedding service using Ollama's /api/embeddings endpoint.

    Implements IEmbeddingService following Single Responsibility Principle.
    Supports both single and batch embedding generation.
    """

    def __init__(
        self,
        model: str = None,
        base_url: str = None,
        timeout: int = 60
    ):
        """Initialize Ollama embedding service.

        Args:
            model: Embedding model name (defaults to settings.EMBEDDING_MODEL)
            base_url: Ollama API base URL (defaults to settings.OLLAMA_HOST)
            timeout: Request timeout in seconds
        """
        self.model = model or settings.EMBEDDING_MODEL
        self.base_url = (base_url or settings.OLLAMA_HOST).rstrip('/')
        self.timeout = timeout
        self.embedding_dimension = settings.EMBEDDING_DIMENSION

        logger.info(
            f"✅ OllamaEmbeddingService initialized "
            f"(model={self.model}, base_url={self.base_url})"
        )

    async def embed_text(self, text: str) -> EmbeddingVector:
        """Generate embedding vector for a single text using Ollama.

        Args:
            text: The text to embed

        Returns:
            EmbeddingVector with the generated embedding

        Raises:
            ValueError: If text is empty
            RuntimeError: If embedding generation fails
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={
                        "model": self.model,
                        "prompt": text
                    }
                )
                response.raise_for_status()

                data = response.json()
                embedding = data.get("embedding")

                if not embedding:
                    raise RuntimeError(
                        f"No embedding returned from Ollama API. Response: {data}"
                    )

                logger.debug(
                    f"✅ Generated embedding for text "
                    f"(length={len(text)}, dimension={len(embedding)})"
                )

                return EmbeddingVector(
                    text=text,
                    vector=embedding,
                    model=self.model,
                    dimension=len(embedding)
                )

        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP error generating embedding: {e}")
            raise RuntimeError(f"Failed to generate embedding: {e}") from e
        except Exception as e:
            logger.error(f"❌ Unexpected error generating embedding: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}") from e

    async def embed_batch(self, texts: List[str]) -> List[EmbeddingVector]:
        """Generate embedding vectors for multiple texts (sequential processing).

        Note: Ollama's /api/embeddings endpoint processes one text at a time.
        For production, consider using a batching API if available.

        Args:
            texts: List of texts to embed

        Returns:
            List of EmbeddingVector objects in the same order as input

        Raises:
            ValueError: If texts list is empty
            RuntimeError: If embedding generation fails
        """
        if not texts:
            raise ValueError("Texts list cannot be empty")

        logger.info(f"📊 Batch embedding {len(texts)} texts...")

        embeddings = []
        for idx, text in enumerate(texts):
            try:
                embedding = await self.embed_text(text)
                embeddings.append(embedding)

                if (idx + 1) % 10 == 0:  # Log progress every 10 embeddings
                    logger.debug(f"Progress: {idx + 1}/{len(texts)} embeddings generated")

            except Exception as e:
                logger.error(f"❌ Failed to embed text {idx}: {e}")
                # Continue with remaining texts, but log the error
                # Could also choose to fail fast here
                raise

        logger.info(
            f"✅ Batch embedding complete: {len(embeddings)}/{len(texts)} successful"
        )

        return embeddings
