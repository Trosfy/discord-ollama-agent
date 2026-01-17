"""Core interfaces for TROISE AI (Dependency Inversion Principle)."""
from .skill import ISkill, SkillResult
from .agent import IAgent, AgentResult
from .tool import ITool, ToolResult
from .profile import IConfigProfile
from .storage import IFileStorage
from .services import (
    IBrainService,
    IVaultService,
    IUserMemory,
    IEmbeddingService,
    IVRAMOrchestrator,
    IExecutor,
    # RAG interfaces
    TextChunk,
    WebChunk,
    IChunkingService,
    IVectorStorage,
)
from .queue import (
    QueueMetrics,
    QueuedRequest,
    UserTier,
    IPrioritizer,
    IRequestSubmitter,
    IQueueInternal,
    IQueueMonitor,
)
from .circuit_breaker import (
    CircuitState,
    CircuitBreakerMetrics,
    ICircuitBreaker,
)
from .graph import (
    GraphState,
    NodeResult,
    GraphResult,
    Edge,
    IGraphNode,
    IGraphCondition,
    IGraph,
    IGraphExecutor,
    IGraphRegistry,
    END,
)

__all__ = [
    "ISkill",
    "SkillResult",
    "IAgent",
    "AgentResult",
    "ITool",
    "ToolResult",
    "IConfigProfile",
    # Storage interface
    "IFileStorage",
    # Service interfaces
    "IBrainService",
    "IVaultService",
    "IUserMemory",
    "IEmbeddingService",
    "IVRAMOrchestrator",
    "IExecutor",
    # RAG interfaces
    "TextChunk",
    "WebChunk",
    "IChunkingService",
    "IVectorStorage",
    # Queue interfaces
    "QueueMetrics",
    "QueuedRequest",
    "UserTier",
    "IPrioritizer",
    "IRequestSubmitter",
    "IQueueInternal",
    "IQueueMonitor",
    # Circuit breaker interfaces
    "CircuitState",
    "CircuitBreakerMetrics",
    "ICircuitBreaker",
    # Graph interfaces
    "GraphState",
    "NodeResult",
    "GraphResult",
    "Edge",
    "IGraphNode",
    "IGraphCondition",
    "IGraph",
    "IGraphExecutor",
    "IGraphRegistry",
    "END",
]
