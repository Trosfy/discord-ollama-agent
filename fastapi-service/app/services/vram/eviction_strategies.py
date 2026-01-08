"""Eviction strategies for model unloading (Strategy Pattern)."""
from typing import Dict, List
from app.services.vram.interfaces import IEvictionStrategy, LoadedModel, ModelPriority
import logging_client

logger = logging_client.setup_logger('vram_eviction')


class LRUEvictionStrategy(IEvictionStrategy):
    """Classic LRU eviction - evict least recently used models first."""

    def select_victims(
        self,
        loaded_models: Dict[str, LoadedModel],
        required_gb: float,
        current_usage_gb: float,
        hard_limit_gb: float
    ) -> List[str]:
        """Select victims by LRU order until enough space is freed."""
        # Calculate how much we need to free
        target_usage = current_usage_gb + required_gb
        space_to_free = target_usage - hard_limit_gb

        if space_to_free <= 0:
            return []  # No eviction needed

        # Sort by last_accessed (oldest first)
        models_by_lru = sorted(
            loaded_models.items(),
            key=lambda item: item[1].last_accessed
        )

        victims = []
        freed_gb = 0.0

        for model_id, model in models_by_lru:
            victims.append(model_id)
            freed_gb += model.size_gb

            if freed_gb >= space_to_free:
                break

        logger.info(f"🎯 LRU eviction: Selected {len(victims)} models to free {freed_gb:.1f}GB")
        return victims


class PriorityEvictionStrategy(IEvictionStrategy):
    """Priority-based eviction - evict low priority models first."""

    def select_victims(
        self,
        loaded_models: Dict[str, LoadedModel],
        required_gb: float,
        current_usage_gb: float,
        hard_limit_gb: float
    ) -> List[str]:
        """Select victims by priority (low priority first)."""
        # Calculate how much we need to free
        target_usage = current_usage_gb + required_gb
        space_to_free = target_usage - hard_limit_gb

        if space_to_free <= 0:
            return []  # No eviction needed

        # Sort by priority (low priority first), then by size (larger first for efficiency)
        # Negate priority.value to get descending order (LOW=4 first, CRITICAL=1 last)
        models_by_priority = sorted(
            loaded_models.items(),
            key=lambda item: (-item[1].priority.value, -item[1].size_gb)
        )

        victims = []
        freed_gb = 0.0

        for model_id, model in models_by_priority:
            # Never evict CRITICAL priority models
            if model.priority == ModelPriority.CRITICAL:
                continue

            victims.append(model_id)
            freed_gb += model.size_gb

            if freed_gb >= space_to_free:
                break

        logger.info(f"🎯 Priority eviction: Selected {len(victims)} models to free {freed_gb:.1f}GB")
        return victims


class HybridEvictionStrategy(IEvictionStrategy):
    """
    Hybrid eviction - combines priority and LRU.

    Evicts low priority models first, using LRU within each priority level.
    Protects CRITICAL priority models from eviction.
    """

    def select_victims(
        self,
        loaded_models: Dict[str, LoadedModel],
        required_gb: float,
        current_usage_gb: float,
        hard_limit_gb: float
    ) -> List[str]:
        """Select victims by priority (low first), then LRU within each priority."""
        # Calculate how much we need to free
        target_usage = current_usage_gb + required_gb
        space_to_free = target_usage - hard_limit_gb

        if space_to_free <= 0:
            return []  # No eviction needed

        # Sort by priority (low first), then by last_accessed (oldest first)
        # Negate priority.value to get descending order (LOW=4 first, CRITICAL=1 last)
        models_by_hybrid = sorted(
            loaded_models.items(),
            key=lambda item: (-item[1].priority.value, item[1].last_accessed)
        )

        victims = []
        freed_gb = 0.0

        for model_id, model in models_by_hybrid:
            # Never evict CRITICAL priority models
            if model.priority == ModelPriority.CRITICAL:
                logger.debug(f"🛡️  Protecting CRITICAL model: {model_id}")
                continue

            victims.append(model_id)
            freed_gb += model.size_gb
            logger.debug(
                f"📤 Selected for eviction: {model_id} "
                f"(priority={model.priority.name}, size={model.size_gb:.1f}GB)"
            )

            if freed_gb >= space_to_free:
                break

        if freed_gb < space_to_free:
            logger.warning(
                f"⚠️  Could only free {freed_gb:.1f}GB of {space_to_free:.1f}GB needed "
                f"(CRITICAL models protected)"
            )

        logger.info(
            f"🎯 Hybrid eviction: Selected {len(victims)} models to free {freed_gb:.1f}GB"
        )
        return victims
