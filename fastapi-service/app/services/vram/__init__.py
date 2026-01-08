"""VRAM orchestration service - Factory and singleton access."""
from typing import Optional

from app.services.vram.model_registry import ModelRegistry
from app.services.vram.unified_memory_monitor import UnifiedMemoryMonitor
from app.services.vram.eviction_strategies import HybridEvictionStrategy
from app.services.vram.backend_managers import CompositeBackendManager
from app.services.vram.crash_tracker import CrashTracker
from app.services.vram.orchestrator import VRAMOrchestrator
from app.config import settings
import logging_client

logger = logging_client.setup_logger('vram_init')

# Singleton instances
_orchestrator: Optional[VRAMOrchestrator] = None
_crash_tracker: Optional[CrashTracker] = None


def get_crash_tracker() -> CrashTracker:
    """
    Get global crash tracker instance (singleton pattern).

    Creates crash tracker on first call for circuit breaker pattern.

    Returns:
        Singleton CrashTracker instance
    """
    global _crash_tracker
    if _crash_tracker is None:
        crash_threshold = getattr(settings, 'VRAM_CRASH_THRESHOLD', 2)
        crash_window = getattr(settings, 'VRAM_CRASH_WINDOW_SECONDS', 300)

        _crash_tracker = CrashTracker(
            crash_threshold=crash_threshold,
            time_window_seconds=crash_window
        )
        logger.info(
            f"✅ CrashTracker singleton initialized "
            f"(threshold={crash_threshold}, window={crash_window}s)"
        )
    return _crash_tracker


def create_orchestrator() -> VRAMOrchestrator:
    """
    Create orchestrator with default dependencies.

    Uses dependency injection pattern to wire up all components:
    - ModelRegistry: Tracks loaded models
    - UnifiedMemoryMonitor: Monitors system memory via `free` + PSI
    - HybridEvictionStrategy: Priority-weighted LRU eviction
    - CompositeBackendManager: Delegates to Ollama/TensorRT/vLLM managers
    - CrashTracker: Circuit breaker pattern for crash loops

    Returns:
        Configured VRAMOrchestrator instance
    """
    # Create components
    registry = ModelRegistry()
    memory_monitor = UnifiedMemoryMonitor(registry)
    eviction_strategy = HybridEvictionStrategy()  # Priority-weighted LRU
    backend_manager = CompositeBackendManager()   # Delegates to backend-specific managers
    crash_tracker = get_crash_tracker()           # Circuit breaker for crash loops

    # Get limits from settings
    soft_limit = getattr(settings, 'VRAM_SOFT_LIMIT_GB', 100.0)
    hard_limit = getattr(settings, 'VRAM_HARD_LIMIT_GB', 110.0)

    logger.info(
        f"🧠 Creating VRAMOrchestrator "
        f"(soft_limit={soft_limit:.0f}GB, hard_limit={hard_limit:.0f}GB)"
    )

    return VRAMOrchestrator(
        registry=registry,
        memory_monitor=memory_monitor,
        eviction_strategy=eviction_strategy,
        backend_manager=backend_manager,
        crash_tracker=crash_tracker,
        soft_limit_gb=soft_limit,
        hard_limit_gb=hard_limit
    )


def get_orchestrator() -> VRAMOrchestrator:
    """
    Get global orchestrator instance (singleton pattern).

    Creates orchestrator on first call, returns cached instance on subsequent calls.

    Returns:
        Singleton VRAMOrchestrator instance
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = create_orchestrator()
        logger.info("✅ VRAMOrchestrator singleton initialized")
    return _orchestrator


# Export public API
__all__ = [
    'get_orchestrator',
    'create_orchestrator',
    'get_crash_tracker',
    'VRAMOrchestrator',
    'CrashTracker',
    'ModelRegistry',
    'UnifiedMemoryMonitor',
    'HybridEvictionStrategy',
    'CompositeBackendManager'
]
