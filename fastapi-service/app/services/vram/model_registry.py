"""Model registry for tracking loaded models (Single Responsibility)."""
from collections import OrderedDict
from datetime import datetime
from typing import Dict, Optional, List

from app.services.vram.interfaces import LoadedModel, ModelPriority, BackendType


class ModelRegistry:
    """
    Tracks loaded models with LRU ordering.

    Single Responsibility: Model state management.
    """

    def __init__(self):
        # OrderedDict maintains insertion/access order for LRU
        self._models: OrderedDict[str, LoadedModel] = OrderedDict()

    def register(
        self,
        model_id: str,
        backend: BackendType,
        size_gb: float,
        priority: ModelPriority = ModelPriority.NORMAL,
        is_external: bool = False
    ) -> None:
        """Register a newly loaded model."""
        model = LoadedModel(
            model_id=model_id,
            backend=backend,
            size_gb=size_gb,
            priority=priority,
            loaded_at=datetime.now(),
            last_accessed=datetime.now(),
            is_external=is_external
        )
        self._models[model_id] = model

    def update_access(self, model_id: str) -> None:
        """Update last accessed timestamp (for LRU)."""
        if model_id in self._models:
            self._models[model_id].last_accessed = datetime.now()
            # Move to end of OrderedDict (most recently used)
            self._models.move_to_end(model_id)

    def unregister(self, model_id: str) -> None:
        """Remove model from registry."""
        if model_id in self._models:
            del self._models[model_id]

    def is_loaded(self, model_id: str) -> bool:
        """Check if model is currently loaded."""
        return model_id in self._models

    def get(self, model_id: str) -> Optional[LoadedModel]:
        """Get model info."""
        return self._models.get(model_id)

    def get_all(self) -> Dict[str, LoadedModel]:
        """Get all loaded models."""
        return dict(self._models)

    def get_total_usage_gb(self) -> float:
        """Calculate total memory usage from loaded models."""
        return sum(model.size_gb for model in self._models.values())

    def get_manageable_vram_usage(self) -> float:
        """
        Calculate total VRAM used by manageable (non-external) models only.

        External models (is_external=True) are pre-loaded and permanent,
        so they shouldn't count against orchestrator's VRAM limits.

        Returns:
            Total VRAM in GB used by models that can be managed (loaded/unloaded)
        """
        return sum(
            model.size_gb
            for model in self._models.values()
            if not model.is_external
        )

    def get_by_backend(self, backend: BackendType) -> List[LoadedModel]:
        """Get all models for a specific backend."""
        return [
            model for model in self._models.values()
            if model.backend == backend
        ]
