"""Tests for BackendManager and backend clients.

Tests cover:
- OllamaClient: load_model, unload_model, list_loaded, health_check
- SGLangClient: state tracking, health_check
- VLLMClient: state tracking, health_check
- BackendManager: client initialization, model management, SSH operations
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.services.backend_manager import (
    OllamaClient,
    SGLangClient,
    VLLMClient,
    BackendManager,
    IBackendClient,
)
from app.core.config import Config, BackendConfig


# =============================================================================
# Mock Fixtures
# =============================================================================

class MockResponse:
    """Mock aiohttp response."""

    def __init__(self, status: int, json_data: Dict[str, Any] = None, text: str = ""):
        self.status = status
        self._json_data = json_data or {}
        self._text = text

    async def json(self):
        return self._json_data

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockSession:
    """Mock aiohttp ClientSession."""

    def __init__(self, response: MockResponse = None):
        self._response = response or MockResponse(200)
        self.closed = False
        self.post_calls = []
        self.get_calls = []

    def post(self, url, json=None, **kwargs):
        self.post_calls.append({"url": url, "json": json, "kwargs": kwargs})
        return self._response

    def get(self, url, **kwargs):
        self.get_calls.append({"url": url, "kwargs": kwargs})
        return self._response

    async def close(self):
        self.closed = True


@pytest.fixture
def mock_config():
    """Create mock Config with backends."""
    config = MagicMock(spec=Config)
    config.backends = {
        "ollama": BackendConfig(
            type="ollama",
            host="http://localhost:11434",
            dgx_script=None,
        ),
        "sglang": BackendConfig(
            type="sglang",
            host="http://localhost:30000",
            dgx_script="/path/to/sglang-start.sh",
        ),
    }
    config.dgx_config = {
        "host": "dgx.local",
        "user": "testuser",
        "ssh_key": "/path/to/key",
    }
    config.get_backend_for_model = MagicMock(return_value=config.backends["ollama"])
    return config


# =============================================================================
# OllamaClient Tests
# =============================================================================

async def test_ollama_load_model_success():
    """OllamaClient.load_model() sends correct request."""
    client = OllamaClient("http://localhost:11434")
    mock_session = MockSession(MockResponse(200))
    client._session = mock_session

    result = await client.load_model("llama3:8b", keep_alive="15m")

    assert result is True
    assert len(mock_session.post_calls) == 1
    call = mock_session.post_calls[0]
    assert call["url"] == "http://localhost:11434/api/generate"
    assert call["json"]["model"] == "llama3:8b"
    assert call["json"]["keep_alive"] == "15m"


async def test_ollama_load_model_failure():
    """OllamaClient.load_model() returns False on error."""
    client = OllamaClient("http://localhost:11434")
    mock_session = MockSession(MockResponse(500, text="Internal error"))
    client._session = mock_session

    result = await client.load_model("bad-model")

    assert result is False


async def test_ollama_unload_model():
    """OllamaClient.unload_model() sets keep_alive to 0."""
    client = OllamaClient("http://localhost:11434")
    mock_session = MockSession(MockResponse(200))
    client._session = mock_session

    result = await client.unload_model("llama3:8b")

    assert result is True
    call = mock_session.post_calls[0]
    assert call["json"]["keep_alive"] == "0"


async def test_ollama_list_loaded():
    """OllamaClient.list_loaded() returns model list."""
    client = OllamaClient("http://localhost:11434")
    models_data = {"models": [{"name": "llama3:8b"}, {"name": "mistral:7b"}]}
    mock_session = MockSession(MockResponse(200, models_data))
    client._session = mock_session

    result = await client.list_loaded()

    assert len(result) == 2
    assert result[0]["name"] == "llama3:8b"


async def test_ollama_list_loaded_empty():
    """OllamaClient.list_loaded() returns empty list on error."""
    client = OllamaClient("http://localhost:11434")
    mock_session = MockSession(MockResponse(500))
    client._session = mock_session

    result = await client.list_loaded()

    assert result == []


async def test_ollama_health_check_success():
    """OllamaClient.health_check() returns True when healthy."""
    client = OllamaClient("http://localhost:11434")
    mock_session = MockSession(MockResponse(200))
    client._session = mock_session

    result = await client.health_check()

    assert result is True
    assert mock_session.get_calls[0]["url"] == "http://localhost:11434/api/tags"


async def test_ollama_health_check_failure():
    """OllamaClient.health_check() returns False on error."""
    client = OllamaClient("http://localhost:11434")
    mock_session = MockSession(MockResponse(503))
    client._session = mock_session

    result = await client.health_check()

    assert result is False


async def test_ollama_close_session():
    """OllamaClient.close() closes the session."""
    client = OllamaClient("http://localhost:11434")
    mock_session = MockSession()
    client._session = mock_session

    await client.close()

    assert mock_session.closed is True


async def test_ollama_host_trailing_slash_removed():
    """OllamaClient removes trailing slash from host."""
    client = OllamaClient("http://localhost:11434/")

    assert client.host == "http://localhost:11434"


# =============================================================================
# SGLangClient Tests
# =============================================================================

async def test_sglang_load_model_tracks_state():
    """SGLangClient.load_model() tracks model state."""
    client = SGLangClient("http://localhost:30000")

    result = await client.load_model("deepseek-coder")

    assert result is True
    assert client._loaded_model == "deepseek-coder"


async def test_sglang_unload_model_clears_state():
    """SGLangClient.unload_model() clears model state."""
    client = SGLangClient("http://localhost:30000")
    client._loaded_model = "deepseek-coder"

    result = await client.unload_model("deepseek-coder")

    assert result is True
    assert client._loaded_model is None


async def test_sglang_unload_model_wrong_model():
    """SGLangClient.unload_model() ignores wrong model ID."""
    client = SGLangClient("http://localhost:30000")
    client._loaded_model = "deepseek-coder"

    result = await client.unload_model("other-model")

    assert result is True
    assert client._loaded_model == "deepseek-coder"


async def test_sglang_list_loaded_with_model():
    """SGLangClient.list_loaded() returns loaded model."""
    client = SGLangClient("http://localhost:30000")
    client._loaded_model = "deepseek-coder"

    result = await client.list_loaded()

    assert len(result) == 1
    assert result[0]["name"] == "deepseek-coder"
    assert result[0]["backend"] == "sglang"


async def test_sglang_list_loaded_empty():
    """SGLangClient.list_loaded() returns empty when no model."""
    client = SGLangClient("http://localhost:30000")

    result = await client.list_loaded()

    assert result == []


async def test_sglang_health_check_success():
    """SGLangClient.health_check() returns True when healthy."""
    client = SGLangClient("http://localhost:30000")
    mock_session = MockSession(MockResponse(200))
    client._session = mock_session

    result = await client.health_check()

    assert result is True
    assert mock_session.get_calls[0]["url"] == "http://localhost:30000/health"


async def test_sglang_health_check_failure():
    """SGLangClient.health_check() returns False on error."""
    client = SGLangClient("http://localhost:30000")
    mock_session = MockSession(MockResponse(503))
    client._session = mock_session

    result = await client.health_check()

    assert result is False


# =============================================================================
# VLLMClient Tests
# =============================================================================

async def test_vllm_load_model_tracks_state():
    """VLLMClient.load_model() tracks model state."""
    client = VLLMClient("http://localhost:8000")

    result = await client.load_model("llama-2-70b")

    assert result is True
    assert client._loaded_model == "llama-2-70b"


async def test_vllm_unload_model_clears_state():
    """VLLMClient.unload_model() clears model state."""
    client = VLLMClient("http://localhost:8000")
    client._loaded_model = "llama-2-70b"

    result = await client.unload_model("llama-2-70b")

    assert result is True
    assert client._loaded_model is None


async def test_vllm_list_loaded():
    """VLLMClient.list_loaded() returns loaded model."""
    client = VLLMClient("http://localhost:8000")
    client._loaded_model = "llama-2-70b"

    result = await client.list_loaded()

    assert len(result) == 1
    assert result[0]["name"] == "llama-2-70b"
    assert result[0]["backend"] == "vllm"


async def test_vllm_health_check():
    """VLLMClient.health_check() checks /health endpoint."""
    client = VLLMClient("http://localhost:8000")
    mock_session = MockSession(MockResponse(200))
    client._session = mock_session

    result = await client.health_check()

    assert result is True
    assert mock_session.get_calls[0]["url"] == "http://localhost:8000/health"


# =============================================================================
# BackendManager Tests
# =============================================================================

def test_backend_manager_init_creates_clients(mock_config):
    """BackendManager._init_clients() creates appropriate clients."""
    manager = BackendManager(mock_config)

    assert "ollama" in manager._clients
    assert "sglang" in manager._clients
    assert isinstance(manager._clients["ollama"], OllamaClient)
    assert isinstance(manager._clients["sglang"], SGLangClient)


def test_backend_manager_create_client_unknown_type(mock_config):
    """BackendManager._create_client() returns None for unknown type."""
    manager = BackendManager(mock_config)
    unknown_config = BackendConfig(type="unknown", host="http://localhost:9999")

    result = manager._create_client(unknown_config)

    assert result is None


async def test_backend_manager_health_check(mock_config):
    """BackendManager.health_check() delegates to client."""
    manager = BackendManager(mock_config)
    mock_client = AsyncMock(spec=IBackendClient)
    mock_client.health_check.return_value = True
    manager._clients["ollama"] = mock_client

    result = await manager.health_check("ollama")

    assert result is True
    mock_client.health_check.assert_called_once()


async def test_backend_manager_health_check_not_found(mock_config):
    """BackendManager.health_check() returns False for unknown backend."""
    manager = BackendManager(mock_config)

    result = await manager.health_check("nonexistent")

    assert result is False


async def test_backend_manager_load_model(mock_config):
    """BackendManager.load_model() routes to correct client."""
    manager = BackendManager(mock_config)
    mock_client = AsyncMock(spec=IBackendClient)
    mock_client.load_model.return_value = True
    manager._clients["ollama"] = mock_client

    result = await manager.load_model("llama3:8b", "10m")

    assert result is True
    mock_client.load_model.assert_called_once_with("llama3:8b", "10m")


async def test_backend_manager_load_model_no_backend(mock_config):
    """BackendManager.load_model() returns False when no backend found."""
    mock_config.get_backend_for_model.return_value = None
    manager = BackendManager(mock_config)

    result = await manager.load_model("unknown-model")

    assert result is False


async def test_backend_manager_unload_model(mock_config):
    """BackendManager.unload_model() routes to correct client."""
    manager = BackendManager(mock_config)
    mock_client = AsyncMock(spec=IBackendClient)
    mock_client.unload_model.return_value = True
    manager._clients["ollama"] = mock_client

    result = await manager.unload_model("llama3:8b")

    assert result is True
    mock_client.unload_model.assert_called_once_with("llama3:8b")


async def test_backend_manager_list_loaded_models_all(mock_config):
    """BackendManager.list_loaded_models() aggregates all backends."""
    manager = BackendManager(mock_config)
    mock_ollama = AsyncMock(spec=IBackendClient)
    mock_ollama.list_loaded.return_value = [{"name": "llama3:8b"}]
    mock_sglang = AsyncMock(spec=IBackendClient)
    mock_sglang.list_loaded.return_value = [{"name": "deepseek"}]
    manager._clients = {"ollama": mock_ollama, "sglang": mock_sglang}

    result = await manager.list_loaded_models()

    assert len(result) == 2
    backend_names = {m["backend_name"] for m in result}
    assert backend_names == {"ollama", "sglang"}


async def test_backend_manager_list_loaded_models_specific(mock_config):
    """BackendManager.list_loaded_models() can query specific backend."""
    manager = BackendManager(mock_config)
    mock_client = AsyncMock(spec=IBackendClient)
    mock_client.list_loaded.return_value = [{"name": "llama3:8b"}]
    manager._clients["ollama"] = mock_client

    result = await manager.list_loaded_models("ollama")

    assert len(result) == 1
    assert result[0]["backend_name"] == "ollama"


async def test_backend_manager_list_loaded_models_unknown_backend(mock_config):
    """BackendManager.list_loaded_models() returns empty for unknown backend."""
    manager = BackendManager(mock_config)

    result = await manager.list_loaded_models("nonexistent")

    assert result == []


def test_backend_manager_get_client(mock_config):
    """BackendManager.get_client() returns client by name."""
    manager = BackendManager(mock_config)

    client = manager.get_client("ollama")

    assert isinstance(client, OllamaClient)


def test_backend_manager_get_client_not_found(mock_config):
    """BackendManager.get_client() returns None for unknown name."""
    manager = BackendManager(mock_config)

    client = manager.get_client("nonexistent")

    assert client is None


async def test_backend_manager_close(mock_config):
    """BackendManager.close() closes all clients."""
    manager = BackendManager(mock_config)
    mock_client = AsyncMock()
    manager._clients["ollama"] = mock_client

    await manager.close()

    mock_client.close.assert_called_once()


# =============================================================================
# SSH/DGX Tests (mocked)
# =============================================================================

async def test_backend_manager_start_backend_no_script(mock_config):
    """BackendManager.start_backend() fails without dgx_script."""
    mock_config.backends["ollama"].dgx_script = None
    manager = BackendManager(mock_config)

    result = await manager.start_backend("ollama")

    assert result is False


async def test_backend_manager_start_backend_not_found(mock_config):
    """BackendManager.start_backend() fails for unknown backend."""
    manager = BackendManager(mock_config)

    result = await manager.start_backend("nonexistent")

    assert result is False


async def test_backend_manager_stop_backend_no_script(mock_config):
    """BackendManager.stop_backend() fails without dgx_script."""
    mock_config.backends["ollama"].dgx_script = None
    manager = BackendManager(mock_config)

    result = await manager.stop_backend("ollama")

    assert result is False


async def test_backend_manager_ssh_no_config(mock_config):
    """BackendManager._get_ssh() returns None without DGX config."""
    mock_config.dgx_config = None
    manager = BackendManager(mock_config)

    result = await manager._get_ssh()

    assert result is None


async def test_backend_manager_ssh_incomplete_config(mock_config):
    """BackendManager._get_ssh() returns None with incomplete config."""
    mock_config.dgx_config = {"host": "dgx.local"}  # missing user and ssh_key
    manager = BackendManager(mock_config)

    result = await manager._get_ssh()

    assert result is None


# =============================================================================
# DiffusionClient Tests
# =============================================================================

from app.services.backend_manager import DiffusionClient


async def test_diffusion_load_model_already_loaded():
    """DiffusionClient.load_model() returns True for already loaded model."""
    client = DiffusionClient()
    client._pipelines["flux2-dev-bnb4bit"] = MagicMock()  # Simulate loaded

    result = await client.load_model("flux2-dev-bnb4bit")

    assert result is True


async def test_diffusion_load_model_success():
    """DiffusionClient.load_model() loads pipeline successfully."""
    client = DiffusionClient()
    mock_pipeline = MagicMock()

    with patch.object(client, '_load_diffusion_pipeline', return_value=mock_pipeline):
        result = await client.load_model("flux2-dev-bnb4bit")

    assert result is True
    assert "flux2-dev-bnb4bit" in client._pipelines
    assert client._pipelines["flux2-dev-bnb4bit"] == mock_pipeline


async def test_diffusion_load_model_failure():
    """DiffusionClient.load_model() returns False on error."""
    client = DiffusionClient()

    with patch.object(client, '_load_diffusion_pipeline', side_effect=ValueError("Unknown")):
        result = await client.load_model("unknown-model")

    assert result is False
    assert "unknown-model" not in client._pipelines


async def test_diffusion_unload_model_success():
    """DiffusionClient.unload_model() removes pipeline and clears cache."""
    client = DiffusionClient()
    client._pipelines["flux2-dev-bnb4bit"] = MagicMock()

    with patch("torch.cuda.empty_cache") as mock_cache:
        result = await client.unload_model("flux2-dev-bnb4bit")

    assert result is True
    assert "flux2-dev-bnb4bit" not in client._pipelines
    mock_cache.assert_called_once()


async def test_diffusion_unload_model_not_loaded():
    """DiffusionClient.unload_model() returns True for non-loaded model."""
    client = DiffusionClient()

    result = await client.unload_model("not-loaded")

    assert result is True


async def test_diffusion_list_loaded():
    """DiffusionClient.list_loaded() returns loaded pipelines."""
    client = DiffusionClient()
    client._pipelines["flux2-dev-bnb4bit"] = MagicMock()
    client._pipelines["sd-xl"] = MagicMock()

    result = await client.list_loaded()

    assert len(result) == 2
    names = [m["name"] for m in result]
    assert "flux2-dev-bnb4bit" in names
    assert "sd-xl" in names
    for m in result:
        assert m["backend"] == "diffusion"


async def test_diffusion_list_loaded_empty():
    """DiffusionClient.list_loaded() returns empty list when none loaded."""
    client = DiffusionClient()

    result = await client.list_loaded()

    assert result == []


async def test_diffusion_health_check():
    """DiffusionClient.health_check() always returns True (in-process)."""
    client = DiffusionClient()

    result = await client.health_check()

    assert result is True


def test_diffusion_get_pipeline_loaded():
    """DiffusionClient.get_pipeline() returns loaded pipeline."""
    client = DiffusionClient()
    mock_pipe = MagicMock()
    client._pipelines["flux2-dev-bnb4bit"] = mock_pipe

    result = client.get_pipeline("flux2-dev-bnb4bit")

    assert result == mock_pipe


def test_diffusion_get_pipeline_not_loaded():
    """DiffusionClient.get_pipeline() returns None for non-loaded model."""
    client = DiffusionClient()

    result = client.get_pipeline("not-loaded")

    assert result is None


def test_backend_manager_creates_diffusion_client(mock_config):
    """BackendManager creates DiffusionClient for diffusion backend."""
    mock_config.backends["diffusion"] = BackendConfig(type="diffusion", host="local")
    manager = BackendManager(mock_config)

    assert "diffusion" in manager._clients
    assert isinstance(manager._clients["diffusion"], DiffusionClient)
