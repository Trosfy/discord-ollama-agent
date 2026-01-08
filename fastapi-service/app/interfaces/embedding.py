"""Interface for embedding services."""
from typing import List, Protocol
from pydantic import BaseModel


class EmbeddingVector(BaseModel):
    """Represents an embedding vector with metadata."""
    text: str  # Original text that was embedded
    vector: List[float]  # Embedding vector
    model: str  # Model used for embedding
    dimension: int  # Dimension of the vector


class IEmbeddingService(Protocol):
    """Interface for text embedding services.

    Follows Interface Segregation Principle - focused on embedding generation only.
    Implementations can use different embedding providers (Ollama, OpenAI, Cohere, etc.).
    """

    async def embed_text(self, text: str) -> EmbeddingVector:
        """Generate embedding vector for a single text.

        Args:
            text: The text to embed

        Returns:
            EmbeddingVector with the generated embedding

        Raises:
            ValueError: If text is empty
            RuntimeError: If embedding generation fails
        """
        ...

    async def embed_batch(self, texts: List[str]) -> List[EmbeddingVector]:
        """Generate embedding vectors for multiple texts (batch processing).

        Args:
            texts: List of texts to embed

        Returns:
            List of EmbeddingVector objects in the same order as input

        Raises:
            ValueError: If texts list is empty
            RuntimeError: If embedding generation fails
        """
        ...
