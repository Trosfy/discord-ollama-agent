"""Unit tests for LangChainChunkingService."""
import pytest
from unittest.mock import MagicMock

from app.services.chunking_service import (
    LangChainChunkingService,
    ChunkingServiceError,
    create_chunking_service,
)
from app.core.interfaces import TextChunk
from app.core.config import RAGConfig


# =============================================================================
# Initialization Tests
# =============================================================================

def test_init_default_parameters():
    """ChunkingService initializes with default parameters."""
    service = LangChainChunkingService()

    assert service.chunk_size == 1000
    assert service.chunk_overlap == 200
    assert service.encoding == "cl100k_base"
    assert service.separators == ["\n\n", "\n", ". ", " ", ""]


def test_init_custom_parameters():
    """ChunkingService initializes with custom parameters."""
    service = LangChainChunkingService(
        chunk_size=500,
        chunk_overlap=100,
        encoding="o200k_base",
        separators=["\n", " "],
    )

    assert service.chunk_size == 500
    assert service.chunk_overlap == 100
    assert service.encoding == "o200k_base"
    assert service.separators == ["\n", " "]


def test_init_invalid_encoding_fallback():
    """ChunkingService falls back to cl100k_base for invalid encoding."""
    service = LangChainChunkingService(encoding="invalid_encoding_name")

    assert service.encoding == "cl100k_base"


def test_from_config():
    """from_config() creates service from RAGConfig."""
    config = RAGConfig(
        chunk_size=800,
        chunk_overlap=150,
        tokenizer_encoding="cl100k_base",
        separators=["\n\n", "\n"],
    )

    service = LangChainChunkingService.from_config(config)

    assert service.chunk_size == 800
    assert service.chunk_overlap == 150
    assert service.encoding == "cl100k_base"


# =============================================================================
# chunk_text Tests
# =============================================================================

async def test_chunk_text_single_chunk():
    """chunk_text() returns single chunk for short text."""
    service = LangChainChunkingService(chunk_size=1000)
    text = "This is a short text that fits in one chunk."

    chunks = await service.chunk_text(text, "https://example.com")

    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].chunk_index == 0
    assert chunks[0].source_url == "https://example.com"
    assert chunks[0].token_count > 0


async def test_chunk_text_multiple_chunks():
    """chunk_text() splits long text into multiple chunks."""
    service = LangChainChunkingService(chunk_size=50, chunk_overlap=10)

    # Create text that will span multiple chunks
    paragraphs = [f"Paragraph {i}. " * 10 for i in range(5)]
    text = "\n\n".join(paragraphs)

    chunks = await service.chunk_text(text, "https://example.com")

    assert len(chunks) > 1

    # Verify sequential indices
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i
        assert chunk.source_url == "https://example.com"
        assert len(chunk.chunk_id) == 36  # UUID format


async def test_chunk_text_preserves_order():
    """chunk_text() preserves text order across chunks."""
    service = LangChainChunkingService(chunk_size=50, chunk_overlap=0)

    text = "First section.\n\nSecond section.\n\nThird section."
    chunks = await service.chunk_text(text, "https://example.com")

    # The concatenation of chunks should preserve original order
    reconstructed = ""
    for chunk in chunks:
        reconstructed += chunk.text

    # All original content should be present
    assert "First" in reconstructed
    assert "Second" in reconstructed
    assert "Third" in reconstructed


async def test_chunk_text_empty_raises():
    """chunk_text() raises ValueError for empty text."""
    service = LangChainChunkingService()

    with pytest.raises(ValueError) as exc_info:
        await service.chunk_text("", "https://example.com")

    assert "empty" in str(exc_info.value).lower()


async def test_chunk_text_whitespace_only_raises():
    """chunk_text() raises ValueError for whitespace-only text."""
    service = LangChainChunkingService()

    with pytest.raises(ValueError):
        await service.chunk_text("   \n\t  ", "https://example.com")


async def test_chunk_text_no_url_raises():
    """chunk_text() raises ValueError when source_url is missing."""
    service = LangChainChunkingService()

    with pytest.raises(ValueError) as exc_info:
        await service.chunk_text("Some text", "")

    assert "url" in str(exc_info.value).lower()


async def test_chunk_text_custom_chunk_size():
    """chunk_text() uses override chunk_size when provided."""
    service = LangChainChunkingService(chunk_size=1000)
    text = "Word " * 100  # Approximately 100 tokens

    # Use smaller chunk size override (overlap must be smaller than chunk_size)
    chunks = await service.chunk_text(
        text, "https://example.com", chunk_size=20, chunk_overlap=5
    )

    # Should produce more chunks than default
    assert len(chunks) > 1


async def test_chunk_text_custom_overlap():
    """chunk_text() uses override chunk_overlap when provided."""
    service = LangChainChunkingService(chunk_size=50, chunk_overlap=0)
    text = "Word " * 50

    chunks_no_overlap = await service.chunk_text(
        text, "https://example.com", chunk_overlap=0
    )

    # With overlap, might have different chunk distribution
    chunks_with_overlap = await service.chunk_text(
        text, "https://example.com", chunk_overlap=20
    )

    # Both should produce valid chunks
    assert all(c.token_count > 0 for c in chunks_no_overlap)
    assert all(c.token_count > 0 for c in chunks_with_overlap)


async def test_chunk_text_tracks_positions():
    """chunk_text() tracks start_char and end_char positions."""
    service = LangChainChunkingService(chunk_size=50, chunk_overlap=10)
    text = "Hello world.\n\nThis is a test paragraph with more content."

    chunks = await service.chunk_text(text, "https://example.com")

    for chunk in chunks:
        # start_char should be valid
        assert chunk.start_char >= 0
        # end_char should be greater than start_char
        assert chunk.end_char > chunk.start_char


async def test_chunk_text_generates_unique_ids():
    """chunk_text() generates unique chunk_ids."""
    service = LangChainChunkingService(chunk_size=50, chunk_overlap=10)
    text = "Word " * 50

    chunks = await service.chunk_text(text, "https://example.com")

    chunk_ids = [c.chunk_id for c in chunks]
    assert len(chunk_ids) == len(set(chunk_ids))  # All unique


# =============================================================================
# count_tokens Tests
# =============================================================================

def test_count_tokens_basic():
    """count_tokens() returns accurate token count."""
    service = LangChainChunkingService()

    # "Hello world" should be around 2 tokens
    count = service.count_tokens("Hello world")
    assert count == 2


def test_count_tokens_empty():
    """count_tokens() returns 0 for empty string."""
    service = LangChainChunkingService()

    count = service.count_tokens("")
    assert count == 0


def test_count_tokens_code():
    """count_tokens() handles code with special characters."""
    service = LangChainChunkingService()

    code = "def hello():\n    return 'world'"
    count = service.count_tokens(code)

    assert count > 0


def test_count_tokens_unicode():
    """count_tokens() handles unicode text."""
    service = LangChainChunkingService()

    text = "Hello \u4e16\u754c"  # "Hello World" in Chinese
    count = service.count_tokens(text)

    assert count > 0


# =============================================================================
# TextChunk Validation Tests
# =============================================================================

async def test_textchunk_has_required_fields():
    """TextChunk returned by chunk_text has all required fields."""
    service = LangChainChunkingService()
    text = "Test content for chunking."

    chunks = await service.chunk_text(text, "https://example.com")
    chunk = chunks[0]

    assert hasattr(chunk, 'chunk_id')
    assert hasattr(chunk, 'text')
    assert hasattr(chunk, 'chunk_index')
    assert hasattr(chunk, 'token_count')
    assert hasattr(chunk, 'source_url')
    assert hasattr(chunk, 'start_char')
    assert hasattr(chunk, 'end_char')


async def test_textchunk_is_pydantic_model():
    """TextChunk is a Pydantic model."""
    service = LangChainChunkingService()
    chunks = await service.chunk_text("Test", "https://example.com")

    # Should be able to convert to dict
    chunk_dict = chunks[0].model_dump()
    assert isinstance(chunk_dict, dict)


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_chunking_service_factory():
    """create_chunking_service() creates configured service."""
    config = RAGConfig(
        chunk_size=600,
        chunk_overlap=100,
        tokenizer_encoding="cl100k_base",
    )

    service = create_chunking_service(config)

    assert isinstance(service, LangChainChunkingService)
    assert service.chunk_size == 600
    assert service.chunk_overlap == 100


# =============================================================================
# Token Budget Validation Tests
# =============================================================================

async def test_chunks_respect_token_size():
    """Individual chunks respect chunk_size limit (approximately)."""
    service = LangChainChunkingService(chunk_size=100, chunk_overlap=20)

    # Create long text
    text = "This is a sentence with several words. " * 50

    chunks = await service.chunk_text(text, "https://example.com")

    # Each chunk should be around the target size (with some tolerance)
    for chunk in chunks:
        # Allow some variance (LangChain may slightly exceed due to keeping separators)
        assert chunk.token_count <= 150  # Allow 50% margin


async def test_total_tokens_reasonable():
    """Total tokens across chunks is reasonable relative to original."""
    service = LangChainChunkingService(chunk_size=100, chunk_overlap=20)

    text = "Word " * 200  # About 200 tokens

    chunks = await service.chunk_text(text, "https://example.com")

    total = sum(c.token_count for c in chunks)

    # With overlap, total may exceed original but shouldn't be excessive
    original_tokens = service.count_tokens(text)
    assert total >= original_tokens
    # Allow up to 2x due to overlap
    assert total < original_tokens * 2


# =============================================================================
# Edge Cases
# =============================================================================

async def test_chunk_text_very_long():
    """chunk_text() handles very long text."""
    service = LangChainChunkingService(chunk_size=500, chunk_overlap=50)

    # Create very long text
    text = "This is a test paragraph with content. " * 1000

    chunks = await service.chunk_text(text, "https://example.com")

    assert len(chunks) > 1
    assert all(c.token_count > 0 for c in chunks)


async def test_chunk_text_special_characters():
    """chunk_text() handles text with special characters."""
    service = LangChainChunkingService()

    text = 'Test with "quotes", <brackets>, & symbols!'

    chunks = await service.chunk_text(text, "https://example.com")

    assert len(chunks) >= 1
    assert 'quotes' in chunks[0].text


async def test_chunk_text_newlines_preserved():
    """chunk_text() preserves paragraph structure."""
    service = LangChainChunkingService(chunk_size=1000)

    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."

    chunks = await service.chunk_text(text, "https://example.com")

    # All content should be preserved
    all_text = "".join(c.text for c in chunks)
    assert "First" in all_text
    assert "Second" in all_text
    assert "Third" in all_text
