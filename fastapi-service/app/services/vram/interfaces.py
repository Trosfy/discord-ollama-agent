"""Interfaces for VRAM orchestration components (Dependency Inversion)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum


# Data Models
class ModelPriority(Enum):
    """Priority levels for model eviction."""
    CRITICAL = 1  # Router models (never evict)
    HIGH = 2      # Frequently used models
    NORMAL = 3    # Standard models (default)
    LOW = 4       # Rarely used, evict first


class BackendType(Enum):
    """Supported backend types for model inference."""
    OLLAMA = "ollama"
    TENSORRT = "tensorrt-llm"
    VLLM = "vllm"
    SGLANG = "sglang"


@dataclass
class LoadedModel:
    """Represents a model currently loaded in memory."""
    model_id: str
    backend: BackendType
    size_gb: float
    priority: ModelPriority
    loaded_at: datetime
    last_accessed: datetime  # For LRU tracking
    is_external: bool = False  # True for pre-loaded external models (SGLang, vLLM, etc.)


@dataclass
class MemoryStatus:
    """Current system memory state with PSI data."""
    total_gb: float
    used_gb: float
    available_gb: float
    model_usage_gb: float  # Sum of all loaded models
    psi_pressure: Dict[str, float]  # PSI metrics (some_avg10, full_avg10)


# Interfaces (Open/Closed Principle)

class IMemoryMonitor(ABC):
    """Interface for memory monitoring strategies."""

    @abstractmethod
    async def get_status(self) -> MemoryStatus:
        """Query system memory and return status."""
        pass

    @abstractmethod
    async def check_pressure(self) -> Dict[str, float]:
        """Check PSI (Pressure Stall Information)."""
        pass

    @abstractmethod
    async def flush_cache(self) -> None:
        """Flush system buffer cache."""
        pass


class IEvictionStrategy(ABC):
    """Interface for model eviction strategies (Strategy Pattern)."""

    @abstractmethod
    def select_victims(
        self,
        loaded_models: Dict[str, LoadedModel],
        required_gb: float,
        current_usage_gb: float,
        hard_limit_gb: float
    ) -> List[str]:
        """
        Select models to evict to free required space.

        Args:
            loaded_models: Currently loaded models
            required_gb: Space needed for new model
            current_usage_gb: Current memory usage
            hard_limit_gb: Memory hard limit

        Returns:
            List of model_ids to evict (in order)
        """
        pass


class IBackendManager(ABC):
    """Interface for backend-specific operations (Strategy Pattern)."""

    @abstractmethod
    def supports(self, backend_type: BackendType) -> bool:
        """Check if this manager handles given backend type."""
        pass

    @abstractmethod
    async def unload(self, model_id: str, backend_type: BackendType) -> None:
        """Unload model from backend."""
        pass

    @abstractmethod
    async def cleanup(self, backend_type: BackendType) -> None:
        """Cleanup backend resources (shared memory, etc.)."""
        pass
