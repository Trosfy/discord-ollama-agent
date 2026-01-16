"""Text chunking service using LangChain with tiktoken for token counting."""
import uuid
import logging
from typing import List, Optional

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.interfaces import TextChunk, IChunkingService
from app.core.config import RAGConfig

logger = logging.getLogger(__name__)


class ChunkingServiceError(Exception):
    """Error during text chunking."""
    pass


class LangChainChunkingService:
    """Chunking service using LangChain's RecursiveCharacterTextSplitter.

    Implements IChunkingService following Single Responsibility Principle.
    Uses tiktoken for accurate token counting.

    All parameters are configurable via RAGConfig.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        encoding: str = "cl100k_base",
        separators: Optional[List[str]] = None,
    ):
        """Initialize chunking service with LangChain splitter.

        Args:
            chunk_size: Target tokens per chunk
            chunk_overlap: Token overlap between chunks
            encoding: tiktoken encoding name (cl100k_base, o200k_base, etc.)
            separators: List of separators for splitting (in priority order)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = encoding
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

        # Initialize tiktoken encoder for token counting
        try:
            self.tokenizer = tiktoken.get_encoding(encoding)
        except Exception as e:
            logger.warning(f"Failed to load encoding {encoding}, falling back to cl100k_base: {e}")
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
            self.encoding = "cl100k_base"

        # Create LangChain text splitter with tiktoken
        self.text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name=self.encoding,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators,
            keep_separator=True  # Keep separators for context
        )

        logger.info(
            f"LangChainChunkingService initialized "
            f"(chunk_size={self.chunk_size}, overlap={self.chunk_overlap}, encoding={self.encoding})"
        )

    @classmethod
    def from_config(cls, config: RAGConfig) -> "LangChainChunkingService":
        """Create chunking service from RAGConfig.

        Args:
            config: RAGConfig instance

        Returns:
            Configured LangChainChunkingService
        """
        return cls(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            encoding=config.tokenizer_encoding,
            separators=config.separators,
        )

    async def chunk_text(
        self,
        text: str,
        source_url: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ) -> List[TextChunk]:
        """Split text into overlapping chunks using LangChain.

        Args:
            text: The text content to chunk
            source_url: Source URL for attribution
            chunk_size: Override default chunk size (optional)
            chunk_overlap: Override default overlap (optional)

        Returns:
            List of TextChunk objects with metadata

        Raises:
            ValueError: If text is empty or parameters are invalid
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        if not source_url:
            raise ValueError("Source URL is required")

        # Use custom splitter if parameters differ from defaults
        if chunk_size is not None or chunk_overlap is not None:
            custom_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                encoding_name=self.encoding,
                chunk_size=chunk_size if chunk_size is not None else self.chunk_size,
                chunk_overlap=chunk_overlap if chunk_overlap is not None else self.chunk_overlap,
                separators=self.separators,
                keep_separator=True
            )
            splits = custom_splitter.split_text(text)
        else:
            splits = self.text_splitter.split_text(text)

        # Create TextChunk objects with metadata
        chunks = []
        current_pos = 0

        for idx, chunk_text in enumerate(splits):
            # Find actual position in original text
            start_char = text.find(chunk_text, current_pos)
            if start_char == -1:
                # Fallback: use current position (may happen with overlaps)
                start_char = current_pos
            end_char = start_char + len(chunk_text)
            current_pos = end_char

            # Count tokens for this chunk
            token_count = len(self.tokenizer.encode(chunk_text))

            chunk = TextChunk(
                chunk_id=str(uuid.uuid4()),
                text=chunk_text,
                chunk_index=idx,
                token_count=token_count,
                source_url=source_url,
                start_char=start_char,
                end_char=end_char
            )
            chunks.append(chunk)

        total_tokens = sum(c.token_count for c in chunks)
        logger.debug(
            f"Chunked text from {source_url} into {len(chunks)} chunks "
            f"(total tokens: {total_tokens})"
        )

        return chunks

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using configured encoding.

        Args:
            text: Text to count tokens for

        Returns:
            Token count
        """
        return len(self.tokenizer.encode(text))


def create_chunking_service(config: RAGConfig) -> LangChainChunkingService:
    """Factory function to create chunking service from config.

    Args:
        config: RAGConfig instance

    Returns:
        Configured LangChainChunkingService
    """
    return LangChainChunkingService.from_config(config)
