"""Adapters for external services and storage."""
from .obsidian import (
    VaultService,
    PreferencesAdapter,
    LearnedContextAdapter,
    UserPreferences,
    LearnedContext,
)
from .dynamodb import (
    DynamoDBClient,
    TroiseMainAdapter,
    TroiseBrainAdapter,
    TroiseVectorsAdapter,
    SessionItem,
    MessageItem,
    InferenceItem,
    MemoryItem,
    NoteMetaItem,
    NoteChunkItem,
    EmbeddingCacheItem,
)
from .minio import MinIOAdapter, MinIOConfig

__all__ = [
    # Obsidian adapters
    "VaultService",
    "PreferencesAdapter",
    "LearnedContextAdapter",
    "UserPreferences",
    "LearnedContext",
    # DynamoDB adapters
    "DynamoDBClient",
    "TroiseMainAdapter",
    "TroiseBrainAdapter",
    "TroiseVectorsAdapter",
    "SessionItem",
    "MessageItem",
    "InferenceItem",
    "MemoryItem",
    "NoteMetaItem",
    "NoteChunkItem",
    "EmbeddingCacheItem",
    # MinIO adapters
    "MinIOAdapter",
    "MinIOConfig",
]
