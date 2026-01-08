"""Unit tests for ModelService."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.model_service import ModelService


@pytest.fixture
def mock_vram_client():
    """Fixture for mocked VRAMClient."""
    return MagicMock()


@pytest.fixture
def model_service(mock_vram_client):
    """Fixture for ModelService with mocked VRAMClient."""
    return ModelService(vram_client=mock_vram_client)


class TestModelService:
    """Tests for ModelService business logic."""

    @pytest.mark.asyncio
    async def test_list_available_models_success(self, model_service, mock_vram_client):
        """Test listing available models."""
        mock_vram_client.list_available_models = AsyncMock(return_value=[
            {
                "name": "qwen2.5:72b",
                "vram_size_gb": 42.5,
                "priority": "HIGH",
                "backend": {"type": "sglang", "endpoint": "http://sglang:5000"},
                "capabilities": ["chat", "completion"]
            }
        ])

        result = await model_service.list_available_models()

        assert len(result) == 1
        assert result[0]["name"] == "qwen2.5:72b"
        mock_vram_client.list_available_models.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_loaded_models_success(self, model_service, mock_vram_client):
        """Test listing loaded models."""
        mock_vram_client.list_models = AsyncMock(return_value={
            "models": [
                {
                    "model_id": "qwen2.5:72b",
                    "vram_size_gb": 42.5,
                    "priority": "HIGH",
                    "backend": "sglang"
                }
            ]
        })

        result = await model_service.list_loaded_models()

        assert len(result) == 1
        assert result[0]["model_id"] == "qwen2.5:72b"
        mock_vram_client.list_models.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.services.model_service.log_admin_action')
    async def test_load_model_success(self, mock_log, model_service, mock_vram_client):
        """Test successful model loading with audit log."""
        mock_vram_client.load_model = AsyncMock(return_value={
            "status": "success",
            "model_id": "qwen2.5:72b"
        })

        result = await model_service.load_model(
            model_id="qwen2.5:72b",
            admin_user="admin123",
            priority="HIGH"
        )

        assert result["status"] == "success"
        assert result["model_id"] == "qwen2.5:72b"
        
        # Verify VRAMClient was called
        mock_vram_client.load_model.assert_called_once_with("qwen2.5:72b", "HIGH")
        
        # Verify audit log was called
        mock_log.assert_called_once()
        log_call = mock_log.call_args[1]
        assert log_call["admin_user"] == "admin123"
        assert log_call["action"] == "model_load"
        assert log_call["result"] == "success"

    @pytest.mark.asyncio
    @patch('app.services.model_service.log_admin_action')
    async def test_load_model_failure(self, mock_log, model_service, mock_vram_client):
        """Test model loading failure with audit log."""
        mock_vram_client.load_model = AsyncMock(
            side_effect=ValueError("Insufficient VRAM")
        )

        with pytest.raises(ValueError) as exc_info:
            await model_service.load_model(
                model_id="qwen2.5:72b",
                admin_user="admin123"
            )
        
        assert "Insufficient VRAM" in str(exc_info.value)
        
        # Verify audit log recorded failure
        mock_log.assert_called_once()
        log_call = mock_log.call_args[1]
        assert log_call["result"].startswith("failure:")

    @pytest.mark.asyncio
    @patch('app.services.model_service.log_admin_action')
    async def test_unload_model_success(self, mock_log, model_service, mock_vram_client):
        """Test successful model unloading."""
        mock_vram_client.unload_model = AsyncMock(return_value={
            "status": "success",
            "model_id": "qwen2.5:72b"
        })

        result = await model_service.unload_model(
            model_id="qwen2.5:72b",
            admin_user="admin123"
        )

        assert result["status"] == "success"
        mock_vram_client.unload_model.assert_called_once_with("qwen2.5:72b")
        
        # Verify audit log
        mock_log.assert_called_once()
        log_call = mock_log.call_args[1]
        assert log_call["action"] == "model_unload"
        assert log_call["result"] == "success"

    @pytest.mark.asyncio
    @patch('app.services.model_service.log_admin_action')
    async def test_emergency_evict_success(self, mock_log, model_service, mock_vram_client):
        """Test successful emergency eviction."""
        mock_vram_client.emergency_evict = AsyncMock(return_value={
            "evicted": True,
            "model_id": "qwen2.5:14b",
            "size_gb": 14.0,
            "reason": None
        })

        result = await model_service.emergency_evict(
            priority="NORMAL",
            admin_user="admin123"
        )

        assert result["evicted"] is True
        assert result["model_id"] == "qwen2.5:14b"
        assert "14.0GB" in result["message"]
        
        mock_vram_client.emergency_evict.assert_called_once_with("NORMAL")
        
        # Verify audit log
        mock_log.assert_called_once()
        log_call = mock_log.call_args[1]
        assert log_call["action"] == "emergency_evict"
        assert log_call["result"] == "success"

    @pytest.mark.asyncio
    @patch('app.services.model_service.log_admin_action')
    async def test_emergency_evict_no_models(self, mock_log, model_service, mock_vram_client):
        """Test emergency eviction when no models available."""
        mock_vram_client.emergency_evict = AsyncMock(return_value={
            "evicted": False,
            "reason": "No models available at NORMAL priority"
        })

        result = await model_service.emergency_evict(
            priority="NORMAL",
            admin_user="admin123"
        )

        assert result["evicted"] is False
        assert "No models" in result["message"]
        
        # Verify audit log recorded "no_models_evicted"
        mock_log.assert_called_once()
        log_call = mock_log.call_args[1]
        assert log_call["result"] == "no_models_evicted"

    @pytest.mark.asyncio
    async def test_get_vram_status_success(self, model_service, mock_vram_client):
        """Test getting VRAM status."""
        mock_vram_client.get_status = AsyncMock(return_value={
            "memory": {"usage_pct": 70.0},
            "healthy": True
        })

        result = await model_service.get_vram_status()

        assert result["healthy"] is True
        assert result["memory"]["usage_pct"] == 70.0
        mock_vram_client.get_status.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.services.model_service.log_admin_action')
    async def test_load_model_generic_error(self, mock_log, model_service, mock_vram_client):
        """Test model loading with generic exception."""
        mock_vram_client.load_model = AsyncMock(
            side_effect=Exception("Network error")
        )

        with pytest.raises(Exception) as exc_info:
            await model_service.load_model(
                model_id="qwen2.5:72b",
                admin_user="admin123"
            )
        
        assert "Network error" in str(exc_info.value)
        
        # Verify audit log recorded error
        mock_log.assert_called_once()
        log_call = mock_log.call_args[1]
        assert log_call["result"].startswith("error:")
