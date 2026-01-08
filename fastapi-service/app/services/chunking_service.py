"""Text chunking service using LangChain with tiktoken for token counting."""
import uuid
from typing import List
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.interfaces.chunking import TextChunk, IChunkingService
from app.config import settings
import logging_client

logger = logging_client.setup_logger('chunking_service')


class LangChainChunkingService:
    """Chunking service using LangChain's RecursiveCharacterTextSplitter.

    Implements IChunkingService following Single Responsibility Principle.
    Uses tiktoken for accurate token counting.
    """

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        encoding_name: str = "cl100k_base"  # GPT-3.5/GPT-4 encoding
    ):
        """Initialize chunking service with LangChain splitter.

        Args:
            chunk_size: Tokens per chunk (defaults to settings.CHUNK_SIZE)
            chunk_overlap: Token overlap (defaults to settings.CHUNK_OVERLAP)
            encoding_name: tiktoken encoding name for token counting
        """
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self.encoding_name = encoding_name

        # Initialize tiktoken encoder for token counting
        self.tokenizer = tiktoken.get_encoding(encoding_name)

        # Create LangChain text splitter with tiktoken
        self.text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name=encoding_name,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],  # Try paragraph, line, sentence, word
            keep_separator=True  # Keep separators for context
        )

        logger.info(
            f"✅ LangChainChunkingService initialized "
            f"(chunk_size={self.chunk_size}, overlap={self.chunk_overlap})"
        )

    async def chunk_text(
        self,
        text: str,
        source_url: str,
        chunk_size: int = None,
        chunk_overlap: int = None
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
        if chunk_size or chunk_overlap:
            custom_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                encoding_name=self.encoding_name,
                chunk_size=chunk_size or self.chunk_size,
                chunk_overlap=chunk_overlap or self.chunk_overlap,
                separators=["\n\n", "\n", ". ", " ", ""],
                keep_separator=True
            )
            splits = custom_splitter.split_text(text)
        else:
            splits = self.text_splitter.split_text(text)

        logger.info(
            f"📄 Chunked text from {source_url} into {len(splits)} chunks "
            f"(size={chunk_size or self.chunk_size}, overlap={chunk_overlap or self.chunk_overlap})"
        )

        # Create TextChunk objects with metadata
        chunks = []
        current_pos = 0

        for idx, chunk_text in enumerate(splits):
            # Find actual position in original text
            start_char = text.find(chunk_text, current_pos)
            if start_char == -1:
                # Fallback: use current position
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

        logger.debug(
            f"✅ Created {len(chunks)} TextChunk objects "
            f"(total tokens: {sum(c.token_count for c in chunks)})"
        )

        return chunks
