"""File Watcher for Obsidian Vault using inotify.

Watches the Obsidian vault for file changes and triggers callbacks
for index updates, cache invalidation, and synchronization.

Uses watchfiles (based on notify-rs) for efficient cross-platform
file system monitoring.

Events:
- Note created/modified: Re-index in DynamoDB brain table
- Note deleted: Remove from brain table index
- ai-preferences.yaml changed: Invalidate preferences cache
- ai-learned.yaml changed: Invalidate learned context cache
"""
import asyncio
import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
from enum import Enum
from dataclasses import dataclass

try:
    from watchfiles import awatch, Change
    WATCHFILES_AVAILABLE = True
except ImportError:
    WATCHFILES_AVAILABLE = False
    Change = None

logger = logging.getLogger(__name__)


class FileChangeType(Enum):
    """Type of file change event."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class FileEvent:
    """Represents a file change event."""
    path: Path
    change_type: FileChangeType
    relative_path: str  # Path relative to vault root

    def is_markdown(self) -> bool:
        """Check if the changed file is a markdown file."""
        return self.path.suffix.lower() == ".md"

    def is_yaml(self) -> bool:
        """Check if the changed file is a YAML file."""
        return self.path.suffix.lower() in (".yaml", ".yml")

    def is_preferences(self) -> bool:
        """Check if this is the ai-preferences.yaml file."""
        return "ai-preferences" in self.path.name.lower()

    def is_learned(self) -> bool:
        """Check if this is the ai-learned.yaml file."""
        return "ai-learned" in self.path.name.lower()

    def is_ignored(self) -> bool:
        """Check if this file should be ignored."""
        name = self.path.name
        parts = self.path.parts
        return (
            name.startswith(".") or
            name.startswith("_") or
            ".obsidian" in parts or
            ".git" in parts or
            ".trash" in parts
        )


# Type alias for event handlers
EventHandler = Callable[[FileEvent], None]
AsyncEventHandler = Callable[[FileEvent], "asyncio.coroutine"]


class VaultFileWatcher:
    """
    Async file system watcher for Obsidian vault.

    Uses watchfiles for efficient file monitoring with debouncing.
    Triggers callbacks when notes are created, modified, or deleted.

    Example:
        watcher = VaultFileWatcher("/path/to/vault")

        async def on_note_changed(event: FileEvent):
            print(f"Note changed: {event.relative_path}")

        watcher.on_note_change(on_note_changed)
        await watcher.start()

        # Later...
        await watcher.stop()
    """

    # Default patterns to ignore
    IGNORE_PATTERNS: Set[str] = {
        ".obsidian",
        ".git",
        ".trash",
        ".DS_Store",
        "node_modules",
    }

    def __init__(
        self,
        vault_path: str,
        debounce_ms: int = 200,
    ):
        """
        Initialize the file watcher.

        Args:
            vault_path: Path to the Obsidian vault.
            debounce_ms: Debounce delay in milliseconds.

        Raises:
            RuntimeError: If watchfiles is not installed.
        """
        if not WATCHFILES_AVAILABLE:
            raise RuntimeError(
                "watchfiles not installed. Install with: pip install watchfiles"
            )

        self._vault_path = Path(vault_path).resolve()
        self._debounce_ms = debounce_ms
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Event handlers
        self._note_handlers: List[AsyncEventHandler] = []
        self._config_handlers: List[AsyncEventHandler] = []
        self._any_handlers: List[AsyncEventHandler] = []

        # Stats
        self._events_processed = 0
        self._events_ignored = 0

        if not self._vault_path.exists():
            raise ValueError(f"Vault path does not exist: {self._vault_path}")

        logger.info(f"VaultFileWatcher initialized for: {self._vault_path}")

    @property
    def vault_path(self) -> Path:
        """Get the vault root path."""
        return self._vault_path

    @property
    def is_running(self) -> bool:
        """Check if the watcher is currently running."""
        return self._running

    @property
    def stats(self) -> Dict[str, int]:
        """Get watcher statistics."""
        return {
            "events_processed": self._events_processed,
            "events_ignored": self._events_ignored,
        }

    def on_note_change(self, handler: AsyncEventHandler) -> None:
        """
        Register a handler for note changes (markdown files).

        Args:
            handler: Async function(FileEvent) to call on note changes.
        """
        self._note_handlers.append(handler)

    def on_config_change(self, handler: AsyncEventHandler) -> None:
        """
        Register a handler for config changes (ai-*.yaml files).

        Args:
            handler: Async function(FileEvent) to call on config changes.
        """
        self._config_handlers.append(handler)

    def on_any_change(self, handler: AsyncEventHandler) -> None:
        """
        Register a handler for any file changes.

        Args:
            handler: Async function(FileEvent) to call on any changes.
        """
        self._any_handlers.append(handler)

    def _should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored."""
        for part in path.parts:
            if part in self.IGNORE_PATTERNS:
                return True
            if part.startswith("."):
                return True
        return False

    def _make_event(self, change: "Change", path_str: str) -> Optional[FileEvent]:
        """
        Create a FileEvent from a watchfiles change.

        Args:
            change: The Change enum from watchfiles.
            path_str: The path string from watchfiles.

        Returns:
            FileEvent or None if should be ignored.
        """
        path = Path(path_str)

        # Determine change type
        if change == Change.added:
            change_type = FileChangeType.CREATED
        elif change == Change.modified:
            change_type = FileChangeType.MODIFIED
        elif change == Change.deleted:
            change_type = FileChangeType.DELETED
        else:
            return None

        # Get relative path
        try:
            relative_path = str(path.relative_to(self._vault_path))
        except ValueError:
            # Path is not relative to vault (shouldn't happen)
            return None

        event = FileEvent(
            path=path,
            change_type=change_type,
            relative_path=relative_path,
        )

        if event.is_ignored() or self._should_ignore(path):
            self._events_ignored += 1
            return None

        return event

    async def _dispatch_event(self, event: FileEvent) -> None:
        """
        Dispatch an event to registered handlers.

        Args:
            event: The file event to dispatch.
        """
        try:
            # Call specific handlers
            if event.is_markdown():
                for handler in self._note_handlers:
                    await handler(event)

            if event.is_preferences() or event.is_learned():
                for handler in self._config_handlers:
                    await handler(event)

            # Call catch-all handlers
            for handler in self._any_handlers:
                await handler(event)

            self._events_processed += 1

        except Exception as e:
            logger.error(f"Error dispatching event for {event.relative_path}: {e}")

    async def _watch_loop(self) -> None:
        """
        Main watch loop using watchfiles.

        Runs until stop() is called.
        """
        logger.info(f"Starting file watcher for {self._vault_path}")

        try:
            async for changes in awatch(
                self._vault_path,
                debounce=self._debounce_ms,
                recursive=True,
            ):
                if not self._running:
                    break

                for change, path_str in changes:
                    event = self._make_event(change, path_str)
                    if event:
                        await self._dispatch_event(event)

        except asyncio.CancelledError:
            logger.info("File watcher cancelled")
        except Exception as e:
            logger.error(f"File watcher error: {e}")
            raise

        logger.info("File watcher stopped")

    async def start(self) -> None:
        """
        Start watching the vault.

        Runs in the background until stop() is called.
        """
        if self._running:
            logger.warning("File watcher already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._watch_loop())
        logger.info("File watcher started")

    async def stop(self) -> None:
        """Stop watching the vault."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info(
            f"File watcher stopped. "
            f"Processed: {self._events_processed}, Ignored: {self._events_ignored}"
        )

    async def __aenter__(self) -> "VaultFileWatcher":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()


def create_vault_watcher(vault_path: str) -> VaultFileWatcher:
    """
    Factory function to create a vault file watcher.

    Args:
        vault_path: Path to the Obsidian vault.

    Returns:
        Configured VaultFileWatcher instance.
    """
    return VaultFileWatcher(vault_path)
