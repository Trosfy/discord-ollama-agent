"""Tests for VRAMOrchestrator."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.services.vram.orchestrator import VRAMOrchestrator
from app.services.vram.model_registry import ModelRegistry
from app.services.vram.interfaces import (
    IMemoryMonitor,
    IEvictionStrategy,
    IBackendManager,
    MemoryStatus,
    ModelPriority,
    BackendType,
    LoadedModel
)


class MockMemoryMonitor(IMemoryMonitor):
    """Mock memory monitor for testing."""

    def __init__(self, registry, available_gb=50.0):
        self.registry = registry
        self.available_gb = available_gb

    async def get_status(self):
        # Calculate model_usage_gb from registry (realistic behavior)
        model_usage_gb = self.registry.get_total_usage_gb()
        return MemoryStatus(
            total_gb=128.0,
            used_gb=78.0,
            available_gb=self.available_gb,
            model_usage_gb=model_usage_gb,
            psi_pressure={'some_avg10': 0.0, 'full_avg10': 0.0}
        )

    async def check_pressure(self):
        return {'some_avg10': 0.0, 'full_avg10': 0.0}

    async def flush_cache(self):
        pass


class MockEvictionStrategy(IEvictionStrategy):
    """Mock eviction strategy for testing."""

    def __init__(self, victims=None):
        self.victims = victims or []

    def select_victims(self, loaded_models, required_gb, current_usage_gb, hard_limit_gb):
        return self.victims


class MockBackendManager(IBackendManager):
    """Mock backend manager for testing."""

    def __init__(self):
        self.unloaded = []

    def supports(self, backend_type):
        return True

    async def unload(self, model_id, backend_type):
        self.unloaded.append(model_id)

    async def cleanup(self, backend_type):
        pass


@pytest.mark.asyncio
async def test_orchestrator_model_already_loaded():
    """Test requesting a model that's already loaded."""
    registry = ModelRegistry()
    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(registry, monitor, eviction, backend)

    # Pre-register a model
    registry.register("test-model", BackendType.OLLAMA, 20.0)

    # Mock get_model_capabilities
    with patch('app.services.vram.orchestrator.get_model_capabilities') as mock_caps:
        mock_caps.return_value = Mock(
            backend=Mock(type="ollama"),
            vram_size_gb=20.0,
            priority="NORMAL"
        )

        await orchestrator.request_model_load("test-model")

        # Should not evict anything since model already loaded
        assert len(backend.unloaded) == 0


@pytest.mark.asyncio
async def test_orchestrator_successful_load():
    """Test successfully loading a new model."""
    registry = ModelRegistry()
    monitor = MockMemoryMonitor(registry, available_gb=60.0)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(
        registry, monitor, eviction, backend,
        soft_limit_gb=100.0,
        hard_limit_gb=110.0
    )

    with patch('app.services.vram.orchestrator.get_model_capabilities') as mock_caps:
        mock_caps.return_value = Mock(
            backend=Mock(type="ollama"),
            vram_size_gb=20.0,
            priority="NORMAL"
        )

        await orchestrator.request_model_load("new-model")

        # Model should be registered
        assert registry.is_loaded("new-model")
        model = registry.get("new-model")
        assert model.size_gb == 20.0


@pytest.mark.asyncio
async def test_orchestrator_eviction_triggered():
    """Test that eviction is triggered when needed."""
    registry = ModelRegistry()

    # Pre-load models to exceed limit
    registry.register("old-model-1", BackendType.OLLAMA, 40.0, ModelPriority.NORMAL)
    registry.register("old-model-2", BackendType.OLLAMA, 30.0, ModelPriority.NORMAL)
    registry.register("old-model-3", BackendType.OLLAMA, 35.0, ModelPriority.NORMAL)
    # Total: 105GB

    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy(victims=["old-model-1"])  # Will evict old-model-1
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(
        registry, monitor, eviction, backend,
        soft_limit_gb=100.0,
        hard_limit_gb=110.0
    )

    with patch('app.services.vram.orchestrator.get_model_capabilities') as mock_caps:
        mock_caps.return_value = Mock(
            backend=Mock(type="ollama"),
            vram_size_gb=20.0,
            priority="NORMAL"
        )

        await orchestrator.request_model_load("new-model")

        # Should have evicted old-model-1
        assert "old-model-1" in backend.unloaded
        assert not registry.is_loaded("old-model-1")

        # New model should be loaded
        assert registry.is_loaded("new-model")


@pytest.mark.asyncio
async def test_orchestrator_flush_cache_for_large_model():
    """Test that cache is flushed for large models (>70GB)."""
    registry = ModelRegistry()
    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(registry, monitor, eviction, backend)

    # Track if flush_cache was called
    flush_called = False

    async def mock_flush():
        nonlocal flush_called
        flush_called = True

    monitor.flush_cache = mock_flush

    with patch('app.services.vram.orchestrator.get_model_capabilities') as mock_caps:
        mock_caps.return_value = Mock(
            backend=Mock(type="ollama"),
            vram_size_gb=80.0,  # Large model
            priority="NORMAL"
        )

        await orchestrator.request_model_load("large-model")

        # Cache should have been flushed
        assert flush_called


@pytest.mark.asyncio
async def test_orchestrator_get_status():
    """Test getting orchestrator status."""
    registry = ModelRegistry()
    registry.register("model-1", BackendType.OLLAMA, 20.0, ModelPriority.HIGH)
    registry.register("model-2", BackendType.OLLAMA, 30.0, ModelPriority.NORMAL)

    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(
        registry, monitor, eviction, backend,
        soft_limit_gb=100.0,
        hard_limit_gb=110.0
    )

    status = await orchestrator.get_status()

    assert status['memory']['soft_limit_gb'] == 100.0
    assert status['memory']['hard_limit_gb'] == 110.0
    assert len(status['loaded_models']) == 2
    assert status['loaded_models'][0]['model_id'] in ['model-1', 'model-2']


@pytest.mark.asyncio
async def test_orchestrator_mark_model_accessed():
    """Test marking a model as accessed updates LRU."""
    registry = ModelRegistry()
    registry.register("model-1", BackendType.OLLAMA, 20.0)

    original_access = registry.get("model-1").last_accessed

    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(registry, monitor, eviction, backend)

    import asyncio
    await asyncio.sleep(0.01)  # Small delay

    await orchestrator.mark_model_accessed("model-1")

    new_access = registry.get("model-1").last_accessed
    assert new_access > original_access


@pytest.mark.asyncio
async def test_orchestrator_manual_unload():
    """Test manually unloading a model."""
    registry = ModelRegistry()
    registry.register("model-1", BackendType.OLLAMA, 20.0)

    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(registry, monitor, eviction, backend)

    await orchestrator.mark_model_unloaded("model-1")

    # Model should be unregistered
    assert not registry.is_loaded("model-1")

    # Backend should have unloaded it
    assert "model-1" in backend.unloaded


@pytest.mark.asyncio
async def test_orchestrator_memory_error_when_cant_free_enough():
    """Test that MemoryError is raised when can't free enough memory."""
    registry = ModelRegistry()

    # Load a CRITICAL priority model that can't be evicted
    registry.register("critical-model", BackendType.OLLAMA, 90.0, ModelPriority.CRITICAL)

    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy(victims=[])  # Can't evict anything
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(
        registry, monitor, eviction, backend,
        soft_limit_gb=100.0,
        hard_limit_gb=110.0
    )

    with patch('app.services.vram.orchestrator.get_model_capabilities') as mock_caps:
        mock_caps.return_value = Mock(
            backend=Mock(type="ollama"),
            vram_size_gb=30.0,
            priority="NORMAL"
        )

        # Should raise MemoryError since we can't free enough space
        with pytest.raises(MemoryError, match="Cannot free enough memory"):
            await orchestrator.request_model_load("new-model")


@pytest.mark.asyncio
async def test_orchestrator_reconciliation_detects_desync():
    """Test that reconciliation detects and cleans up desynced models."""
    registry = ModelRegistry()
    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(registry, monitor, eviction, backend)

    # Register models in registry (simulate they were loaded)
    registry.register("model-1", BackendType.OLLAMA, 20.0, ModelPriority.NORMAL)
    registry.register("model-2", BackendType.OLLAMA, 30.0, ModelPriority.NORMAL)
    registry.register("model-3", BackendType.OLLAMA, 25.0, ModelPriority.NORMAL)

    # Mock Ollama to report only 2 models actually loaded (model-2 was killed externally)
    with patch('app.services.vram.backend_managers.OllamaBackendManager.get_loaded_models') as mock_ollama:
        mock_ollama.return_value = {"model-1", "model-3"}  # model-2 missing!

        stats = await orchestrator.reconcile_registry()

        # Should detect the desync
        assert stats['registry_count'] == 3  # Registry had 3 models
        assert stats['backend_count'] == 2   # Ollama has 2 models
        assert stats['cleaned_count'] == 1   # Cleaned 1 desync
        assert stats['cleaned_models'] == ["model-2"]

        # Registry should now be in sync
        assert not registry.is_loaded("model-2")
        assert registry.is_loaded("model-1")
        assert registry.is_loaded("model-3")


@pytest.mark.asyncio
async def test_orchestrator_reconciliation_no_desync():
    """Test that reconciliation works when registry is already in sync."""
    registry = ModelRegistry()
    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(registry, monitor, eviction, backend)

    # Register models
    registry.register("model-1", BackendType.OLLAMA, 20.0, ModelPriority.NORMAL)
    registry.register("model-2", BackendType.OLLAMA, 30.0, ModelPriority.NORMAL)

    # Mock Ollama to report same models
    with patch('app.services.vram.backend_managers.OllamaBackendManager.get_loaded_models') as mock_ollama:
        mock_ollama.return_value = {"model-1", "model-2"}

        stats = await orchestrator.reconcile_registry()

        # No cleanup needed
        assert stats['registry_count'] == 2
        assert stats['backend_count'] == 2
        assert stats['cleaned_count'] == 0
        assert stats['cleaned_models'] == []


@pytest.mark.asyncio
async def test_orchestrator_reconciliation_all_models_killed():
    """Test reconciliation when all models were killed externally."""
    registry = ModelRegistry()
    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(registry, monitor, eviction, backend)

    # Register 3 models
    registry.register("model-1", BackendType.OLLAMA, 20.0, ModelPriority.NORMAL)
    registry.register("model-2", BackendType.OLLAMA, 30.0, ModelPriority.NORMAL)
    registry.register("model-3", BackendType.OLLAMA, 25.0, ModelPriority.NORMAL)

    # Mock Ollama to report no models (all killed by earlyoom)
    with patch('app.services.vram.backend_managers.OllamaBackendManager.get_loaded_models') as mock_ollama:
        mock_ollama.return_value = set()  # Empty!

        stats = await orchestrator.reconcile_registry()

        # All models should be cleaned
        assert stats['registry_count'] == 3
        assert stats['backend_count'] == 0
        assert stats['cleaned_count'] == 3
        assert set(stats['cleaned_models']) == {"model-1", "model-2", "model-3"}

        # Registry should be empty
        assert len(registry.get_all()) == 0


@pytest.mark.asyncio
async def test_orchestrator_emergency_evict_low_priority_only():
    """Test emergency eviction with LOW priority only evicts LOW models."""
    registry = ModelRegistry()
    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(registry, monitor, eviction, backend)

    # Register models with different priorities
    registry.register("low-model-1", BackendType.OLLAMA, 20.0, ModelPriority.LOW)
    registry.register("low-model-2", BackendType.OLLAMA, 25.0, ModelPriority.LOW)
    registry.register("normal-model", BackendType.OLLAMA, 30.0, ModelPriority.NORMAL)
    registry.register("high-model", BackendType.OLLAMA, 35.0, ModelPriority.HIGH)

    # Make low-model-2 older (less recently accessed)
    import asyncio
    await asyncio.sleep(0.01)
    registry.update_access("low-model-1")

    # Emergency eviction with LOW priority - should evict low-model-2 (LRU among LOW)
    result = await orchestrator.emergency_evict_lru(ModelPriority.LOW)

    assert result['evicted'] is True
    assert result['model_id'] == "low-model-2"
    assert result['size_gb'] == 25.0
    assert result['reason'] == 'psi_emergency'

    # Verify registry state
    assert not registry.is_loaded("low-model-2")
    assert registry.is_loaded("low-model-1")
    assert registry.is_loaded("normal-model")
    assert registry.is_loaded("high-model")

    # Verify backend unload was called
    assert "low-model-2" in backend.unloaded


@pytest.mark.asyncio
async def test_orchestrator_emergency_evict_normal_priority():
    """Test emergency eviction with NORMAL priority evicts LOW and NORMAL models."""
    registry = ModelRegistry()
    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(registry, monitor, eviction, backend)

    # Register models with different priorities
    registry.register("low-model", BackendType.OLLAMA, 20.0, ModelPriority.LOW)
    registry.register("normal-model-1", BackendType.OLLAMA, 30.0, ModelPriority.NORMAL)
    registry.register("normal-model-2", BackendType.OLLAMA, 25.0, ModelPriority.NORMAL)
    registry.register("high-model", BackendType.OLLAMA, 35.0, ModelPriority.HIGH)

    # Make normal-model-1 older
    import asyncio
    await asyncio.sleep(0.01)
    registry.update_access("low-model")
    registry.update_access("normal-model-2")
    registry.update_access("high-model")

    # Emergency eviction with NORMAL - should evict normal-model-1 (LRU among LOW+NORMAL)
    result = await orchestrator.emergency_evict_lru(ModelPriority.NORMAL)

    assert result['evicted'] is True
    assert result['model_id'] == "normal-model-1"
    assert result['size_gb'] == 30.0

    # Verify HIGH model was NOT evicted
    assert registry.is_loaded("high-model")


@pytest.mark.asyncio
async def test_orchestrator_emergency_evict_no_eligible_models():
    """Test emergency eviction when no eligible models exist."""
    registry = ModelRegistry()
    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(registry, monitor, eviction, backend)

    # Only HIGH and CRITICAL models
    registry.register("high-model", BackendType.OLLAMA, 30.0, ModelPriority.HIGH)
    registry.register("critical-model", BackendType.OLLAMA, 40.0, ModelPriority.CRITICAL)

    # Try to evict LOW priority - should fail (no LOW models)
    result = await orchestrator.emergency_evict_lru(ModelPriority.LOW)

    assert result['evicted'] is False
    assert result['model_id'] is None
    assert result['size_gb'] == 0.0
    assert result['reason'] == 'no_eligible_models'

    # All models should still be loaded
    assert registry.is_loaded("high-model")
    assert registry.is_loaded("critical-model")


@pytest.mark.asyncio
async def test_orchestrator_emergency_evict_never_evicts_critical():
    """Test that emergency eviction NEVER evicts CRITICAL models."""
    registry = ModelRegistry()
    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(registry, monitor, eviction, backend)

    # Register only CRITICAL models
    registry.register("critical-model-1", BackendType.OLLAMA, 40.0, ModelPriority.CRITICAL)
    registry.register("critical-model-2", BackendType.OLLAMA, 35.0, ModelPriority.CRITICAL)

    # Even with HIGH priority level, should NOT evict CRITICAL
    result = await orchestrator.emergency_evict_lru(ModelPriority.HIGH)

    assert result['evicted'] is False
    assert result['reason'] == 'no_eligible_models'

    # Both CRITICAL models should remain
    assert registry.is_loaded("critical-model-1")
    assert registry.is_loaded("critical-model-2")


@pytest.mark.asyncio
async def test_orchestrator_emergency_evict_selects_lru():
    """Test that emergency eviction selects the least recently used model."""
    registry = ModelRegistry()
    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(registry, monitor, eviction, backend)

    # Register multiple LOW priority models
    registry.register("low-1", BackendType.OLLAMA, 20.0, ModelPriority.LOW)
    registry.register("low-2", BackendType.OLLAMA, 25.0, ModelPriority.LOW)
    registry.register("low-3", BackendType.OLLAMA, 30.0, ModelPriority.LOW)

    # Access them in specific order (low-1 is oldest, low-3 is newest)
    import asyncio
    await asyncio.sleep(0.01)
    registry.update_access("low-2")
    await asyncio.sleep(0.01)
    registry.update_access("low-3")

    # Should evict low-1 (least recently accessed)
    result = await orchestrator.emergency_evict_lru(ModelPriority.LOW)

    assert result['evicted'] is True
    assert result['model_id'] == "low-1"
    assert result['size_gb'] == 20.0

    # Verify low-1 is gone but others remain
    assert not registry.is_loaded("low-1")
    assert registry.is_loaded("low-2")
    assert registry.is_loaded("low-3")


@pytest.mark.asyncio
async def test_orchestrator_emergency_evict_backend_failure():
    """Test emergency eviction handling when backend unload fails."""
    registry = ModelRegistry()
    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy()

    # Mock backend that fails unload
    class FailingBackendManager(IBackendManager):
        def supports(self, backend_type):
            return True

        async def unload(self, model_id, backend_type):
            raise RuntimeError("Backend unload failed")

        async def cleanup(self, backend_type):
            pass

    backend = FailingBackendManager()
    orchestrator = VRAMOrchestrator(registry, monitor, eviction, backend)

    # Register a LOW priority model
    registry.register("low-model", BackendType.OLLAMA, 20.0, ModelPriority.LOW)

    # Emergency eviction should catch the exception
    result = await orchestrator.emergency_evict_lru(ModelPriority.LOW)

    assert result['evicted'] is False
    assert result['model_id'] == "low-model"
    assert 'eviction_failed' in result['reason']

    # Model should still be in registry (failed to unload)
    assert registry.is_loaded("low-model")


# ============================================================
# Circuit Breaker Tests
# ============================================================

@pytest.mark.asyncio
async def test_orchestrator_circuit_breaker_triggers_eviction():
    """Test that circuit breaker evicts LRU models when model has crash history."""
    from app.services.vram.crash_tracker import CrashTracker

    # Setup
    registry = ModelRegistry()
    crash_tracker = CrashTracker(crash_threshold=2, time_window_seconds=300)

    # Pre-load models
    registry.register("safe-model-1", BackendType.OLLAMA, 30.0, ModelPriority.NORMAL)
    registry.register("safe-model-2", BackendType.OLLAMA, 25.0, ModelPriority.NORMAL)

    # Record crashes for problematic model
    crash_tracker.record_crash("problem-model")
    crash_tracker.record_crash("problem-model")

    monitor = MockMemoryMonitor(registry, available_gb=30.0)  # Insufficient - forces eviction
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(
        registry, monitor, eviction, backend, crash_tracker,
        soft_limit_gb=100.0, hard_limit_gb=110.0
    )

    with patch('app.services.vram.orchestrator.get_model_capabilities') as mock_caps:
        mock_caps.return_value = Mock(
            backend=Mock(type="ollama"),
            vram_size_gb=40.0,  # Requires 40GB + 20GB buffer = 60GB total, but only 30GB available
            priority="NORMAL"
        )
        with patch('app.services.vram.orchestrator.settings') as mock_settings:
            mock_settings.VRAM_CIRCUIT_BREAKER_ENABLED = True
            mock_settings.VRAM_CIRCUIT_BREAKER_BUFFER_GB = 20.0
            mock_settings.VRAM_CRASH_WINDOW_SECONDS = 300

            # Circuit breaker should proactively evict models
            await orchestrator.request_model_load("problem-model")

            # Verify eviction happened (freed space for buffer)
            assert len(backend.unloaded) >= 1  # At least one model evicted
            assert registry.is_loaded("problem-model")


@pytest.mark.asyncio
async def test_orchestrator_circuit_breaker_blocks_when_no_evictable():
    """Test that circuit breaker blocks when no models can be evicted."""
    from app.services.vram.crash_tracker import CrashTracker

    registry = ModelRegistry()
    crash_tracker = CrashTracker(crash_threshold=2, time_window_seconds=300)

    # Only CRITICAL models (can't evict)
    registry.register("critical-model", BackendType.OLLAMA, 80.0, ModelPriority.CRITICAL)

    # Record crashes
    crash_tracker.record_crash("problem-model")
    crash_tracker.record_crash("problem-model")

    monitor = MockMemoryMonitor(registry, available_gb=30.0)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(
        registry, monitor, eviction, backend, crash_tracker,
        soft_limit_gb=100.0, hard_limit_gb=110.0
    )

    with patch('app.services.vram.orchestrator.get_model_capabilities') as mock_caps:
        mock_caps.return_value = Mock(
            backend=Mock(type="ollama"),
            vram_size_gb=40.0,
            priority="NORMAL"
        )
        with patch('app.services.vram.orchestrator.settings') as mock_settings:
            mock_settings.VRAM_CIRCUIT_BREAKER_ENABLED = True
            mock_settings.VRAM_CIRCUIT_BREAKER_BUFFER_GB = 20.0
            mock_settings.VRAM_CRASH_WINDOW_SECONDS = 300

            # Should raise MemoryError with circuit breaker message
            with pytest.raises(MemoryError, match="Circuit breaker"):
                await orchestrator.request_model_load("problem-model")


@pytest.mark.asyncio
async def test_orchestrator_circuit_breaker_no_crashes():
    """Test that circuit breaker doesn't trigger for model with no crash history."""
    from app.services.vram.crash_tracker import CrashTracker

    registry = ModelRegistry()
    crash_tracker = CrashTracker(crash_threshold=2, time_window_seconds=300)
    monitor = MockMemoryMonitor(registry, available_gb=60.0)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(
        registry, monitor, eviction, backend, crash_tracker,
        soft_limit_gb=100.0, hard_limit_gb=110.0
    )

    with patch('app.services.vram.orchestrator.get_model_capabilities') as mock_caps:
        mock_caps.return_value = Mock(
            backend=Mock(type="ollama"),
            vram_size_gb=20.0,
            priority="NORMAL"
        )
        with patch('app.services.vram.orchestrator.settings') as mock_settings:
            mock_settings.VRAM_CIRCUIT_BREAKER_ENABLED = True

            # Should load normally without circuit breaker triggering
            await orchestrator.request_model_load("safe-model")

            # No evictions should have happened (circuit breaker didn't trigger)
            assert len(backend.unloaded) == 0
            assert registry.is_loaded("safe-model")


@pytest.mark.asyncio
async def test_orchestrator_mark_model_unloaded_tracks_crash():
    """Test that mark_model_unloaded records crashes when crashed=True."""
    from app.services.vram.crash_tracker import CrashTracker

    registry = ModelRegistry()
    crash_tracker = CrashTracker(crash_threshold=2, time_window_seconds=300)
    monitor = MockMemoryMonitor(registry)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    # Pre-register model
    registry.register("test-model", BackendType.OLLAMA, 20.0, ModelPriority.NORMAL)

    orchestrator = VRAMOrchestrator(
        registry, monitor, eviction, backend, crash_tracker,
        soft_limit_gb=100.0, hard_limit_gb=110.0
    )

    with patch('app.services.vram.orchestrator.settings') as mock_settings:
        mock_settings.VRAM_CIRCUIT_BREAKER_ENABLED = True

        # Mark as crashed
        await orchestrator.mark_model_unloaded("test-model", crashed=True)

        # Verify crash was tracked
        status = crash_tracker.check_crash_history("test-model")
        assert status['crash_count'] == 1


@pytest.mark.asyncio
async def test_orchestrator_circuit_breaker_disabled():
    """Test that circuit breaker is bypassed when disabled."""
    from app.services.vram.crash_tracker import CrashTracker

    registry = ModelRegistry()
    crash_tracker = CrashTracker(crash_threshold=2, time_window_seconds=300)

    # Record crashes
    crash_tracker.record_crash("problem-model")
    crash_tracker.record_crash("problem-model")

    monitor = MockMemoryMonitor(registry, available_gb=60.0)
    eviction = MockEvictionStrategy()
    backend = MockBackendManager()

    orchestrator = VRAMOrchestrator(
        registry, monitor, eviction, backend, crash_tracker,
        soft_limit_gb=100.0, hard_limit_gb=110.0
    )

    with patch('app.services.vram.orchestrator.get_model_capabilities') as mock_caps:
        mock_caps.return_value = Mock(
            backend=Mock(type="ollama"),
            vram_size_gb=20.0,
            priority="NORMAL"
        )
        with patch('app.services.vram.orchestrator.settings') as mock_settings:
            mock_settings.VRAM_CIRCUIT_BREAKER_ENABLED = False  # DISABLED

            # Should load normally without circuit breaker check
            await orchestrator.request_model_load("problem-model")

            # Circuit breaker shouldn't have triggered (no evictions for headroom)
            assert len(backend.unloaded) == 0
            assert registry.is_loaded("problem-model")
