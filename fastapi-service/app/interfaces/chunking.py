"""Interface for text chunking services."""
from abc import ABC, abstractmethod
from typing import List, Protocol
from pydantic import BaseModel


class TextChunk(BaseModel):
    """Represents a chunk of text with metadata."""
    chunk_id: str  # Unique identifier (UUID)
    text: str  # The actual chunk text
    chunk_index: int  # Position in original document (0-based)
    token_count: int  # Number of tokens in this chunk
    source_url: str  # Original source URL
    start_char: int  # Starting character position in original text
    end_char: int  # Ending character position in original text


class IChunkingService(Protocol):
    """Interface for text chunking services.

    Follows Interface Segregation Principle - focused on chunking only.
    Implementations can use different chunking strategies (recursive, semantic, etc.).
    """

    async def chunk_text(
        self,
        text: str,
        source_url: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[TextChunk]:
        """Split text into overlapping chunks with metadata.

        Args:
            text: The text content to chunk
            source_url: Source URL for attribution
            chunk_size: Target tokens per chunk
            chunk_overlap: Token overlap between consecutive chunks

        Returns:
            List of TextChunk objects with IDs, indices, and metadata

        Raises:
            ValueError: If text is empty or parameters are invalid
        """
        ...
