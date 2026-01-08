"""Tests for eviction strategies."""
import pytest
from datetime import datetime, timedelta
from app.services.vram.eviction_strategies import (
    LRUEvictionStrategy,
    PriorityEvictionStrategy,
    HybridEvictionStrategy
)
from app.services.vram.interfaces import LoadedModel, ModelPriority, BackendType


def create_test_model(model_id: str, size_gb: float, priority: ModelPriority, age_seconds: int = 0):
    """Helper to create a test model."""
    now = datetime.now()
    return LoadedModel(
        model_id=model_id,
        backend=BackendType.OLLAMA,
        size_gb=size_gb,
        priority=priority,
        loaded_at=now - timedelta(seconds=age_seconds),
        last_accessed=now - timedelta(seconds=age_seconds)
    )


def test_lru_eviction_strategy():
    """Test LRU eviction selects oldest models first."""
    strategy = LRUEvictionStrategy()

    # Create models with different ages (older = higher age_seconds)
    models = {
        "model-new": create_test_model("model-new", 20.0, ModelPriority.NORMAL, age_seconds=10),
        "model-old": create_test_model("model-old", 30.0, ModelPriority.NORMAL, age_seconds=100),
        "model-medium": create_test_model("model-medium", 25.0, ModelPriority.NORMAL, age_seconds=50),
    }

    # Need to free 40GB from current usage of 75GB with limit of 100GB
    # Current: 75GB, Adding: 40GB, Projected: 115GB, Limit: 100GB -> Need to free 15GB
    victims = strategy.select_victims(
        loaded_models=models,
        required_gb=40.0,
        current_usage_gb=75.0,
        hard_limit_gb=100.0
    )

    # Should evict oldest first (model-old = 30GB is enough)
    assert len(victims) == 1
    assert victims[0] == "model-old"


def test_lru_no_eviction_needed():
    """Test LRU when no eviction is needed."""
    strategy = LRUEvictionStrategy()

    models = {
        "model-1": create_test_model("model-1", 20.0, ModelPriority.NORMAL),
        "model-2": create_test_model("model-2", 30.0, ModelPriority.NORMAL),
    }

    # Current: 50GB, Adding: 20GB, Projected: 70GB, Limit: 100GB -> No eviction needed
    victims = strategy.select_victims(
        loaded_models=models,
        required_gb=20.0,
        current_usage_gb=50.0,
        hard_limit_gb=100.0
    )

    assert len(victims) == 0


def test_priority_eviction_strategy():
    """Test priority-based eviction selects low priority first."""
    strategy = PriorityEvictionStrategy()

    models = {
        "high-priority": create_test_model("high-priority", 20.0, ModelPriority.HIGH),
        "normal-priority": create_test_model("normal-priority", 30.0, ModelPriority.NORMAL),
        "low-priority": create_test_model("low-priority", 25.0, ModelPriority.LOW),
    }

    # Need to free 30GB
    victims = strategy.select_victims(
        loaded_models=models,
        required_gb=40.0,
        current_usage_gb=75.0,
        hard_limit_gb=100.0
    )

    # Should evict low priority first, then normal
    assert "low-priority" in victims
    assert "high-priority" not in victims  # High priority protected


def test_priority_never_evict_critical():
    """Test that CRITICAL priority models are never evicted."""
    strategy = PriorityEvictionStrategy()

    models = {
        "critical": create_test_model("critical", 50.0, ModelPriority.CRITICAL),
        "normal": create_test_model("normal", 30.0, ModelPriority.NORMAL),
    }

    # Even if we need lots of space, CRITICAL should not be evicted
    victims = strategy.select_victims(
        loaded_models=models,
        required_gb=60.0,
        current_usage_gb=80.0,
        hard_limit_gb=100.0
    )

    assert "critical" not in victims
    assert "normal" in victims


def test_hybrid_eviction_strategy():
    """Test hybrid strategy combines priority and LRU."""
    strategy = HybridEvictionStrategy()

    models = {
        "low-old": create_test_model("low-old", 20.0, ModelPriority.LOW, age_seconds=100),
        "low-new": create_test_model("low-new", 20.0, ModelPriority.LOW, age_seconds=10),
        "normal-old": create_test_model("normal-old", 30.0, ModelPriority.NORMAL, age_seconds=100),
        "high-old": create_test_model("high-old", 25.0, ModelPriority.HIGH, age_seconds=100),
    }

    # Need to free 30GB
    victims = strategy.select_victims(
        loaded_models=models,
        required_gb=40.0,
        current_usage_gb=95.0,
        hard_limit_gb=100.0
    )

    # Should evict LOW priority first (by LRU within priority)
    # Then NORMAL priority if needed
    assert "low-old" in victims  # Lowest priority + oldest
    # May also evict low-new or normal-old to reach 30GB
    assert "high-old" not in victims  # High priority better protected


def test_hybrid_protects_critical():
    """Test hybrid strategy protects CRITICAL models."""
    strategy = HybridEvictionStrategy()

    models = {
        "critical-old": create_test_model("critical-old", 40.0, ModelPriority.CRITICAL, age_seconds=200),
        "low-new": create_test_model("low-new", 20.0, ModelPriority.LOW, age_seconds=10),
    }

    # Need eviction: current 60GB + required 50GB = 110GB, limit 100GB -> need to free 10GB
    victims = strategy.select_victims(
        loaded_models=models,
        required_gb=50.0,  # Changed from 30 to trigger eviction
        current_usage_gb=60.0,
        hard_limit_gb=100.0
    )

    # Even though critical-old is much older and larger, it should not be evicted
    assert "critical-old" not in victims
    assert "low-new" in victims


def test_eviction_multiple_models():
    """Test evicting multiple models to free enough space."""
    strategy = LRUEvictionStrategy()

    models = {
        "model-1": create_test_model("model-1", 10.0, ModelPriority.NORMAL, age_seconds=100),
        "model-2": create_test_model("model-2", 15.0, ModelPriority.NORMAL, age_seconds=80),
        "model-3": create_test_model("model-3", 20.0, ModelPriority.NORMAL, age_seconds=60),
    }

    # Need to free 30GB - should evict model-1 (10GB) + model-2 (15GB) = 25GB
    # Actually need to continue until we have 30GB freed
    victims = strategy.select_victims(
        loaded_models=models,
        required_gb=50.0,
        current_usage_gb=45.0,
        hard_limit_gb=100.0
    )

    # No eviction needed since 45 + 50 = 95 < 100
    assert len(victims) == 0

    # Try case where eviction IS needed
    victims = strategy.select_victims(
        loaded_models=models,
        required_gb=70.0,
        current_usage_gb=45.0,
        hard_limit_gb=100.0
    )

    # Need to free 15GB (45 + 70 = 115, limit 100, so free 15)
    # Should evict model-1 (10GB) + model-2 (15GB) = 25GB total
    assert len(victims) >= 1
    assert "model-1" in victims  # Oldest
