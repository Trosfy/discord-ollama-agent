"""Tests for ModelRegistry."""
import pytest
from datetime import datetime, timedelta
from app.services.vram.model_registry import ModelRegistry
from app.services.vram.interfaces import ModelPriority, BackendType


def test_register_model():
    """Test registering a model."""
    registry = ModelRegistry()

    registry.register(
        model_id="test-model",
        backend=BackendType.OLLAMA,
        size_gb=20.0,
        priority=ModelPriority.NORMAL
    )

    assert registry.is_loaded("test-model")
    model = registry.get("test-model")
    assert model.model_id == "test-model"
    assert model.backend == BackendType.OLLAMA
    assert model.size_gb == 20.0
    assert model.priority == ModelPriority.NORMAL


def test_unregister_model():
    """Test unregistering a model."""
    registry = ModelRegistry()
    registry.register("test-model", BackendType.OLLAMA, 20.0)

    assert registry.is_loaded("test-model")

    registry.unregister("test-model")

    assert not registry.is_loaded("test-model")
    assert registry.get("test-model") is None


def test_update_access():
    """Test updating last access timestamp."""
    registry = ModelRegistry()
    registry.register("model-1", BackendType.OLLAMA, 20.0)

    original_time = registry.get("model-1").last_accessed

    # Small delay to ensure time difference
    import time
    time.sleep(0.01)

    registry.update_access("model-1")

    new_time = registry.get("model-1").last_accessed
    assert new_time > original_time


def test_lru_ordering():
    """Test that LRU ordering is maintained."""
    registry = ModelRegistry()

    # Register 3 models
    registry.register("model-1", BackendType.OLLAMA, 20.0)
    registry.register("model-2", BackendType.OLLAMA, 30.0)
    registry.register("model-3", BackendType.OLLAMA, 40.0)

    # Access model-1 to make it most recent
    registry.update_access("model-1")

    # Get all models (should be in LRU order)
    models = registry.get_all()
    model_ids = list(models.keys())

    # model-1 should be last (most recently accessed)
    assert model_ids[-1] == "model-1"


def test_get_total_usage():
    """Test calculating total memory usage."""
    registry = ModelRegistry()

    registry.register("model-1", BackendType.OLLAMA, 20.0)
    registry.register("model-2", BackendType.OLLAMA, 30.0)
    registry.register("model-3", BackendType.OLLAMA, 40.0)

    total_usage = registry.get_total_usage_gb()
    assert total_usage == 90.0


def test_get_by_backend():
    """Test filtering models by backend."""
    registry = ModelRegistry()

    registry.register("ollama-1", BackendType.OLLAMA, 20.0)
    registry.register("ollama-2", BackendType.OLLAMA, 30.0)
    registry.register("tensorrt-1", BackendType.TENSORRT, 40.0)

    ollama_models = registry.get_by_backend(BackendType.OLLAMA)
    assert len(ollama_models) == 2
    assert all(m.backend == BackendType.OLLAMA for m in ollama_models)

    tensorrt_models = registry.get_by_backend(BackendType.TENSORRT)
    assert len(tensorrt_models) == 1
    assert tensorrt_models[0].backend == BackendType.TENSORRT


def test_empty_registry():
    """Test operations on empty registry."""
    registry = ModelRegistry()

    assert not registry.is_loaded("nonexistent")
    assert registry.get("nonexistent") is None
    assert registry.get_total_usage_gb() == 0.0
    assert len(registry.get_all()) == 0
