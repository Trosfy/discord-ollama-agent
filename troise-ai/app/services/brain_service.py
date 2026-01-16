"""
Brain Service for TROISE AI.

Provides unified search over the Obsidian vault knowledge base.
Combines semantic (embedding-based) and keyword search for hybrid retrieval.

Features:
- Semantic search using embeddings
- Keyword/BM25-style search
- Hybrid search combining both approaches
- Note indexing and re-indexing
- Backlink resolution
- Implements IBrainService interface

Architecture:
    VaultService (reads files) -> BrainService -> TroiseBrainAdapter (DynamoDB)
                                              -> EmbeddingService (vectors)
"""

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.interfaces import IBrainService, IVaultService, IEmbeddingService
from app.adapters.dynamodb import (
    DynamoDBClient,
    TroiseBrainAdapter,
    NoteMetaItem,
    NoteChunkItem,
)

logger = logging.getLogger(__name__)

# Search configuration
DEFAULT_LIMIT = 5
SEMANTIC_WEIGHT = 0.7  # Weight for semantic search in hybrid
KEYWORD_WEIGHT = 0.3   # Weight for keyword search in hybrid
MIN_SIMILARITY_THRESHOLD = 0.3  # Minimum similarity to include


@dataclass
class SearchResult:
    """Result from brain search."""
    path: str
    title: str
    score: float  # Combined relevance score (0.0-1.0)
    chunk_text: str
    chunk_index: int
    heading: Optional[str] = None
    match_type: str = "hybrid"  # semantic, keyword, or hybrid
    tags: List[str] = field(default_factory=list)
    snippet: Optional[str] = None  # Highlighted snippet

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "path": self.path,
            "title": self.title,
            "score": round(self.score, 3),
            "chunk_text": self.chunk_text,
            "chunk_index": self.chunk_index,
            "heading": self.heading,
            "match_type": self.match_type,
            "tags": self.tags,
            "snippet": self.snippet,
        }


@dataclass
class FetchResult:
    """Result from fetching a note."""
    path: str
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    outlinks: List[str] = field(default_factory=list)
    backlinks: List[str] = field(default_factory=list)
    modified_at: Optional[str] = None
    word_count: int = 0
    frontmatter: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "path": self.path,
            "title": self.title,
            "content": self.content,
            "tags": self.tags,
            "outlinks": self.outlinks,
            "backlinks": self.backlinks,
            "modified_at": self.modified_at,
            "word_count": self.word_count,
            "frontmatter": self.frontmatter,
        }


class BrainService:
    """
    Service for searching and managing the knowledge base.

    Provides hybrid search combining semantic and keyword approaches.
    Implements the IBrainService protocol.

    Example:
        service = BrainService(
            vault=VaultService("/path/to/vault"),
            brain_adapter=TroiseBrainAdapter(dynamo_client),
            embedding_service=EmbeddingService(...)
        )

        # Search for relevant notes
        results = await service.search("how does authentication work?")

        # Fetch full note content
        note = await service.fetch("docs/auth/overview.md")

        # Index the vault
        await service.index_vault()
    """

    def __init__(
        self,
        vault: IVaultService,
        brain_adapter: TroiseBrainAdapter,
        embedding_service: IEmbeddingService,
        semantic_weight: float = SEMANTIC_WEIGHT,
        keyword_weight: float = KEYWORD_WEIGHT,
    ):
        """
        Initialize the brain service.

        Args:
            vault: Vault service for reading note content.
            brain_adapter: DynamoDB adapter for brain index.
            embedding_service: Service for generating embeddings.
            semantic_weight: Weight for semantic search (0.0-1.0).
            keyword_weight: Weight for keyword search (0.0-1.0).
        """
        self._vault = vault
        self._brain = brain_adapter
        self._embedding = embedding_service
        self._semantic_weight = semantic_weight
        self._keyword_weight = keyword_weight

        # In-memory keyword index for fast lookups
        self._keyword_index: Dict[str, List[Tuple[str, int]]] = {}
        self._keyword_index_built = False

    # ========== Search Operations (IBrainService) ==========

    async def search(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        search_type: str = "hybrid",
        min_score: float = MIN_SIMILARITY_THRESHOLD,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant notes.

        Implements IBrainService.search protocol.

        Args:
            query: Search query string.
            limit: Maximum number of results.
            search_type: Type of search (semantic, keyword, hybrid).
            min_score: Minimum relevance score to include.

        Returns:
            List of result dictionaries with path, title, score, chunk_text.
        """
        if search_type == "semantic":
            results = await self._semantic_search(query, limit * 2, min_score)
        elif search_type == "keyword":
            results = await self._keyword_search(query, limit * 2, min_score)
        else:
            results = await self._hybrid_search(query, limit * 2, min_score)

        # Deduplicate by path (take highest scoring chunk per note)
        seen_paths = {}
        for result in results:
            if result.path not in seen_paths or result.score > seen_paths[result.path].score:
                seen_paths[result.path] = result

        # Sort by score and limit
        final_results = sorted(seen_paths.values(), key=lambda x: x.score, reverse=True)[:limit]

        return [r.to_dict() for r in final_results]

    async def fetch(self, path: str) -> Dict[str, Any]:
        """
        Fetch full note content.

        Implements IBrainService.fetch protocol.

        Args:
            path: Note path in vault.

        Returns:
            Dictionary with path, title, content, tags, links, etc.

        Raises:
            FileNotFoundError: If the note doesn't exist.
        """
        # Get content from vault
        content = await self._vault.read_note(path)

        # Get metadata from brain index
        meta = await self._brain.get_note_meta(path)

        if meta:
            result = FetchResult(
                path=path,
                title=meta.title,
                content=content,
                tags=meta.tags,
                outlinks=meta.outlinks,
                backlinks=meta.backlinks,
                modified_at=meta.modified_at,
                word_count=meta.word_count,
                frontmatter=meta.frontmatter,
            )
        else:
            # Note not indexed, extract basic info
            title = path.split("/")[-1].replace(".md", "")
            result = FetchResult(
                path=path,
                title=title,
                content=content,
                word_count=len(content.split()),
            )

        return result.to_dict()

    # ========== Search Implementations ==========

    async def _semantic_search(
        self,
        query: str,
        limit: int,
        min_score: float,
    ) -> List[SearchResult]:
        """
        Semantic search using embeddings.

        Args:
            query: Search query.
            limit: Maximum results.
            min_score: Minimum similarity score.

        Returns:
            List of SearchResult objects.
        """
        # Generate query embedding
        query_embedding = await self._embedding.embed(query)

        # Get all chunks with embeddings
        chunks_with_meta = await self._brain.get_all_chunks_with_embeddings(limit=1000)

        if not chunks_with_meta:
            logger.warning("No chunks with embeddings found in brain index")
            return []

        # Calculate similarities
        scored_results = []
        for chunk, meta in chunks_with_meta:
            if not chunk.embedding:
                continue

            similarity = self._cosine_similarity(query_embedding, chunk.embedding)

            if similarity >= min_score:
                scored_results.append(SearchResult(
                    path=chunk.path,
                    title=meta.title,
                    score=similarity,
                    chunk_text=chunk.text,
                    chunk_index=chunk.chunk_index,
                    heading=chunk.heading,
                    match_type="semantic",
                    tags=meta.tags,
                    snippet=self._generate_snippet(chunk.text, query),
                ))

        # Sort by similarity
        scored_results.sort(key=lambda x: x.score, reverse=True)

        return scored_results[:limit]

    async def _keyword_search(
        self,
        query: str,
        limit: int,
        min_score: float,
    ) -> List[SearchResult]:
        """
        Keyword search using TF-IDF style scoring.

        Args:
            query: Search query.
            limit: Maximum results.
            min_score: Minimum relevance score.

        Returns:
            List of SearchResult objects.
        """
        # Build keyword index if needed
        if not self._keyword_index_built:
            await self._build_keyword_index()

        # Tokenize query
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        # Find matching chunks
        chunk_scores: Dict[Tuple[str, int], float] = {}  # (path, chunk_index) -> score
        chunk_data: Dict[Tuple[str, int], NoteChunkItem] = {}

        for term in query_terms:
            if term in self._keyword_index:
                for path, chunk_index in self._keyword_index[term]:
                    key = (path, chunk_index)
                    chunk_scores[key] = chunk_scores.get(key, 0) + 1

        if not chunk_scores:
            return []

        # Normalize scores to 0-1 range
        max_score = max(chunk_scores.values())
        for key in chunk_scores:
            chunk_scores[key] = chunk_scores[key] / max_score

        # Get chunk data and metadata
        results = []
        for (path, chunk_index), score in sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True):
            if score < min_score:
                continue

            chunk = await self._brain.get_chunk(path, chunk_index)
            if not chunk:
                continue

            meta = await self._brain.get_note_meta(path)

            results.append(SearchResult(
                path=path,
                title=meta.title if meta else path,
                score=score,
                chunk_text=chunk.text,
                chunk_index=chunk_index,
                heading=chunk.heading,
                match_type="keyword",
                tags=meta.tags if meta else [],
                snippet=self._generate_snippet(chunk.text, query),
            ))

            if len(results) >= limit:
                break

        return results

    async def _hybrid_search(
        self,
        query: str,
        limit: int,
        min_score: float,
    ) -> List[SearchResult]:
        """
        Hybrid search combining semantic and keyword.

        Args:
            query: Search query.
            limit: Maximum results.
            min_score: Minimum relevance score.

        Returns:
            List of SearchResult objects.
        """
        # Run both searches
        semantic_results = await self._semantic_search(query, limit, min_score * 0.5)
        keyword_results = await self._keyword_search(query, limit, min_score * 0.5)

        # Combine scores
        combined: Dict[Tuple[str, int], SearchResult] = {}

        for result in semantic_results:
            key = (result.path, result.chunk_index)
            combined[key] = SearchResult(
                path=result.path,
                title=result.title,
                score=result.score * self._semantic_weight,
                chunk_text=result.chunk_text,
                chunk_index=result.chunk_index,
                heading=result.heading,
                match_type="hybrid",
                tags=result.tags,
                snippet=result.snippet,
            )

        for result in keyword_results:
            key = (result.path, result.chunk_index)
            if key in combined:
                combined[key].score += result.score * self._keyword_weight
            else:
                combined[key] = SearchResult(
                    path=result.path,
                    title=result.title,
                    score=result.score * self._keyword_weight,
                    chunk_text=result.chunk_text,
                    chunk_index=result.chunk_index,
                    heading=result.heading,
                    match_type="hybrid",
                    tags=result.tags,
                    snippet=result.snippet,
                )

        # Filter by minimum score and sort
        results = [r for r in combined.values() if r.score >= min_score]
        results.sort(key=lambda x: x.score, reverse=True)

        return results[:limit]

    # ========== Indexing Operations ==========

    async def index_vault(
        self,
        force_reindex: bool = False,
        patterns: Optional[List[str]] = None,
    ) -> Dict[str, int]:
        """
        Index or re-index the vault.

        Args:
            force_reindex: If True, re-index all notes regardless of modification time.
            patterns: Optional list of glob patterns to limit indexing (e.g., ["projects/*"]).

        Returns:
            Dictionary with indexing statistics.
        """
        logger.info("Starting vault indexing...")

        # Get all notes in vault
        all_notes = await self._vault.list_notes()

        # Filter by patterns if specified
        if patterns:
            filtered = []
            for note in all_notes:
                for pattern in patterns:
                    if self._match_pattern(note, pattern):
                        filtered.append(note)
                        break
            all_notes = filtered

        stats = {
            "total": len(all_notes),
            "indexed": 0,
            "skipped": 0,
            "errors": 0,
        }

        for path in all_notes:
            try:
                await self._index_note(path, force_reindex)
                stats["indexed"] += 1
            except Exception as e:
                logger.error(f"Error indexing {path}: {e}")
                stats["errors"] += 1

        # Rebuild keyword index
        await self._build_keyword_index()

        # Update backlinks
        await self._update_backlinks()

        logger.info(f"Indexing complete: {stats}")
        return stats

    async def _index_note(
        self,
        path: str,
        force: bool = False,
    ) -> Optional[NoteMetaItem]:
        """
        Index a single note.

        Args:
            path: Note path.
            force: Force re-index even if not modified.

        Returns:
            NoteMetaItem if indexed, None if skipped.
        """
        # Get note metadata from vault
        try:
            metadata = await self._vault.get_note_metadata(path)
        except Exception:
            metadata = None

        modified_at = metadata.get("modified_at") if metadata else datetime.now().isoformat()

        # Check if re-indexing is needed
        if not force:
            needs_reindex = await self._brain.needs_reindex(path, modified_at)
            if not needs_reindex:
                logger.debug(f"Skipping {path} (not modified)")
                return None

        # Read content and metadata
        content = await self._vault.read_note(path)

        # Parse frontmatter
        frontmatter, content_without_front = self._parse_frontmatter(content)

        # Extract title
        title = frontmatter.get("title") or self._extract_title(path, content)

        # Extract tags
        tags = frontmatter.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        # Extract outlinks
        outlinks = self._extract_links(content)

        # Extract aliases
        aliases = frontmatter.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [a.strip() for a in aliases.split(",")]

        # Generate embeddings for chunks
        chunks = self._brain._chunk_content(content_without_front, path)
        chunk_texts = [c.text for c in chunks]
        embeddings = await self._embedding.embed_batch(chunk_texts) if chunk_texts else []

        # Index the note
        meta = await self._brain.index_note(
            path=path,
            title=title,
            content=content_without_front,
            modified_at=modified_at,
            tags=tags,
            outlinks=outlinks,
            aliases=aliases,
            frontmatter=frontmatter,
            chunk_embeddings=embeddings,
        )

        logger.debug(f"Indexed {path}: {len(chunks)} chunks")
        return meta

    async def reindex_note(self, path: str) -> Optional[NoteMetaItem]:
        """
        Force re-index a specific note.

        Args:
            path: Note path.

        Returns:
            NoteMetaItem if indexed.
        """
        result = await self._index_note(path, force=True)

        # Invalidate keyword index
        self._keyword_index_built = False

        return result

    async def delete_from_index(self, path: str) -> bool:
        """
        Remove a note from the index.

        Args:
            path: Note path.

        Returns:
            True if deleted.
        """
        result = await self._brain.delete_note(path)

        # Invalidate keyword index
        self._keyword_index_built = False

        return result

    # ========== Backlink Operations ==========

    async def _update_backlinks(self) -> None:
        """Update backlinks for all indexed notes."""
        # Get all notes
        all_notes = await self._brain.list_all_notes()

        # Build backlink map: target_path -> [source_paths]
        backlinks: Dict[str, List[str]] = {}

        for note in all_notes:
            for outlink in note.outlinks:
                if outlink not in backlinks:
                    backlinks[outlink] = []
                backlinks[outlink].append(note.path)

        # Update each note with its backlinks
        for path, sources in backlinks.items():
            await self._brain.update_note_meta(path, backlinks=sources)

        logger.info(f"Updated backlinks for {len(backlinks)} notes")

    async def get_backlinks(self, path: str) -> List[str]:
        """
        Get notes that link to the given path.

        Args:
            path: Note path.

        Returns:
            List of paths that link to this note.
        """
        meta = await self._brain.get_note_meta(path)
        return meta.backlinks if meta else []

    async def get_outlinks(self, path: str) -> List[str]:
        """
        Get notes that the given path links to.

        Args:
            path: Note path.

        Returns:
            List of paths this note links to.
        """
        meta = await self._brain.get_note_meta(path)
        return meta.outlinks if meta else []

    # ========== Keyword Index ==========

    async def _build_keyword_index(self) -> None:
        """Build in-memory keyword index for fast lookups."""
        logger.info("Building keyword index...")

        self._keyword_index = {}

        # Get all notes
        all_notes = await self._brain.list_all_notes()

        for note in all_notes:
            # Get chunks for this note
            chunks = await self._brain.get_note_chunks(note.path, include_embeddings=False)

            for chunk in chunks:
                terms = self._tokenize(chunk.text)
                for term in terms:
                    if term not in self._keyword_index:
                        self._keyword_index[term] = []
                    self._keyword_index[term].append((note.path, chunk.chunk_index))

        self._keyword_index_built = True
        logger.info(f"Keyword index built: {len(self._keyword_index)} unique terms")

    # ========== Utility Methods ==========

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into searchable terms."""
        # Lowercase and extract words
        text = text.lower()
        words = re.findall(r'\b[a-z]{2,}\b', text)

        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
            'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them',
            'their', 'we', 'us', 'our', 'you', 'your', 'he', 'she', 'him', 'her',
        }

        return [w for w in words if w not in stop_words]

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(v1) != len(v2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _generate_snippet(
        self,
        text: str,
        query: str,
        max_length: int = 200,
    ) -> str:
        """Generate a snippet with query terms highlighted."""
        query_terms = set(self._tokenize(query))

        # Find best sentence containing query terms
        sentences = re.split(r'[.!?]\s+', text)

        best_sentence = None
        best_score = 0

        for sentence in sentences:
            sentence_terms = set(self._tokenize(sentence))
            overlap = len(query_terms & sentence_terms)
            if overlap > best_score:
                best_score = overlap
                best_sentence = sentence

        if best_sentence:
            snippet = best_sentence[:max_length]
            if len(best_sentence) > max_length:
                snippet += "..."
            return snippet

        # Fallback to first part of text
        return text[:max_length] + ("..." if len(text) > max_length else "")

    def _extract_title(self, path: str, content: str) -> str:
        """Extract title from note content or path."""
        # Try to find H1 heading
        h1_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if h1_match:
            return h1_match.group(1).strip()

        # Fall back to filename
        return path.split("/")[-1].replace(".md", "").replace("-", " ").title()

    def _extract_links(self, content: str) -> List[str]:
        """Extract wiki-style links from content."""
        # Match [[link]] or [[link|display]]
        links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)
        return list(set(links))

    def _parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from markdown content."""
        if not content.startswith("---"):
            return {}, content

        # Find closing ---
        end_match = re.search(r'\n---\s*\n', content[3:])
        if not end_match:
            return {}, content

        frontmatter_text = content[3:end_match.start() + 3]
        remaining_content = content[end_match.end() + 3:]

        try:
            import yaml
            frontmatter = yaml.safe_load(frontmatter_text) or {}
        except Exception:
            frontmatter = {}

        return frontmatter, remaining_content

    def _match_pattern(self, path: str, pattern: str) -> bool:
        """Simple glob-style pattern matching."""
        import fnmatch
        return fnmatch.fnmatch(path, pattern)

    async def get_stats(self) -> Dict[str, Any]:
        """Get brain service statistics."""
        brain_stats = await self._brain.get_index_stats()
        cache_stats = await self._embedding.get_cache_stats() if hasattr(self._embedding, 'get_cache_stats') else None

        return {
            "brain_index": brain_stats,
            "embedding_cache": cache_stats,
            "keyword_index_size": len(self._keyword_index) if self._keyword_index_built else 0,
        }


# Factory function for DI container
def create_brain_service(
    vault: IVaultService,
    brain_adapter: TroiseBrainAdapter,
    embedding_service: IEmbeddingService,
) -> BrainService:
    """
    Create a BrainService instance.

    Factory function for the DI container.

    Args:
        vault: Vault service for reading notes.
        brain_adapter: DynamoDB adapter for brain index.
        embedding_service: Service for generating embeddings.

    Returns:
        Configured BrainService instance.
    """
    return BrainService(
        vault=vault,
        brain_adapter=brain_adapter,
        embedding_service=embedding_service,
    )
