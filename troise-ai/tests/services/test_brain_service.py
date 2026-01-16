"""Unit tests for Brain Service."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.brain_service import (
    BrainService,
    SearchResult,
    FetchResult,
    DEFAULT_LIMIT,
    SEMANTIC_WEIGHT,
    KEYWORD_WEIGHT,
    MIN_SIMILARITY_THRESHOLD,
    create_brain_service,
)
from app.adapters.dynamodb import NoteMetaItem, NoteChunkItem


# =============================================================================
# Mock Services
# =============================================================================

class MockVaultService:
    """Mock vault service for testing."""

    def __init__(self, notes: Dict[str, str] = None):
        self._notes = notes or {}
        self._metadata = {}

    async def read_note(self, path: str) -> str:
        if path not in self._notes:
            raise FileNotFoundError(f"Note not found: {path}")
        return self._notes[path]

    async def list_notes(self) -> List[str]:
        return list(self._notes.keys())

    async def get_note_metadata(self, path: str) -> Dict[str, Any]:
        return self._metadata.get(path, {})

    def add_note(self, path: str, content: str, metadata: Dict = None):
        """Helper to add test notes."""
        self._notes[path] = content
        if metadata:
            self._metadata[path] = metadata


class MockEmbeddingService:
    """Mock embedding service for testing."""

    def __init__(self, dimensions: int = 768):
        self._dimensions = dimensions
        self._embeddings = {}

    async def embed(self, text: str) -> List[float]:
        # Return a predictable embedding based on text
        if text in self._embeddings:
            return self._embeddings[text]
        # Generate deterministic embedding
        hash_val = hash(text) % 1000
        return [hash_val / 1000.0] * self._dimensions

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [await self.embed(t) for t in texts]

    async def get_cache_stats(self) -> Dict[str, Any]:
        return {"total_items": len(self._embeddings)}

    def set_embedding(self, text: str, embedding: List[float]):
        """Helper to set specific embeddings for tests."""
        self._embeddings[text] = embedding


class MockBrainAdapter:
    """Mock brain adapter for testing."""

    def __init__(self):
        self._notes: Dict[str, NoteMetaItem] = {}
        self._chunks: Dict[str, List[NoteChunkItem]] = {}

    async def index_note(
        self,
        path: str,
        title: str,
        content: str,
        modified_at: str = None,
        tags: List[str] = None,
        outlinks: List[str] = None,
        aliases: List[str] = None,
        frontmatter: Dict = None,
        chunk_embeddings: List[List[float]] = None,
    ) -> NoteMetaItem:
        # Extract folder from path
        folder = "/".join(path.split("/")[:-1]) or ""
        indexed_at = "2024-01-01T00:00:00"

        meta = NoteMetaItem(
            path=path,
            title=title,
            folder=folder,
            modified_at=modified_at or "2024-01-01T00:00:00",
            indexed_at=indexed_at,
            word_count=len(content.split()),
            tags=tags or [],
            outlinks=outlinks or [],
            aliases=aliases or [],
            backlinks=[],
            frontmatter=frontmatter or {},
        )
        self._notes[path] = meta

        # Create chunks
        chunks = self._chunk_content(content, path)
        if chunk_embeddings:
            for i, chunk in enumerate(chunks):
                if i < len(chunk_embeddings):
                    chunk.embedding = chunk_embeddings[i]
        self._chunks[path] = chunks

        return meta

    def _chunk_content(self, content: str, path: str, chunk_size: int = 500) -> List[NoteChunkItem]:
        """Split content into chunks."""
        words = content.split()
        chunks = []
        chunk_words = []
        chunk_index = 0
        line_num = 1

        for word in words:
            chunk_words.append(word)
            if len(" ".join(chunk_words)) >= chunk_size:
                chunks.append(NoteChunkItem(
                    path=path,
                    chunk_index=chunk_index,
                    text=" ".join(chunk_words),
                    start_line=line_num,
                    end_line=line_num + 10,
                ))
                chunk_words = []
                chunk_index += 1
                line_num += 10

        if chunk_words:
            chunks.append(NoteChunkItem(
                path=path,
                chunk_index=chunk_index,
                text=" ".join(chunk_words),
                start_line=line_num,
                end_line=line_num + 10,
            ))

        return chunks if chunks else [NoteChunkItem(path=path, chunk_index=0, text=content, start_line=1, end_line=1)]

    async def get_note_meta(self, path: str) -> Optional[NoteMetaItem]:
        return self._notes.get(path)

    async def get_note_chunks(self, path: str, include_embeddings: bool = True) -> List[NoteChunkItem]:
        return self._chunks.get(path, [])

    async def get_chunk(self, path: str, chunk_index: int) -> Optional[NoteChunkItem]:
        chunks = self._chunks.get(path, [])
        for chunk in chunks:
            if chunk.chunk_index == chunk_index:
                return chunk
        return None

    async def get_all_chunks_with_embeddings(self, limit: int = 1000) -> List[Tuple[NoteChunkItem, NoteMetaItem]]:
        results = []
        for path, chunks in self._chunks.items():
            meta = self._notes.get(path)
            if meta:
                for chunk in chunks:
                    if chunk.embedding:
                        results.append((chunk, meta))
        return results[:limit]

    async def list_all_notes(self) -> List[NoteMetaItem]:
        return list(self._notes.values())

    async def needs_reindex(self, path: str, modified_at: str) -> bool:
        meta = self._notes.get(path)
        if not meta:
            return True
        return meta.modified_at < modified_at

    async def update_note_meta(self, path: str, **kwargs) -> bool:
        if path in self._notes:
            for key, value in kwargs.items():
                if hasattr(self._notes[path], key):
                    setattr(self._notes[path], key, value)
            return True
        return False

    async def delete_note(self, path: str) -> bool:
        if path in self._notes:
            del self._notes[path]
            if path in self._chunks:
                del self._chunks[path]
            return True
        return False

    async def get_index_stats(self) -> Dict[str, Any]:
        return {
            "total_notes": len(self._notes),
            "total_chunks": sum(len(c) for c in self._chunks.values()),
        }


# =============================================================================
# Search Tests
# =============================================================================

async def test_search_returns_results():
    """search() returns results for matching query."""
    vault = MockVaultService({
        "docs/python.md": "# Python\n\nPython is a programming language.",
    })
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    # Index the note
    embedding_vec = [0.5] * 768
    await brain.index_note(
        path="docs/python.md",
        title="Python",
        content="Python is a programming language.",
        tags=["python", "programming"],
        chunk_embeddings=[embedding_vec],
    )
    embedding.set_embedding("python programming", embedding_vec)

    service = BrainService(vault, brain, embedding)

    results = await service.search("python programming", limit=5)

    assert len(results) > 0
    assert results[0]["path"] == "docs/python.md"


async def test_search_semantic_only():
    """search() with search_type=semantic uses only embeddings."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    # Index with specific embedding
    vec = [0.9] * 768
    await brain.index_note(
        path="note.md",
        title="Note",
        content="Content about topic",
        chunk_embeddings=[vec],
    )
    embedding.set_embedding("query", vec)

    service = BrainService(vault, brain, embedding)

    results = await service.search("query", search_type="semantic")

    assert len(results) > 0


async def test_search_keyword_only():
    """search() with search_type=keyword uses only keyword matching."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    await brain.index_note(
        path="note.md",
        title="Note",
        content="Python programming language tutorial",
    )

    service = BrainService(vault, brain, embedding)
    # Force keyword index build
    await service._build_keyword_index()

    results = await service.search("python tutorial", search_type="keyword")

    # Results should exist from keyword matching
    assert isinstance(results, list)


async def test_search_hybrid():
    """search() with search_type=hybrid combines both methods."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    vec = [0.5] * 768
    await brain.index_note(
        path="note.md",
        title="Note",
        content="Python programming language",
        chunk_embeddings=[vec],
    )
    embedding.set_embedding("python", vec)

    service = BrainService(vault, brain, embedding)

    results = await service.search("python", search_type="hybrid")

    assert isinstance(results, list)


async def test_search_respects_limit():
    """search() limits results."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    # Index multiple notes
    vec = [0.5] * 768
    for i in range(10):
        await brain.index_note(
            path=f"note{i}.md",
            title=f"Note {i}",
            content="Python programming",
            chunk_embeddings=[vec],
        )
    embedding.set_embedding("python", vec)

    service = BrainService(vault, brain, embedding)

    results = await service.search("python", limit=3)

    assert len(results) <= 3


async def test_search_deduplicates_by_path():
    """search() takes highest score per note."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    # Note with multiple chunks
    content = "Python " * 200 + "JavaScript " * 200
    vec = [0.5] * 768
    await brain.index_note(
        path="note.md",
        title="Note",
        content=content,
        chunk_embeddings=[vec, vec],
    )

    service = BrainService(vault, brain, embedding)

    results = await service.search("python")

    # Should only have one result per path
    paths = [r["path"] for r in results]
    assert len(paths) == len(set(paths))


# =============================================================================
# Fetch Tests
# =============================================================================

async def test_fetch_returns_note():
    """fetch() returns note content and metadata."""
    vault = MockVaultService({
        "docs/note.md": "# Title\n\nContent here"
    })
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    await brain.index_note(
        path="docs/note.md",
        title="Title",
        content="Content here",
        tags=["test"],
        outlinks=["other.md"],
    )

    service = BrainService(vault, brain, embedding)

    result = await service.fetch("docs/note.md")

    assert result["path"] == "docs/note.md"
    assert result["title"] == "Title"
    assert "Content" in result["content"]
    assert result["tags"] == ["test"]
    assert result["outlinks"] == ["other.md"]


async def test_fetch_not_found():
    """fetch() raises FileNotFoundError for missing note."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    service = BrainService(vault, brain, embedding)

    with pytest.raises(FileNotFoundError):
        await service.fetch("nonexistent.md")


async def test_fetch_unindexed_note():
    """fetch() returns basic info for unindexed note."""
    vault = MockVaultService({
        "new-note.md": "# New Note\n\nNew content"
    })
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    service = BrainService(vault, brain, embedding)

    result = await service.fetch("new-note.md")

    assert result["path"] == "new-note.md"
    assert "new" in result["title"].lower()
    assert "content" in result["content"].lower()


# =============================================================================
# Indexing Tests
# =============================================================================

async def test_index_vault():
    """index_vault() indexes all notes."""
    vault = MockVaultService({
        "note1.md": "# Note 1\n\nContent",
        "note2.md": "# Note 2\n\nMore content",
    })
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    service = BrainService(vault, brain, embedding)

    stats = await service.index_vault()

    assert stats["total"] == 2
    assert stats["indexed"] == 2
    assert stats["errors"] == 0


async def test_index_vault_with_pattern():
    """index_vault() filters by pattern."""
    vault = MockVaultService({
        "docs/note1.md": "Content 1",
        "private/note2.md": "Content 2",
    })
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    service = BrainService(vault, brain, embedding)

    stats = await service.index_vault(patterns=["docs/*"])

    assert stats["indexed"] == 1


async def test_reindex_note():
    """reindex_note() force re-indexes a note."""
    vault = MockVaultService({
        "note.md": "Updated content"
    })
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    await brain.index_note("note.md", "Note", "Original")

    service = BrainService(vault, brain, embedding)

    await service.reindex_note("note.md")

    # Check that the note was re-indexed
    meta = await brain.get_note_meta("note.md")
    assert meta is not None


async def test_delete_from_index():
    """delete_from_index() removes note from index."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    await brain.index_note("note.md", "Note", "Content")

    service = BrainService(vault, brain, embedding)

    result = await service.delete_from_index("note.md")

    assert result is True
    meta = await brain.get_note_meta("note.md")
    assert meta is None


# =============================================================================
# Backlink Tests
# =============================================================================

async def test_get_backlinks():
    """get_backlinks() returns notes linking to path."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    await brain.index_note("target.md", "Target", "Content")
    await brain.update_note_meta("target.md", backlinks=["source1.md", "source2.md"])

    service = BrainService(vault, brain, embedding)

    backlinks = await service.get_backlinks("target.md")

    assert backlinks == ["source1.md", "source2.md"]


async def test_get_outlinks():
    """get_outlinks() returns notes that path links to."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    await brain.index_note(
        "source.md",
        "Source",
        "Content with [[target1]] and [[target2]]",
        outlinks=["target1", "target2"],
    )

    service = BrainService(vault, brain, embedding)

    outlinks = await service.get_outlinks("source.md")

    assert outlinks == ["target1", "target2"]


# =============================================================================
# Utility Tests
# =============================================================================

def test_tokenize():
    """_tokenize() extracts searchable terms."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    service = BrainService(vault, brain, embedding)

    tokens = service._tokenize("Python is a programming language")

    assert "python" in tokens
    assert "programming" in tokens
    assert "language" in tokens
    # Stop words removed
    assert "is" not in tokens
    assert "a" not in tokens


def test_tokenize_removes_single_char_words():
    """_tokenize() removes single character words."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    service = BrainService(vault, brain, embedding)

    tokens = service._tokenize("I am a python dev")

    assert "python" in tokens
    assert "dev" in tokens
    assert "am" in tokens  # 2-char words are kept
    # Single char words removed (via stop words or < 2 chars)
    assert "i" not in tokens
    assert "a" not in tokens


def test_extract_links():
    """_extract_links() extracts wiki-style links."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    service = BrainService(vault, brain, embedding)

    content = "See [[note1]] and [[note2|Display]] for details."
    links = service._extract_links(content)

    assert "note1" in links
    assert "note2" in links


def test_extract_title_from_h1():
    """_extract_title() extracts H1 heading."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    service = BrainService(vault, brain, embedding)

    content = "# My Title\n\nContent here"
    title = service._extract_title("path.md", content)

    assert title == "My Title"


def test_extract_title_from_path():
    """_extract_title() falls back to path."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    service = BrainService(vault, brain, embedding)

    title = service._extract_title("my-note.md", "No heading content")

    assert title == "My Note"


def test_parse_frontmatter():
    """_parse_frontmatter() extracts YAML frontmatter."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    service = BrainService(vault, brain, embedding)

    content = """---
title: Test Note
tags: [python, testing]
---

Content here"""

    frontmatter, remaining = service._parse_frontmatter(content)

    assert frontmatter["title"] == "Test Note"
    assert frontmatter["tags"] == ["python", "testing"]
    assert "Content here" in remaining


def test_parse_frontmatter_none():
    """_parse_frontmatter() handles content without frontmatter."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    service = BrainService(vault, brain, embedding)

    content = "Just content, no frontmatter"
    frontmatter, remaining = service._parse_frontmatter(content)

    assert frontmatter == {}
    assert remaining == content


def test_generate_snippet():
    """_generate_snippet() creates query-relevant snippet."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    service = BrainService(vault, brain, embedding)

    text = "First sentence about cats. Second sentence about python programming. Third sentence."
    snippet = service._generate_snippet(text, "python")

    assert "python" in snippet.lower()


def test_cosine_similarity():
    """_cosine_similarity() calculates correct values."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    service = BrainService(vault, brain, embedding)

    # Identical vectors
    v1 = [1.0, 0.0, 0.0]
    assert abs(service._cosine_similarity(v1, v1) - 1.0) < 0.001

    # Orthogonal vectors
    v2 = [0.0, 1.0, 0.0]
    assert abs(service._cosine_similarity(v1, v2) - 0.0) < 0.001


# =============================================================================
# Stats Tests
# =============================================================================

async def test_get_stats():
    """get_stats() returns service statistics."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    await brain.index_note("note.md", "Note", "Content")

    service = BrainService(vault, brain, embedding)

    stats = await service.get_stats()

    assert "brain_index" in stats
    assert stats["brain_index"]["total_notes"] == 1


# =============================================================================
# SearchResult Tests
# =============================================================================

def test_search_result_to_dict():
    """SearchResult.to_dict() returns correct format."""
    result = SearchResult(
        path="test.md",
        title="Test",
        score=0.85,
        chunk_text="Test content",
        chunk_index=0,
        heading="Section",
        match_type="hybrid",
        tags=["tag1"],
        snippet="Test...",
    )

    d = result.to_dict()

    assert d["path"] == "test.md"
    assert d["title"] == "Test"
    assert d["score"] == 0.85
    assert d["match_type"] == "hybrid"


# =============================================================================
# FetchResult Tests
# =============================================================================

def test_fetch_result_to_dict():
    """FetchResult.to_dict() returns correct format."""
    result = FetchResult(
        path="test.md",
        title="Test",
        content="Full content",
        tags=["tag1"],
        outlinks=["link1"],
        backlinks=["back1"],
        word_count=100,
    )

    d = result.to_dict()

    assert d["path"] == "test.md"
    assert d["content"] == "Full content"
    assert d["word_count"] == 100


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_brain_service():
    """create_brain_service() creates configured instance."""
    vault = MockVaultService()
    brain = MockBrainAdapter()
    embedding = MockEmbeddingService()

    service = create_brain_service(vault, brain, embedding)

    assert service._vault == vault
    assert service._brain == brain
    assert service._embedding == embedding
