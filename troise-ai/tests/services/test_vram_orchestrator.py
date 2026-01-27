"""Tests for VRAMOrchestrator.

Tests cover:
- VRAM detection via nvidia-smi
- Model loading with eviction
- Priority-based eviction (CRITICAL never evict)
- Status reporting
- Sync with backends
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import List

from app.services.vram_orchestrator import VRAMOrchestrator, LoadedModel
from app.core.config import Config, ModelCapabilities, ModelPriority, BackendConfig


# =============================================================================
# Mock Fixtures
# =============================================================================

class MockBackendManager:
    """Mock BackendManager for testing."""

    def __init__(self):
        self.load_calls = []
        self.unload_calls = []
        self._loaded_models = set()  # Track loaded model IDs
        self.load_success = True
        self.unload_success = True

    async def load_model(self, model_id: str, keep_alive: str = "10m") -> bool:
        self.load_calls.append({"model_id": model_id, "keep_alive": keep_alive})
        if self.load_success:
            self._loaded_models.add(model_id)
        return self.load_success

    async def unload_model(self, model_id: str) -> bool:
        self.unload_calls.append(model_id)
        if self.unload_success and model_id in self._loaded_models:
            self._loaded_models.discard(model_id)
        return self.unload_success

    async def list_loaded_models(self, backend_name: str = None) -> List[dict]:
        return [{"name": mid} for mid in self._loaded_models]


class MockProfileManager:
    """Mock ProfileManager for testing."""

    def __init__(self, profile):
        self._profile = profile
        self._original_profile = profile
        self.load_successes = []
        self.load_failures = []
        self.probe_results = []
        self._should_probe = False

    def get_current_profile(self):
        return self._profile

    def get_original_profile(self):
        return self._original_profile

    def record_load_success(self, model_id: str):
        self.load_successes.append(model_id)

    def record_load_failure(self, model_id: str, error: str):
        self.load_failures.append({"model_id": model_id, "error": error})

    def should_probe_recovery(self) -> bool:
        return self._should_probe

    def record_probe_result(self, success: bool, model_id: str):
        self.probe_results.append({"success": success, "model_id": model_id})


class MockProfile:
    """Mock profile with available models."""

    def __init__(self, models: List[ModelCapabilities] = None):
        self.profile_name = "test_profile"
        self.available_models = models or []


def create_model_caps(
    name: str,
    vram_size: float = 10.0,
    priority: str = "NORMAL",
    backend_type: str = "ollama",
    keep_alive: str = "10m",
) -> ModelCapabilities:
    """Helper to create ModelCapabilities."""
    backend = BackendConfig(
        type=backend_type,
        host="http://localhost:11434",
        options={"keep_alive": keep_alive},
    )
    return ModelCapabilities(
        name=name,
        vram_size_gb=vram_size,
        priority=priority,
        backend=backend,
    )


@pytest.fixture
def mock_config():
    """Create mock Config."""
    # Pre-create models for get_model_capabilities lookup
    models = [
        create_model_caps("small-model", vram_size=5.0, priority="LOW"),
        create_model_caps("medium-model", vram_size=10.0, priority="NORMAL"),
        create_model_caps("large-model", vram_size=20.0, priority="HIGH"),
        create_model_caps("critical-model", vram_size=15.0, priority="CRITICAL"),
    ]
    models_by_name = {m.name: m for m in models}

    config = MagicMock(spec=Config)
    config.backends = {
        "ollama": BackendConfig(type="ollama", host="http://localhost:11434"),
    }
    # Make get_model_capabilities return proper ModelCapabilities
    config.get_model_capabilities = MagicMock(side_effect=lambda m: models_by_name.get(m))
    return config


@pytest.fixture
def mock_backend_manager():
    """Create mock BackendManager."""
    return MockBackendManager()


@pytest.fixture
def mock_profile_manager():
    """Create mock ProfileManager with models."""
    models = [
        create_model_caps("small-model", vram_size=5.0, priority="LOW"),
        create_model_caps("medium-model", vram_size=10.0, priority="NORMAL"),
        create_model_caps("large-model", vram_size=20.0, priority="HIGH"),
        create_model_caps("critical-model", vram_size=15.0, priority="CRITICAL"),
    ]
    return MockProfileManager(MockProfile(models))


# =============================================================================
# RAM Detection Tests (via free command)
# =============================================================================

def _make_free_output(total_gb: float, used_gb: float = 0.0) -> str:
    """Helper to generate mock 'free -b' output.

    Args:
        total_gb: Total system RAM in GB (determines vram_limit_gb = total * 0.95)
        used_gb: Currently used RAM in GB (for _get_current_memory_usage_gb)
    """
    total_bytes = int(total_gb * (1024 ** 3))
    used_bytes = int(used_gb * (1024 ** 3))
    free_bytes = total_bytes - used_bytes
    return f"""              total        used        free      shared  buff/cache   available
Mem:    {total_bytes}  {used_bytes}  {free_bytes}  0  0  {free_bytes}
Swap:            0           0           0"""


def test_detect_vram_success(mock_config, mock_backend_manager, mock_profile_manager):
    """_detect_system_vram() parses free command output."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=_make_free_output(128.0),  # 128GB total RAM
        )

        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        # 128GB * 0.95 = 121.6GB (5% reserved for system)
        assert abs(orchestrator._vram_limit_gb - 121.6) < 0.1


def test_detect_vram_multi_gpu(mock_config, mock_backend_manager, mock_profile_manager):
    """_detect_system_vram() parses larger memory systems."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=_make_free_output(256.0),  # 256GB total RAM
        )

        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        # 256GB * 0.95 = 243.2GB
        assert abs(orchestrator._vram_limit_gb - 243.2) < 0.1


def test_detect_vram_free_not_found(mock_config, mock_backend_manager, mock_profile_manager):
    """_detect_system_vram() falls back to 100GB when free not found."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()

        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        assert orchestrator._vram_limit_gb == 100.0


def test_detect_vram_free_timeout(mock_config, mock_backend_manager, mock_profile_manager):
    """_detect_system_vram() falls back on timeout."""
    with patch("subprocess.run") as mock_run:
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("free", 10)

        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        assert orchestrator._vram_limit_gb == 100.0


def test_detect_vram_free_error(mock_config, mock_backend_manager, mock_profile_manager):
    """_detect_system_vram() falls back on free command error."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="error")

        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        assert orchestrator._vram_limit_gb == 100.0


# =============================================================================
# Model State Tests
# =============================================================================

def test_is_loaded_false(mock_config, mock_backend_manager, mock_profile_manager):
    """is_loaded() returns False when model not loaded."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        assert orchestrator.is_loaded("test-model") is False


def test_is_loading_false(mock_config, mock_backend_manager, mock_profile_manager):
    """is_loading() returns False when model not being loaded."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        assert orchestrator.is_loading("test-model") is False


def test_current_usage_empty(mock_config, mock_backend_manager, mock_profile_manager):
    """current_usage_gb returns 0 when no models loaded."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        assert orchestrator.current_usage_gb == 0.0


# =============================================================================
# Request Load Tests
# =============================================================================

async def test_request_load_success(mock_config, mock_backend_manager, mock_profile_manager):
    """request_load() loads model successfully."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))  # 100GB
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        result = await orchestrator.request_load("small-model")

        assert result is True
        assert orchestrator.is_loaded("small-model")
        assert len(mock_backend_manager.load_calls) == 1
        assert mock_profile_manager.load_successes == ["small-model"]


async def test_request_load_already_loaded(mock_config, mock_backend_manager, mock_profile_manager):
    """request_load() updates last_accessed for already loaded model."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        # Load first time
        await orchestrator.request_load("small-model")
        first_access = orchestrator._registry["small-model"].last_accessed

        # Small delay to ensure time difference
        import asyncio
        await asyncio.sleep(0.01)

        # Load again
        await orchestrator.request_load("small-model")
        second_access = orchestrator._registry["small-model"].last_accessed

        # Should have updated last_accessed
        assert second_access >= first_access
        # Only one actual load call
        assert len(mock_backend_manager.load_calls) == 1


async def test_request_load_model_not_in_profile(mock_config, mock_backend_manager, mock_profile_manager):
    """request_load() raises ValueError for model not in profile."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        with pytest.raises(ValueError, match="not in profile"):
            await orchestrator.request_load("unknown-model")

        assert len(mock_profile_manager.load_failures) == 1


async def test_request_load_triggers_eviction(mock_config, mock_backend_manager):
    """request_load() attempts eviction when VRAM full."""
    # Create profile where evictable >= model_size to ensure eviction can succeed
    # Key: the model we're loading must be <= total evictable VRAM
    models = [
        create_model_caps("evictable-model", vram_size=5.0, priority="LOW"),
        create_model_caps("target-model", vram_size=5.0, priority="NORMAL"),
    ]
    profile_manager = MockProfileManager(MockProfile(models))

    with patch("subprocess.run") as mock_run:
        # 8GB limit: to get 8GB limit with 5% reserve, need 8/0.95 = 8.42GB total
        # load evictable (5GB) leaves 3GB free
        # target (5GB) needs eviction: 5+5=10 > 8
        # _evict_for_space(5) called, evictable-model (5GB) >= 5GB, success!
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(8.42))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, profile_manager)

        # Patch _get_current_memory_usage_gb to use registry usage (since mock backend
        # doesn't actually consume system RAM)
        with patch.object(orchestrator, '_get_current_memory_usage_gb',
                          lambda: orchestrator.current_usage_gb):
            await orchestrator.request_load("evictable-model")  # 5GB used, 3GB free
            mock_backend_manager.unload_calls.clear()

            result = await orchestrator.request_load("target-model")

            assert result is True
            assert "evictable-model" in mock_backend_manager.unload_calls


async def test_request_load_eviction_low_priority_first(mock_config, mock_backend_manager):
    """request_load() evicts LOW priority models before NORMAL."""
    # Create profile where:
    # 1. Eviction is triggered (usage + new > limit)
    # 2. LOW priority gets evicted first
    # 3. Total evictable >= model we're loading
    models = [
        create_model_caps("low-priority-model", vram_size=4.0, priority="LOW"),
        create_model_caps("normal-priority-model", vram_size=4.0, priority="NORMAL"),
        create_model_caps("target-model", vram_size=4.0, priority="HIGH"),
    ]
    profile_manager = MockProfileManager(MockProfile(models))

    with patch("subprocess.run") as mock_run:
        # 11GB limit: to get 11GB limit with 5% reserve, need 11/0.95 = 11.58GB total
        # load low (4) + normal (4) = 8GB used, 3GB free
        # target (4GB): 8+4=12 > 11, eviction needed
        # _evict_for_space(4): low (4GB) + normal (4GB) = 8GB evictable >= 4GB needed
        # LOW gets evicted first due to priority sorting
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(11.58))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, profile_manager)

        # Patch _get_current_memory_usage_gb to use registry usage (since mock backend
        # doesn't actually consume system RAM)
        with patch.object(orchestrator, '_get_current_memory_usage_gb',
                          lambda: orchestrator.current_usage_gb):
            await orchestrator.request_load("low-priority-model")
            await orchestrator.request_load("normal-priority-model")

            mock_backend_manager.unload_calls.clear()

            result = await orchestrator.request_load("target-model")

            assert result is True
            # LOW priority should be evicted first
            assert "low-priority-model" in mock_backend_manager.unload_calls
            # NORMAL should still be loaded (only needed to free 4GB, LOW provides 4GB)
            assert orchestrator.is_loaded("normal-priority-model")


async def test_request_load_fails_insufficient_vram(mock_config, mock_backend_manager, mock_profile_manager):
    """request_load() raises MemoryError when can't free enough VRAM."""
    with patch("subprocess.run") as mock_run:
        # 10GB limit: to get 10GB limit with 5% reserve, need 10/0.95 = 10.53GB total
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(10.53))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        # Load critical model (15GB) - but only 10GB available
        # Profile has critical-model at 15GB which won't fit
        with pytest.raises(MemoryError, match="Cannot free"):
            await orchestrator.request_load("large-model")


async def test_request_load_backend_failure(mock_config, mock_backend_manager, mock_profile_manager):
    """request_load() returns False on backend failure."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)
        mock_backend_manager.load_success = False

        result = await orchestrator.request_load("small-model")

        assert result is False
        assert not orchestrator.is_loaded("small-model")
        assert len(mock_profile_manager.load_failures) == 1


# =============================================================================
# Eviction Tests
# =============================================================================

async def test_critical_evicted_only_as_last_resort(mock_config, mock_backend_manager):
    """_evict_for_space() evicts CRITICAL models only when no other option (Phase 2)."""
    # Create profile with both LOW and CRITICAL models
    models = [
        create_model_caps("low-model", vram_size=5.0, priority="LOW"),
        create_model_caps("critical-model", vram_size=15.0, priority="CRITICAL"),
    ]
    profile_manager = MockProfileManager(MockProfile(models))

    with patch("subprocess.run") as mock_run:
        # 25GB limit: to get 25GB with 5% reserve, need 25/0.95 = 26.3GB total
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(26.3))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, profile_manager)

        # Patch _get_current_memory_usage_gb to use registry usage
        with patch.object(orchestrator, '_get_current_memory_usage_gb',
                          lambda: orchestrator.current_usage_gb):
            # Load both models
            await orchestrator.request_load("low-model")
            await orchestrator.request_load("critical-model")
            mock_backend_manager.unload_calls.clear()

            # Request eviction for 5GB - LOW should be evicted first (Phase 1)
            result = await orchestrator._evict_for_space(5.0)

            assert result is True
            assert "low-model" in mock_backend_manager.unload_calls
            # CRITICAL should NOT be evicted when LOW can satisfy the request
            assert "critical-model" not in mock_backend_manager.unload_calls
            assert orchestrator.is_loaded("critical-model")


# =============================================================================
# Unload Tests
# =============================================================================

async def test_unload_model_success(mock_config, mock_backend_manager, mock_profile_manager):
    """unload_model() removes model from registry."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        await orchestrator.request_load("small-model")
        result = await orchestrator.unload_model("small-model")

        assert result is True
        assert not orchestrator.is_loaded("small-model")


async def test_unload_model_not_in_registry(mock_config, mock_backend_manager, mock_profile_manager):
    """unload_model() returns False for model not in registry."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        result = await orchestrator.unload_model("nonexistent")

        assert result is False


async def test_unload_critical_refused(mock_config, mock_backend_manager, mock_profile_manager):
    """unload_model() refuses to unload CRITICAL model."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        await orchestrator.request_load("critical-model")
        result = await orchestrator.unload_model("critical-model")

        assert result is False
        assert orchestrator.is_loaded("critical-model")


# =============================================================================
# Sync Tests
# =============================================================================

async def test_sync_backends_removes_unloaded(mock_config, mock_backend_manager, mock_profile_manager):
    """sync_backends() removes models no longer in backend."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        # Load model
        await orchestrator.request_load("small-model")
        assert orchestrator.is_loaded("small-model")

        # Simulate backend having unloaded it
        mock_backend_manager._loaded_models.clear()

        await orchestrator.sync_backends()

        assert not orchestrator.is_loaded("small-model")


async def test_sync_backends_keeps_loaded(mock_config, mock_backend_manager, mock_profile_manager):
    """sync_backends() keeps models still in backend."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        await orchestrator.request_load("small-model")
        # Model is already in _loaded_models from load_model() call

        await orchestrator.sync_backends()

        assert orchestrator.is_loaded("small-model")


# =============================================================================
# Status Tests
# =============================================================================

async def test_get_status(mock_config, mock_backend_manager, mock_profile_manager):
    """get_status() returns correct status info."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))  # 121.6GB usable (128 * 0.95)
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        await orchestrator.request_load("small-model")

        status = await orchestrator.get_status()

        assert status["used_gb"] == 5.0
        # 128GB * 0.95 = 121.6GB limit
        assert abs(status["limit_gb"] - 121.6) < 0.1
        # Available depends on dynamic memory check, just verify structure
        assert "available_gb" in status
        assert len(status["loaded_models"]) == 1
        assert status["loaded_models"][0]["model_id"] == "small-model"


def test_get_loaded_models(mock_config, mock_backend_manager, mock_profile_manager):
    """get_loaded_models() returns registry copy."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        # Manually add to registry for test
        orchestrator._registry["test"] = LoadedModel(
            model_id="test",
            size_gb=10.0,
            priority=ModelPriority.NORMAL,
            keep_alive_until=datetime.now() + timedelta(minutes=10),
            loaded_at=datetime.now(),
            last_accessed=datetime.now(),
        )

        models = orchestrator.get_loaded_models()

        assert "test" in models
        assert models["test"].model_id == "test"


# =============================================================================
# Duration Parsing Tests
# =============================================================================

def test_parse_duration_minutes(mock_config, mock_backend_manager, mock_profile_manager):
    """_parse_duration_minutes() parses various formats."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        assert orchestrator._parse_duration_minutes("10m") == 10
        assert orchestrator._parse_duration_minutes("1h") == 60
        assert orchestrator._parse_duration_minutes("2h") == 120
        assert orchestrator._parse_duration_minutes("120s") == 2
        assert orchestrator._parse_duration_minutes("30s") == 1  # Rounds up to 1
        assert orchestrator._parse_duration_minutes("15") == 15  # No suffix = minutes


# =============================================================================
# Get Model Tests
# =============================================================================

async def test_get_model_loads_and_returns(mock_config, mock_backend_manager, mock_profile_manager):
    """get_model() ensures model is loaded and returns Strands-compatible Model."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        model = await orchestrator.get_model("small-model", temperature=0.5, max_tokens=2048)

        assert orchestrator.is_loaded("small-model")
        # Model is an ExtendedOllamaModel - verify it was created
        from app.core.models.extended_ollama import ExtendedOllamaModel
        assert isinstance(model, ExtendedOllamaModel)


async def test_get_model_not_in_profile(mock_config, mock_backend_manager, mock_profile_manager):
    """get_model() raises ValueError for unknown model."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        with pytest.raises(ValueError, match="not in profile"):
            await orchestrator.get_model("unknown-model")


# =============================================================================
# get_diffusion_pipeline Tests
# =============================================================================

def create_diffusion_model(
    name: str = "flux2-dev-bnb4bit",
    vram_size: float = 20.0,
    priority: str = "NORMAL",
) -> ModelCapabilities:
    """Helper to create diffusion ModelCapabilities."""
    backend = BackendConfig(type="diffusion", host="local")
    return ModelCapabilities(
        name=name,
        vram_size_gb=vram_size,
        priority=priority,
        backend=backend,
        model_type="diffusion",
    )


async def test_get_diffusion_pipeline_model_not_in_profile(
    mock_config, mock_backend_manager, mock_profile_manager
):
    """get_diffusion_pipeline() raises ValueError for unknown model."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        with pytest.raises(ValueError, match="not in profile"):
            await orchestrator.get_diffusion_pipeline("unknown-diffusion-model")


async def test_get_diffusion_pipeline_not_diffusion_type(
    mock_config, mock_backend_manager, mock_profile_manager
):
    """get_diffusion_pipeline() raises ValueError for non-diffusion model."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend_manager, mock_profile_manager)

        # small-model is LLM type, not diffusion
        with pytest.raises(ValueError, match="not a diffusion model"):
            await orchestrator.get_diffusion_pipeline("small-model")


async def test_get_diffusion_pipeline_backend_not_available(mock_config):
    """get_diffusion_pipeline() raises RuntimeError when backend unavailable."""
    # Add diffusion model to profile
    diffusion_model = create_diffusion_model()
    models = [
        create_model_caps("small-model", vram_size=5.0, priority="LOW"),
        diffusion_model,
    ]
    profile_manager = MockProfileManager(MockProfile(models))

    # Backend manager without diffusion client
    mock_backend = MockBackendManager()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend, profile_manager)
        # Mock get_client to return None for diffusion
        orchestrator._backend_manager.get_client = MagicMock(return_value=None)

        with pytest.raises(RuntimeError, match="Diffusion backend not configured"):
            await orchestrator.get_diffusion_pipeline("flux2-dev-bnb4bit")


async def test_get_diffusion_pipeline_client_no_get_pipeline(mock_config):
    """get_diffusion_pipeline() raises RuntimeError when client lacks get_pipeline."""
    diffusion_model = create_diffusion_model()
    models = [diffusion_model]
    profile_manager = MockProfileManager(MockProfile(models))

    mock_backend = MockBackendManager()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend, profile_manager)

        # Mock client without get_pipeline method
        mock_client = MagicMock(spec=[])  # Empty spec = no methods
        orchestrator._backend_manager.get_client = MagicMock(return_value=mock_client)

        with pytest.raises(RuntimeError, match="does not support get_pipeline"):
            await orchestrator.get_diffusion_pipeline("flux2-dev-bnb4bit")


async def test_get_diffusion_pipeline_pipeline_not_found(mock_config):
    """get_diffusion_pipeline() raises RuntimeError when pipeline is None."""
    diffusion_model = create_diffusion_model()
    models = [diffusion_model]
    profile_manager = MockProfileManager(MockProfile(models))

    mock_backend = MockBackendManager()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend, profile_manager)

        # Mock client with get_pipeline returning None
        mock_client = MagicMock()
        mock_client.get_pipeline.return_value = None
        orchestrator._backend_manager.get_client = MagicMock(return_value=mock_client)

        with pytest.raises(RuntimeError, match="Pipeline for .* not found"):
            await orchestrator.get_diffusion_pipeline("flux2-dev-bnb4bit")


async def test_get_diffusion_pipeline_success(mock_config):
    """get_diffusion_pipeline() loads model and returns pipeline."""
    diffusion_model = create_diffusion_model()
    models = [diffusion_model]
    profile_manager = MockProfileManager(MockProfile(models))

    mock_backend = MockBackendManager()
    mock_backend.load_success = True

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_free_output(128.0))
        orchestrator = VRAMOrchestrator(mock_config, mock_backend, profile_manager)

        # Mock DiffusionClient with get_pipeline
        mock_pipeline = MagicMock()
        mock_client = MagicMock()
        mock_client.get_pipeline.return_value = mock_pipeline
        orchestrator._backend_manager.get_client = MagicMock(return_value=mock_client)

        result = await orchestrator.get_diffusion_pipeline("flux2-dev-bnb4bit")

        assert result == mock_pipeline
        mock_client.get_pipeline.assert_called_with("flux2-dev-bnb4bit")
        # Verify model was loaded
        assert orchestrator.is_loaded("flux2-dev-bnb4bit")
