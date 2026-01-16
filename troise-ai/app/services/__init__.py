"""
TROISE AI Services Module.

Provides service layer components for the TROISE AI system including
backend management, model orchestration, and external integrations.
"""

from .backend_manager import (
    IBackendClient,
    OllamaClient,
    SGLangClient,
    VLLMClient,
    BackendManager,
)
from .profile_manager import (
    ProfileManager,
    ProfileManagerState,
    FallbackState,
    FallbackMetrics,
    FALLBACK_THRESHOLD,
    RECOVERY_SUCCESS_THRESHOLD,
)
from .vram_orchestrator import (
    VRAMOrchestrator,
    LoadedModel,
)
from .embedding_service import (
    EmbeddingService,
    EmbeddingServiceError,
    create_embedding_service,
)
from .brain_service import (
    BrainService,
    SearchResult,
    FetchResult,
    create_brain_service,
)
from .user_profile_service import (
    UserProfile,
    UserProfileService,
    UserMemoryAdapter,
    create_user_profile_service,
    create_user_memory_adapter,
)
from .chunking_service import (
    LangChainChunkingService,
    ChunkingServiceError,
    create_chunking_service,
)
from .memory_promotion import (
    MemoryPromotionService,
    PromotionResult,
    MemoryStats,
    create_memory_promotion_service,
)
from .queue_manager import (
    QueueWorker,
    WorkerPool,
    QueueManager,
)
from .circuit_breaker_registry import (
    CircuitBreakerRegistry,
)
from .visibility_monitor import (
    VisibilityMonitor,
)

__all__ = [
    # Backend management
    "IBackendClient",
    "OllamaClient",
    "SGLangClient",
    "VLLMClient",
    "BackendManager",
    # Profile management
    "ProfileManager",
    "ProfileManagerState",
    "FallbackState",
    "FallbackMetrics",
    "FALLBACK_THRESHOLD",
    "RECOVERY_SUCCESS_THRESHOLD",
    # VRAM orchestration
    "VRAMOrchestrator",
    "LoadedModel",
    # Embedding service
    "EmbeddingService",
    "EmbeddingServiceError",
    "create_embedding_service",
    # Brain service
    "BrainService",
    "SearchResult",
    "FetchResult",
    "create_brain_service",
    # User profile service
    "UserProfile",
    "UserProfileService",
    "UserMemoryAdapter",
    "create_user_profile_service",
    "create_user_memory_adapter",
    # Chunking service (RAG)
    "LangChainChunkingService",
    "ChunkingServiceError",
    "create_chunking_service",
    # Memory promotion service
    "MemoryPromotionService",
    "PromotionResult",
    "MemoryStats",
    "create_memory_promotion_service",
    # Queue management
    "QueueWorker",
    "WorkerPool",
    "QueueManager",
    # Circuit breaker
    "CircuitBreakerRegistry",
    # Visibility monitor
    "VisibilityMonitor",
]
