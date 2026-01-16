"""Obsidian vault adapters."""
from .vault_service import VaultService, NoteNotFoundError
from .preferences import PreferencesAdapter, UserPreferences
from .learned import LearnedContextAdapter, LearnedContext
from .file_watcher import VaultFileWatcher, FileEvent, FileChangeType, create_vault_watcher

__all__ = [
    "VaultService",
    "NoteNotFoundError",
    "PreferencesAdapter",
    "UserPreferences",
    "LearnedContextAdapter",
    "LearnedContext",
    "VaultFileWatcher",
    "FileEvent",
    "FileChangeType",
    "create_vault_watcher",
]
