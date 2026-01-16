"""DynamoDB adapter for troise_brain table.

Handles note metadata and chunks for the brain search index.
Provides storage for semantic search over Obsidian vault notes.

Table Design:
    PK patterns:
    - NOTE#{path_hash} - Note identifier (MD5 of relative path)

    SK patterns:
    - META - Note metadata (title, tags, links, modified_at)
    - CHUNK#{chunk_index:04d} - Individual text chunks with embeddings
"""
import hashlib
import logging
import struct
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from boto3.dynamodb.conditions import Key

from .base import DynamoDBClient

logger = logging.getLogger(__name__)

TABLE_NAME = "troise_brain"

# Chunk configuration
DEFAULT_CHUNK_SIZE = 512  # Characters per chunk
CHUNK_OVERLAP = 100  # Characters of overlap between chunks


def path_to_hash(path: str) -> str:
    """Convert a note path to MD5 hash for consistent partition keys."""
    return hashlib.md5(path.encode('utf-8')).hexdigest()


def embedding_to_binary(embedding: List[float]) -> bytes:
    """Convert embedding list to binary format for storage."""
    return struct.pack(f'{len(embedding)}f', *embedding)


def binary_to_embedding(data: bytes) -> List[float]:
    """Convert binary data back to embedding list."""
    count = len(data) // 4  # 4 bytes per float
    return list(struct.unpack(f'{count}f', data))


@dataclass
class NoteMetaItem:
    """Note metadata item."""
    path: str  # Relative path in vault
    title: str
    folder: str  # Parent folder
    modified_at: str  # ISO8601
    indexed_at: str  # ISO8601 - when we last indexed it
    word_count: int = 0
    chunk_count: int = 0
    tags: List[str] = field(default_factory=list)
    outlinks: List[str] = field(default_factory=list)  # Links to other notes
    backlinks: List[str] = field(default_factory=list)  # Notes linking to this
    aliases: List[str] = field(default_factory=list)
    frontmatter: Dict[str, Any] = field(default_factory=dict)

    @property
    def path_hash(self) -> str:
        return path_to_hash(self.path)

    @property
    def pk(self) -> str:
        return f"NOTE#{self.path_hash}"

    @property
    def sk(self) -> str:
        return "META"

    def to_dynamo_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            'PK': self.pk,
            'SK': self.sk,
            'entity_type': 'NOTE_META',
            'path': self.path,
            'path_hash': self.path_hash,
            'note_path': self.path,  # For GSI
            'title': self.title,
            'folder': self.folder,
            'modified_at': self.modified_at,
            'indexed_at': self.indexed_at,
            'word_count': self.word_count,
            'chunk_count': self.chunk_count,
            'tags': self.tags,
            'outlinks': self.outlinks,
            'backlinks': self.backlinks,
            'aliases': self.aliases,
            'frontmatter': self.frontmatter,
        }

    @classmethod
    def from_dynamo_item(cls, item: Dict[str, Any]) -> "NoteMetaItem":
        """Create from DynamoDB item."""
        return cls(
            path=item['path'],
            title=item.get('title', ''),
            folder=item.get('folder', ''),
            modified_at=item.get('modified_at', ''),
            indexed_at=item.get('indexed_at', ''),
            word_count=item.get('word_count', 0),
            chunk_count=item.get('chunk_count', 0),
            tags=item.get('tags', []),
            outlinks=item.get('outlinks', []),
            backlinks=item.get('backlinks', []),
            aliases=item.get('aliases', []),
            frontmatter=item.get('frontmatter', {}),
        )


@dataclass
class NoteChunkItem:
    """Individual chunk of a note with embedding."""
    path: str  # Note path (for reference)
    chunk_index: int  # 0-indexed position
    text: str  # Chunk text content
    start_line: int  # Line number where chunk starts
    end_line: int  # Line number where chunk ends
    heading: Optional[str] = None  # Nearest heading above chunk
    embedding: Optional[List[float]] = None  # Vector embedding

    @property
    def path_hash(self) -> str:
        return path_to_hash(self.path)

    @property
    def pk(self) -> str:
        return f"NOTE#{self.path_hash}"

    @property
    def sk(self) -> str:
        return f"CHUNK#{self.chunk_index:04d}"

    @property
    def chunk_id(self) -> str:
        """Unique identifier for this chunk."""
        return f"{self.path_hash}:{self.chunk_index}"

    def to_dynamo_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            'PK': self.pk,
            'SK': self.sk,
            'entity_type': 'NOTE_CHUNK',
            'path': self.path,
            'path_hash': self.path_hash,
            'chunk_index': self.chunk_index,
            'text': self.text,
            'start_line': self.start_line,
            'end_line': self.end_line,
            'heading': self.heading,
        }
        if self.embedding:
            item['embedding'] = embedding_to_binary(self.embedding)
        return item

    @classmethod
    def from_dynamo_item(cls, item: Dict[str, Any]) -> "NoteChunkItem":
        """Create from DynamoDB item."""
        embedding = None
        if 'embedding' in item and item['embedding']:
            embedding_data = item['embedding']
            if isinstance(embedding_data, bytes):
                embedding = binary_to_embedding(embedding_data)
            elif hasattr(embedding_data, 'value'):
                # boto3 Binary type
                embedding = binary_to_embedding(embedding_data.value)

        return cls(
            path=item['path'],
            chunk_index=item.get('chunk_index', 0),
            text=item.get('text', ''),
            start_line=item.get('start_line', 0),
            end_line=item.get('end_line', 0),
            heading=item.get('heading'),
            embedding=embedding,
        )


@dataclass
class SearchResult:
    """Result from a brain search."""
    path: str
    title: str
    chunk_text: str
    chunk_index: int
    heading: Optional[str]
    score: float  # Similarity score (0.0-1.0)
    tags: List[str] = field(default_factory=list)


class TroiseBrainAdapter:
    """
    Adapter for the troise_brain DynamoDB table.

    Provides methods for indexing Obsidian vault notes and
    retrieving them for semantic search.

    The brain table stores:
    - Note metadata (title, tags, links, modified date)
    - Note chunks with embeddings for semantic search

    Example:
        client = DynamoDBClient()
        adapter = TroiseBrainAdapter(client)

        # Index a note
        await adapter.index_note(
            path="projects/troise-ai/README.md",
            title="TROISE AI",
            content="...",
            tags=["project", "ai"],
            modified_at="2024-01-15T10:30:00",
            embeddings=[...]  # Pre-computed embeddings
        )

        # Search by path
        chunks = await adapter.get_note_chunks("projects/troise-ai/README.md")

        # Get all notes in a folder
        notes = await adapter.list_notes_in_folder("projects/")

        # Get notes by tag
        notes = await adapter.get_notes_by_tag("project")
    """

    def __init__(self, client: DynamoDBClient):
        """
        Initialize the adapter.

        Args:
            client: DynamoDBClient instance.
        """
        self._client = client
        self._table_name = TABLE_NAME

    # ========== Indexing Operations ==========

    async def index_note(
        self,
        path: str,
        title: str,
        content: str,
        modified_at: str,
        tags: Optional[List[str]] = None,
        outlinks: Optional[List[str]] = None,
        aliases: Optional[List[str]] = None,
        frontmatter: Optional[Dict[str, Any]] = None,
        chunk_embeddings: Optional[List[List[float]]] = None,
    ) -> NoteMetaItem:
        """
        Index a note with its content and optional embeddings.

        Args:
            path: Relative path in vault.
            title: Note title.
            content: Full note content.
            modified_at: Modification timestamp (ISO8601).
            tags: List of tags.
            outlinks: List of linked note paths.
            aliases: List of note aliases.
            frontmatter: Parsed frontmatter dict.
            chunk_embeddings: Pre-computed embeddings for each chunk.

        Returns:
            NoteMetaItem for the indexed note.
        """
        # Split content into chunks
        chunks = self._chunk_content(content, path)

        # Verify embedding count matches if provided
        if chunk_embeddings and len(chunk_embeddings) != len(chunks):
            logger.warning(
                f"Embedding count mismatch for {path}: "
                f"{len(chunk_embeddings)} embeddings for {len(chunks)} chunks"
            )

        # Get folder from path
        folder = "/".join(path.split("/")[:-1]) if "/" in path else ""

        # Count words
        word_count = len(content.split())

        # Create metadata
        now = datetime.now().isoformat()
        meta = NoteMetaItem(
            path=path,
            title=title,
            folder=folder,
            modified_at=modified_at,
            indexed_at=now,
            word_count=word_count,
            chunk_count=len(chunks),
            tags=tags or [],
            outlinks=outlinks or [],
            aliases=aliases or [],
            frontmatter=frontmatter or {},
        )

        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            # Delete existing chunks first (in case note was re-indexed)
            await self._delete_note_chunks(table, path)

            # Store metadata
            await table.put_item(Item=meta.to_dynamo_item())

            # Store chunks
            for i, chunk in enumerate(chunks):
                embedding = None
                if chunk_embeddings and i < len(chunk_embeddings):
                    embedding = chunk_embeddings[i]

                chunk.embedding = embedding
                await table.put_item(Item=chunk.to_dynamo_item())

        logger.info(f"Indexed note {path} with {len(chunks)} chunks")
        return meta

    async def update_note_meta(
        self,
        path: str,
        backlinks: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[NoteMetaItem]:
        """
        Update note metadata without re-indexing content.

        Args:
            path: Note path.
            backlinks: Updated backlinks list.
            tags: Updated tags list.

        Returns:
            Updated NoteMetaItem or None if not found.
        """
        meta = await self.get_note_meta(path)
        if not meta:
            return None

        update_expr_parts = ["#indexed_at = :indexed_at"]
        expr_names = {"#indexed_at": "indexed_at"}
        expr_values = {":indexed_at": datetime.now().isoformat()}

        if backlinks is not None:
            update_expr_parts.append("#backlinks = :backlinks")
            expr_names["#backlinks"] = "backlinks"
            expr_values[":backlinks"] = backlinks
            meta.backlinks = backlinks

        if tags is not None:
            update_expr_parts.append("#tags = :tags")
            expr_names["#tags"] = "tags"
            expr_values[":tags"] = tags
            meta.tags = tags

        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)
            await table.update_item(
                Key={'PK': meta.pk, 'SK': meta.sk},
                UpdateExpression="SET " + ", ".join(update_expr_parts),
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )

        return meta

    async def delete_note(self, path: str) -> bool:
        """
        Delete a note and all its chunks from the index.

        Args:
            path: Note path.

        Returns:
            True if deleted, False if not found.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            pk = f"NOTE#{path_to_hash(path)}"

            # Delete all items with this PK (meta + chunks)
            response = await table.query(
                KeyConditionExpression=Key('PK').eq(pk),
            )

            items = response.get('Items', [])
            if not items:
                return False

            for item in items:
                await table.delete_item(
                    Key={'PK': item['PK'], 'SK': item['SK']}
                )

            logger.info(f"Deleted note {path} ({len(items)} items)")
            return True

    async def _delete_note_chunks(self, table, path: str) -> int:
        """Delete all chunks for a note (internal helper)."""
        pk = f"NOTE#{path_to_hash(path)}"

        response = await table.query(
            KeyConditionExpression=Key('PK').eq(pk) &
                                   Key('SK').begins_with("CHUNK#"),
        )

        count = 0
        for item in response.get('Items', []):
            await table.delete_item(
                Key={'PK': item['PK'], 'SK': item['SK']}
            )
            count += 1

        return count

    # ========== Retrieval Operations ==========

    async def get_note_meta(self, path: str) -> Optional[NoteMetaItem]:
        """
        Get metadata for a note.

        Args:
            path: Note path.

        Returns:
            NoteMetaItem or None if not found.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            response = await table.get_item(
                Key={
                    'PK': f"NOTE#{path_to_hash(path)}",
                    'SK': "META",
                }
            )

            item = response.get('Item')
            if item:
                return NoteMetaItem.from_dynamo_item(item)
            return None

    async def get_note_chunks(
        self,
        path: str,
        include_embeddings: bool = True,
    ) -> List[NoteChunkItem]:
        """
        Get all chunks for a note.

        Args:
            path: Note path.
            include_embeddings: If False, skip loading embeddings.

        Returns:
            List of NoteChunkItem objects in order.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            pk = f"NOTE#{path_to_hash(path)}"

            # Build projection if we want to exclude embeddings
            params = {
                'KeyConditionExpression': Key('PK').eq(pk) &
                                          Key('SK').begins_with("CHUNK#"),
                'ScanIndexForward': True,  # Ascending order
            }

            if not include_embeddings:
                params['ProjectionExpression'] = (
                    "PK, SK, #path, chunk_index, #text, start_line, end_line, heading"
                )
                params['ExpressionAttributeNames'] = {
                    '#path': 'path',
                    '#text': 'text',
                }

            response = await table.query(**params)

            return [NoteChunkItem.from_dynamo_item(item) for item in response.get('Items', [])]

    async def get_chunk(
        self,
        path: str,
        chunk_index: int,
    ) -> Optional[NoteChunkItem]:
        """
        Get a specific chunk.

        Args:
            path: Note path.
            chunk_index: Chunk index.

        Returns:
            NoteChunkItem or None if not found.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            response = await table.get_item(
                Key={
                    'PK': f"NOTE#{path_to_hash(path)}",
                    'SK': f"CHUNK#{chunk_index:04d}",
                }
            )

            item = response.get('Item')
            if item:
                return NoteChunkItem.from_dynamo_item(item)
            return None

    async def list_all_notes(self) -> List[NoteMetaItem]:
        """
        List all indexed notes.

        Returns:
            List of NoteMetaItem objects.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            # Scan for all META items
            response = await table.scan(
                FilterExpression="#sk = :meta",
                ExpressionAttributeNames={"#sk": "SK"},
                ExpressionAttributeValues={":meta": "META"},
            )

            notes = [NoteMetaItem.from_dynamo_item(item) for item in response.get('Items', [])]

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = await table.scan(
                    FilterExpression="#sk = :meta",
                    ExpressionAttributeNames={"#sk": "SK"},
                    ExpressionAttributeValues={":meta": "META"},
                    ExclusiveStartKey=response['LastEvaluatedKey'],
                )
                notes.extend([
                    NoteMetaItem.from_dynamo_item(item)
                    for item in response.get('Items', [])
                ])

            return notes

    async def list_notes_in_folder(self, folder: str) -> List[NoteMetaItem]:
        """
        List notes in a specific folder.

        Args:
            folder: Folder path (e.g., "projects/troise-ai").

        Returns:
            List of NoteMetaItem objects.
        """
        all_notes = await self.list_all_notes()
        return [n for n in all_notes if n.folder == folder or n.folder.startswith(folder + "/")]

    async def get_notes_by_tag(self, tag: str) -> List[NoteMetaItem]:
        """
        Get all notes with a specific tag.

        Args:
            tag: Tag to search for.

        Returns:
            List of NoteMetaItem objects with the tag.
        """
        all_notes = await self.list_all_notes()
        return [n for n in all_notes if tag in n.tags]

    async def get_notes_modified_since(
        self,
        since: str,
    ) -> List[NoteMetaItem]:
        """
        Get notes modified since a given timestamp.

        Args:
            since: ISO8601 timestamp.

        Returns:
            List of NoteMetaItem objects modified after the timestamp.
        """
        all_notes = await self.list_all_notes()
        return [n for n in all_notes if n.modified_at > since]

    async def get_all_chunks_with_embeddings(
        self,
        limit: int = 1000,
    ) -> List[Tuple[NoteChunkItem, NoteMetaItem]]:
        """
        Get all chunks with their embeddings for vector search.

        Returns tuples of (chunk, note_meta) for building search index.

        Args:
            limit: Maximum number of chunks to return.

        Returns:
            List of (chunk, meta) tuples.
        """
        # Get all notes first for metadata
        all_notes = await self.list_all_notes()
        note_map = {n.path: n for n in all_notes}

        results = []

        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            # Scan for all CHUNK items
            response = await table.scan(
                FilterExpression="begins_with(#sk, :chunk_prefix)",
                ExpressionAttributeNames={"#sk": "SK"},
                ExpressionAttributeValues={":chunk_prefix": "CHUNK#"},
                Limit=limit,
            )

            for item in response.get('Items', []):
                chunk = NoteChunkItem.from_dynamo_item(item)
                if chunk.embedding and chunk.path in note_map:
                    results.append((chunk, note_map[chunk.path]))

        return results

    # ========== Chunking ==========

    def _chunk_content(
        self,
        content: str,
        path: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = CHUNK_OVERLAP,
    ) -> List[NoteChunkItem]:
        """
        Split content into overlapping chunks.

        Tries to split on paragraph/sentence boundaries when possible.

        Args:
            content: Full note content.
            path: Note path.
            chunk_size: Target chunk size in characters.
            overlap: Overlap between chunks.

        Returns:
            List of NoteChunkItem objects.
        """
        if not content.strip():
            return []

        lines = content.split('\n')
        chunks = []
        current_chunk = []
        current_size = 0
        current_start_line = 0
        current_heading = None

        for line_num, line in enumerate(lines):
            # Track headings
            if line.startswith('#'):
                heading_match = line.lstrip('#').strip()
                if heading_match:
                    current_heading = heading_match

            line_size = len(line) + 1  # +1 for newline

            # Check if adding this line would exceed chunk size
            if current_size + line_size > chunk_size and current_chunk:
                # Save current chunk
                chunk_text = '\n'.join(current_chunk)
                chunks.append(NoteChunkItem(
                    path=path,
                    chunk_index=len(chunks),
                    text=chunk_text,
                    start_line=current_start_line,
                    end_line=line_num - 1,
                    heading=current_heading,
                ))

                # Start new chunk with overlap
                overlap_lines = self._get_overlap_lines(current_chunk, overlap)
                current_chunk = overlap_lines
                current_size = sum(len(l) + 1 for l in current_chunk)
                current_start_line = line_num - len(overlap_lines)

            current_chunk.append(line)
            current_size += line_size

        # Save final chunk if not empty
        if current_chunk:
            chunk_text = '\n'.join(current_chunk).strip()
            if chunk_text:
                chunks.append(NoteChunkItem(
                    path=path,
                    chunk_index=len(chunks),
                    text=chunk_text,
                    start_line=current_start_line,
                    end_line=len(lines) - 1,
                    heading=current_heading,
                ))

        return chunks

    def _get_overlap_lines(
        self,
        lines: List[str],
        overlap_chars: int,
    ) -> List[str]:
        """Get lines from end that fit within overlap character count."""
        result = []
        char_count = 0

        for line in reversed(lines):
            line_size = len(line) + 1
            if char_count + line_size > overlap_chars and result:
                break
            result.insert(0, line)
            char_count += line_size

        return result

    # ========== Utility ==========

    async def get_index_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the brain index.

        Returns:
            Dict with index statistics.
        """
        notes = await self.list_all_notes()

        total_chunks = sum(n.chunk_count for n in notes)
        total_words = sum(n.word_count for n in notes)

        # Count unique tags
        all_tags = set()
        for n in notes:
            all_tags.update(n.tags)

        # Count notes by folder
        folders = {}
        for n in notes:
            folder = n.folder or "(root)"
            folders[folder] = folders.get(folder, 0) + 1

        return {
            "total_notes": len(notes),
            "total_chunks": total_chunks,
            "total_words": total_words,
            "unique_tags": len(all_tags),
            "folders": folders,
            "tags": list(all_tags),
        }

    async def needs_reindex(self, path: str, modified_at: str) -> bool:
        """
        Check if a note needs to be re-indexed.

        Args:
            path: Note path.
            modified_at: Current modification timestamp.

        Returns:
            True if the note needs re-indexing.
        """
        meta = await self.get_note_meta(path)
        if not meta:
            return True  # Not indexed yet

        return modified_at > meta.modified_at
