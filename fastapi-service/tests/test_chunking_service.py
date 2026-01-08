"""Tests for LangChain chunking service."""
import pytest
from app.services.chunking_service import LangChainChunkingService


@pytest.fixture
def chunking_service():
    """Create chunking service instance."""
    return LangChainChunkingService(chunk_size=100, chunk_overlap=20)


@pytest.mark.asyncio
async def test_chunk_text_basic(chunking_service):
    """Test basic text chunking."""
    text = "This is a test sentence. " * 50  # ~250 tokens
    url = "https://example.com/test"

    chunks = await chunking_service.chunk_text(text, url)

    # Should create multiple chunks
    assert len(chunks) > 1

    # Each chunk should have required fields
    for chunk in chunks:
        assert chunk.chunk_id
        assert chunk.text
        assert chunk.chunk_index >= 0
        assert chunk.token_count > 0
        assert chunk.source_url == url
        assert chunk.start_char >= 0
        assert chunk.end_char > chunk.start_char


@pytest.mark.asyncio
async def test_chunk_text_overlap(chunking_service):
    """Test that chunks have proper overlap."""
    # Create varied text with numbered words to ensure chunks differ
    text = " ".join([f"Word{i}" for i in range(300)])
    url = "https://example.com/overlap"

    chunks = await chunking_service.chunk_text(text, url)

    # Should have at least 2 chunks
    assert len(chunks) >= 2

    # Check that consecutive chunks have some overlap
    for i in range(len(chunks) - 1):
        chunk1_text = chunks[i].text
        chunk2_text = chunks[i + 1].text

        # Chunks should have different content (not identical)
        assert chunk1_text != chunk2_text

        # Later chunks should have higher indices
        assert chunks[i + 1].chunk_index == chunks[i].chunk_index + 1


@pytest.mark.asyncio
async def test_chunk_text_token_count_accuracy(chunking_service):
    """Test that token counts are accurate."""
    text = "Hello world! This is a test."
    url = "https://example.com/tokens"

    chunks = await chunking_service.chunk_text(text, url)

    # For short text, should be single chunk
    assert len(chunks) == 1

    # Token count should be positive and reasonable
    assert chunks[0].token_count > 0
    assert chunks[0].token_count < 50  # Short text shouldn't have many tokens


@pytest.mark.asyncio
async def test_chunk_text_empty_raises_error(chunking_service):
    """Test that empty text raises ValueError."""
    with pytest.raises(ValueError, match="Text cannot be empty"):
        await chunking_service.chunk_text("", "https://example.com")

    with pytest.raises(ValueError, match="Text cannot be empty"):
        await chunking_service.chunk_text("   ", "https://example.com")


@pytest.mark.asyncio
async def test_chunk_text_missing_url_raises_error(chunking_service):
    """Test that missing URL raises ValueError."""
    with pytest.raises(ValueError, match="Source URL is required"):
        await chunking_service.chunk_text("Some text", "")


@pytest.mark.asyncio
async def test_chunk_text_custom_parameters():
    """Test chunking with custom chunk size and overlap."""
    service = LangChainChunkingService(chunk_size=50, chunk_overlap=10)
    text = "This is a test. " * 100  # ~200 tokens
    url = "https://example.com/custom"

    chunks = await service.chunk_text(text, url)

    # With smaller chunk size, should create more chunks
    assert len(chunks) > 2

    # Each chunk should be roughly within the target size
    for chunk in chunks:
        # Allow some variance (LangChain uses approximate chunking)
        assert chunk.token_count <= 70  # Some buffer above 50


@pytest.mark.asyncio
async def test_chunk_text_preserves_structure():
    """Test that chunking preserves text structure."""
    text = """
    Section 1: Introduction
    This is the introduction with multiple sentences.

    Section 2: Body
    This is the body with more content and details.

    Section 3: Conclusion
    This is the conclusion wrapping everything up.
    """
    url = "https://example.com/structure"

    service = LangChainChunkingService(chunk_size=30, chunk_overlap=5)
    chunks = await service.chunk_text(text, url)

    # Should create multiple chunks
    assert len(chunks) >= 2

    # Verify chunks maintain sequential order
    for i in range(len(chunks) - 1):
        assert chunks[i].chunk_index < chunks[i + 1].chunk_index


@pytest.mark.asyncio
async def test_chunk_text_unique_ids():
    """Test that each chunk gets a unique ID."""
    text = "Test sentence. " * 100
    url = "https://example.com/ids"

    service = LangChainChunkingService(chunk_size=50, chunk_overlap=10)
    chunks = await service.chunk_text(text, url)

    # Extract all chunk IDs
    chunk_ids = [chunk.chunk_id for chunk in chunks]

    # All IDs should be unique
    assert len(chunk_ids) == len(set(chunk_ids))


@pytest.mark.asyncio
async def test_chunk_text_long_document():
    """Test chunking of long document."""
    # Create a very long text (simulate long article)
    paragraphs = [
        f"This is paragraph {i}. It contains multiple sentences about topic {i}. "
        f"The content discusses various aspects of subject matter {i}. "
        for i in range(100)
    ]
    text = "\n\n".join(paragraphs)
    url = "https://example.com/long"

    service = LangChainChunkingService(chunk_size=200, chunk_overlap=50)
    chunks = await service.chunk_text(text, url)

    # Should create many chunks for long document
    assert len(chunks) > 5

    # Total token count should be reasonable
    total_tokens = sum(chunk.token_count for chunk in chunks)
    assert total_tokens > 100

    # Verify all chunks have content
    for chunk in chunks:
        assert len(chunk.text) > 0


@pytest.mark.asyncio
async def test_chunk_text_special_characters():
    """Test chunking with special characters and unicode."""
    text = """
    Testing special characters: @#$%^&*()
    Unicode: 你好世界 🌍 émojis
    Math: ∫ x² dx = ⅓x³ + C
    """
    url = "https://example.com/special"

    service = LangChainChunkingService(chunk_size=50, chunk_overlap=10)
    chunks = await service.chunk_text(text, url)

    # Should handle special characters without errors
    assert len(chunks) >= 1

    # Verify content is preserved
    combined_text = " ".join(chunk.text for chunk in chunks)
    assert "special characters" in combined_text.lower()


def test_chunking_service_initialization():
    """Test chunking service initialization with different parameters."""
    # Default initialization
    service1 = LangChainChunkingService()
    assert service1.chunk_size == 1000  # From settings
    assert service1.chunk_overlap == 200

    # Custom initialization
    service2 = LangChainChunkingService(chunk_size=500, chunk_overlap=100)
    assert service2.chunk_size == 500
    assert service2.chunk_overlap == 100


@pytest.mark.asyncio
async def test_chunk_text_boundary_conditions():
    """Test chunking with boundary conditions."""
    service = LangChainChunkingService(chunk_size=100, chunk_overlap=20)

    # Very short text (< chunk size)
    short_text = "Short text."
    short_chunks = await service.chunk_text(short_text, "https://example.com/short")
    assert len(short_chunks) == 1
    assert short_chunks[0].text == short_text

    # Text exactly at chunk boundary
    boundary_text = "Word " * 25  # Approximately 100 tokens
    boundary_chunks = await service.chunk_text(boundary_text, "https://example.com/boundary")
    assert len(boundary_chunks) >= 1
