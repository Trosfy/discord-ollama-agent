"""Obsidian Vault Service - IVaultService implementation.

Provides async file operations for the Obsidian vault:
- Read/write markdown notes
- Read/write YAML files (preferences, learned context)
- List notes in directories
- Path validation and security

The vault path is configured via TROISE_VAULT_PATH environment variable.
"""
import asyncio
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import yaml

logger = logging.getLogger(__name__)


class VaultServiceError(Exception):
    """Base exception for vault service errors."""
    pass


class VaultNotFoundError(VaultServiceError):
    """Raised when vault path doesn't exist."""
    pass


class NoteNotFoundError(VaultServiceError):
    """Raised when a note doesn't exist."""
    pass


class InvalidPathError(VaultServiceError):
    """Raised when a path is invalid or escapes vault."""
    pass


class VaultService:
    """
    Async file operations for Obsidian vault.

    Implements IVaultService interface for reading and writing
    markdown notes and YAML configuration files.

    Security:
    - All paths are validated to prevent directory traversal
    - Paths are resolved relative to vault root
    - Symlinks are not followed outside vault

    Example:
        vault = VaultService("/home/user/obsidian-vault")
        content = await vault.read_note("projects/my-project.md")
        await vault.write_note("inbox/new-idea.md", "# New Idea\\n...")
    """

    # File patterns to ignore when listing notes
    IGNORE_PATTERNS = [
        r"^\.",           # Hidden files
        r"^_",            # Underscore prefix (common for templates)
        r"\.obsidian$",   # Obsidian config folder
        r"\.git$",        # Git folder
        r"\.trash$",      # Obsidian trash
    ]

    def __init__(
        self,
        vault_path: Optional[str] = None,
        create_missing_dirs: bool = True,
    ):
        """
        Initialize the vault service.

        Args:
            vault_path: Path to Obsidian vault. Defaults to TROISE_VAULT_PATH env var.
            create_missing_dirs: Whether to create directories when writing notes.

        Raises:
            VaultNotFoundError: If vault path doesn't exist.
        """
        self._vault_path = Path(
            vault_path or os.getenv("TROISE_VAULT_PATH", "/home/trosfy/obsidian-vault")
        ).resolve()

        if not self._vault_path.exists():
            raise VaultNotFoundError(f"Vault path does not exist: {self._vault_path}")

        if not self._vault_path.is_dir():
            raise VaultNotFoundError(f"Vault path is not a directory: {self._vault_path}")

        self._create_missing_dirs = create_missing_dirs
        self._ignore_patterns = [re.compile(p) for p in self.IGNORE_PATTERNS]

        logger.info(f"VaultService initialized with vault: {self._vault_path}")

    @property
    def vault_path(self) -> Path:
        """Get the vault root path."""
        return self._vault_path

    def _resolve_path(self, relative_path: str) -> Path:
        """
        Resolve a relative path to an absolute path within the vault.

        Validates that the resolved path is within the vault to prevent
        directory traversal attacks.

        Args:
            relative_path: Path relative to vault root.

        Returns:
            Resolved absolute path.

        Raises:
            InvalidPathError: If path escapes vault or is invalid.
        """
        # Normalize the path (remove .., etc.)
        clean_path = Path(relative_path)

        # Don't allow absolute paths
        if clean_path.is_absolute():
            raise InvalidPathError(f"Absolute paths not allowed: {relative_path}")

        # Resolve the full path
        full_path = (self._vault_path / clean_path).resolve()

        # Verify it's still within the vault
        try:
            full_path.relative_to(self._vault_path)
        except ValueError:
            raise InvalidPathError(f"Path escapes vault: {relative_path}")

        return full_path

    def _is_ignored(self, name: str) -> bool:
        """Check if a file/directory name should be ignored."""
        return any(pattern.search(name) for pattern in self._ignore_patterns)

    async def read_note(self, path: str) -> str:
        """
        Read a markdown note from the vault.

        Args:
            path: Path to the note relative to vault root (e.g., "projects/my-project.md").

        Returns:
            Note content as string.

        Raises:
            NoteNotFoundError: If note doesn't exist.
            InvalidPathError: If path is invalid.
        """
        full_path = self._resolve_path(path)

        if not full_path.exists():
            raise NoteNotFoundError(f"Note not found: {path}")

        if not full_path.is_file():
            raise InvalidPathError(f"Path is not a file: {path}")

        async with aiofiles.open(full_path, mode='r', encoding='utf-8') as f:
            content = await f.read()

        logger.debug(f"Read note: {path} ({len(content)} chars)")
        return content

    async def write_note(self, path: str, content: str) -> None:
        """
        Write a markdown note to the vault.

        Creates parent directories if they don't exist (when create_missing_dirs=True).

        Args:
            path: Path to the note relative to vault root.
            content: Note content to write.

        Raises:
            InvalidPathError: If path is invalid.
            VaultServiceError: If write fails.
        """
        full_path = self._resolve_path(path)

        # Ensure parent directory exists
        if self._create_missing_dirs:
            full_path.parent.mkdir(parents=True, exist_ok=True)
        elif not full_path.parent.exists():
            raise VaultServiceError(f"Parent directory doesn't exist: {full_path.parent}")

        async with aiofiles.open(full_path, mode='w', encoding='utf-8') as f:
            await f.write(content)

        logger.info(f"Wrote note: {path} ({len(content)} chars)")

    async def read_yaml(self, path: str) -> Dict[str, Any]:
        """
        Read a YAML file from the vault.

        Args:
            path: Path to YAML file relative to vault root.

        Returns:
            Parsed YAML as dictionary.

        Raises:
            NoteNotFoundError: If file doesn't exist.
            VaultServiceError: If YAML parsing fails.
        """
        full_path = self._resolve_path(path)

        if not full_path.exists():
            raise NoteNotFoundError(f"YAML file not found: {path}")

        async with aiofiles.open(full_path, mode='r', encoding='utf-8') as f:
            content = await f.read()

        try:
            data = yaml.safe_load(content)
            if data is None:
                data = {}
            logger.debug(f"Read YAML: {path}")
            return data
        except yaml.YAMLError as e:
            raise VaultServiceError(f"Failed to parse YAML {path}: {e}")

    async def write_yaml(self, path: str, data: Dict[str, Any]) -> None:
        """
        Write a YAML file to the vault.

        Uses safe_dump with default_flow_style=False for readable output.

        Args:
            path: Path to YAML file relative to vault root.
            data: Dictionary to write as YAML.

        Raises:
            InvalidPathError: If path is invalid.
            VaultServiceError: If write fails.
        """
        full_path = self._resolve_path(path)

        # Ensure parent directory exists
        if self._create_missing_dirs:
            full_path.parent.mkdir(parents=True, exist_ok=True)
        elif not full_path.parent.exists():
            raise VaultServiceError(f"Parent directory doesn't exist: {full_path.parent}")

        try:
            yaml_content = yaml.safe_dump(
                data,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=120,
            )
        except yaml.YAMLError as e:
            raise VaultServiceError(f"Failed to serialize YAML: {e}")

        async with aiofiles.open(full_path, mode='w', encoding='utf-8') as f:
            await f.write(yaml_content)

        logger.info(f"Wrote YAML: {path}")

    async def list_notes(self, directory: Optional[str] = None) -> List[str]:
        """
        List all markdown notes in a directory.

        Args:
            directory: Directory relative to vault root. None for vault root.

        Returns:
            List of note paths relative to vault root.

        Raises:
            InvalidPathError: If directory is invalid.
            VaultServiceError: If directory doesn't exist.
        """
        if directory:
            dir_path = self._resolve_path(directory)
        else:
            dir_path = self._vault_path

        if not dir_path.exists():
            raise VaultServiceError(f"Directory not found: {directory or '/'}")

        if not dir_path.is_dir():
            raise InvalidPathError(f"Path is not a directory: {directory}")

        notes = []

        # Use asyncio.to_thread for directory walking (I/O bound)
        def _walk_sync():
            result = []
            for item in dir_path.rglob("*.md"):
                # Skip ignored patterns
                if any(self._is_ignored(part) for part in item.parts):
                    continue

                # Get relative path from vault root
                rel_path = str(item.relative_to(self._vault_path))
                result.append(rel_path)
            return sorted(result)

        notes = await asyncio.to_thread(_walk_sync)
        logger.debug(f"Listed {len(notes)} notes in {directory or '/'}")
        return notes

    async def exists(self, path: str) -> bool:
        """
        Check if a path exists in the vault.

        Args:
            path: Path relative to vault root.

        Returns:
            True if path exists.
        """
        try:
            full_path = self._resolve_path(path)
            return full_path.exists()
        except InvalidPathError:
            return False

    async def delete_note(self, path: str) -> bool:
        """
        Delete a note from the vault.

        Args:
            path: Path to note relative to vault root.

        Returns:
            True if deleted, False if didn't exist.

        Raises:
            InvalidPathError: If path is invalid.
        """
        full_path = self._resolve_path(path)

        if not full_path.exists():
            return False

        if not full_path.is_file():
            raise InvalidPathError(f"Path is not a file: {path}")

        # Use asyncio.to_thread for file deletion
        await asyncio.to_thread(full_path.unlink)
        logger.info(f"Deleted note: {path}")
        return True

    async def get_note_metadata(self, path: str) -> Dict[str, Any]:
        """
        Get metadata about a note.

        Args:
            path: Path to note relative to vault root.

        Returns:
            Dictionary with metadata (size, modified, created, etc.).

        Raises:
            NoteNotFoundError: If note doesn't exist.
        """
        full_path = self._resolve_path(path)

        if not full_path.exists():
            raise NoteNotFoundError(f"Note not found: {path}")

        stat = await asyncio.to_thread(full_path.stat)

        return {
            "path": path,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "is_file": full_path.is_file(),
        }

    async def search_notes(
        self,
        query: str,
        directory: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Simple text search across notes.

        This is a basic implementation - for full hybrid search,
        use the BrainService which combines keyword and semantic search.

        Args:
            query: Text to search for.
            directory: Directory to search in (None for whole vault).
            limit: Maximum results to return.

        Returns:
            List of matching notes with path and snippet.
        """
        notes = await self.list_notes(directory)
        results = []
        query_lower = query.lower()

        for note_path in notes:
            if len(results) >= limit:
                break

            try:
                content = await self.read_note(note_path)
                content_lower = content.lower()

                if query_lower in content_lower:
                    # Find the snippet around the match
                    idx = content_lower.find(query_lower)
                    start = max(0, idx - 50)
                    end = min(len(content), idx + len(query) + 50)
                    snippet = content[start:end].strip()

                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(content):
                        snippet = snippet + "..."

                    results.append({
                        "path": note_path,
                        "snippet": snippet,
                        "match_position": idx,
                    })

            except Exception as e:
                logger.warning(f"Error reading note {note_path}: {e}")
                continue

        return results

    async def parse_frontmatter(self, path: str) -> tuple[Dict[str, Any], str]:
        """
        Parse YAML frontmatter from a markdown note.

        Args:
            path: Path to note.

        Returns:
            Tuple of (frontmatter dict, content without frontmatter).

        Raises:
            NoteNotFoundError: If note doesn't exist.
        """
        content = await self.read_note(path)

        # Check for frontmatter delimiter
        if not content.startswith("---"):
            return {}, content

        # Find the closing delimiter
        lines = content.split("\n")
        end_idx = None

        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                end_idx = i
                break

        if end_idx is None:
            return {}, content

        # Parse frontmatter
        frontmatter_text = "\n".join(lines[1:end_idx])
        try:
            frontmatter = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError:
            frontmatter = {}

        # Get content after frontmatter
        body = "\n".join(lines[end_idx + 1:]).lstrip()

        return frontmatter, body

    async def write_with_frontmatter(
        self,
        path: str,
        frontmatter: Dict[str, Any],
        content: str,
    ) -> None:
        """
        Write a note with YAML frontmatter.

        Args:
            path: Path to note.
            frontmatter: Dictionary to write as frontmatter.
            content: Markdown content.
        """
        fm_yaml = yaml.safe_dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).strip()

        full_content = f"---\n{fm_yaml}\n---\n\n{content}"
        await self.write_note(path, full_content)
