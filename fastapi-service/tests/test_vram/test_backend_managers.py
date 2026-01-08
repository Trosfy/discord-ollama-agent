"""Tests for backend managers."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.vram.backend_managers import (
    OllamaBackendManager,
    TensorRTBackendManager,
    vLLMBackendManager,
    CompositeBackendManager
)
from app.services.vram.interfaces import BackendType


@pytest.mark.asyncio
async def test_ollama_backend_supports():
    """Test OllamaBackendManager supports Ollama backend."""
    manager = OllamaBackendManager()

    assert manager.supports(BackendType.OLLAMA)
    assert not manager.supports(BackendType.TENSORRT)
    assert not manager.supports(BackendType.VLLM)


@pytest.mark.asyncio
async def test_ollama_backend_unload():
    """Test OllamaBackendManager unload calls force_unload_model."""
    manager = OllamaBackendManager()

    with patch('app.services.vram.backend_managers.force_unload_model', new_callable=AsyncMock) as mock_unload:
        await manager.unload("test-model", BackendType.OLLAMA)

        # Should have called force_unload_model
        mock_unload.assert_called_once_with("test-model")


@pytest.mark.asyncio
async def test_ollama_backend_wrong_type():
    """Test OllamaBackendManager raises error for wrong backend type."""
    manager = OllamaBackendManager()

    with pytest.raises(ValueError, match="doesn't support"):
        await manager.unload("test-model", BackendType.TENSORRT)


@pytest.mark.asyncio
async def test_tensorrt_backend_supports():
    """Test TensorRTBackendManager supports TensorRT backend."""
    manager = TensorRTBackendManager()

    assert manager.supports(BackendType.TENSORRT)
    assert not manager.supports(BackendType.OLLAMA)
    assert not manager.supports(BackendType.VLLM)


@pytest.mark.asyncio
async def test_vllm_backend_supports():
    """Test vLLMBackendManager supports vLLM backend."""
    manager = vLLMBackendManager()

    assert manager.supports(BackendType.VLLM)
    assert not manager.supports(BackendType.OLLAMA)
    assert not manager.supports(BackendType.TENSORRT)


@pytest.mark.asyncio
async def test_composite_manager_delegates_to_ollama():
    """Test CompositeBackendManager delegates to OllamaBackendManager."""
    manager = CompositeBackendManager()

    with patch('app.services.vram.backend_managers.force_unload_model', new_callable=AsyncMock) as mock_unload:
        await manager.unload("test-model", BackendType.OLLAMA)

        # Should have delegated to OllamaBackendManager
        mock_unload.assert_called_once_with("test-model")


@pytest.mark.asyncio
async def test_composite_manager_supports_all():
    """Test CompositeBackendManager supports all backend types."""
    manager = CompositeBackendManager()

    assert manager.supports(BackendType.OLLAMA)
    assert manager.supports(BackendType.TENSORRT)
    assert manager.supports(BackendType.VLLM)


@pytest.mark.asyncio
async def test_composite_manager_unsupported_backend():
    """Test CompositeBackendManager raises error for unsupported backend."""
    manager = CompositeBackendManager()

    # Create a mock backend type that's not supported
    with pytest.raises(ValueError, match="No backend manager found"):
        await manager.unload("test-model", "unknown-backend")


@pytest.mark.asyncio
async def test_ollama_cleanup_shared_memory():
    """Test Ollama cleanup removes shared memory segments."""
    manager = OllamaBackendManager()

    with patch('subprocess.run') as mock_run:
        # Mock ipcs output
        mock_run.return_value = Mock(
            returncode=0,
            stdout="12345\n67890\n"
        )

        await manager.cleanup(BackendType.OLLAMA)

        # Should have called ipcrm for each segment
        assert mock_run.call_count >= 2  # ipcs + ipcrm calls
