"""Unit tests for VRAMClient."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.clients.vram_client import VRAMClient


@pytest.fixture
def vram_client():
    """Fixture for VRAMClient instance."""
    return VRAMClient(base_url="http://test-service:8000", api_key="test_api_key")


class TestVRAMClient:
    """Tests for VRAMClient HTTP methods."""

    @pytest.mark.asyncio
    async def test_get_status_success(self, vram_client):
        """Test successful VRAM status retrieval."""
        mock_response = {
            "memory": {
                "total_gb": 115.0,
                "used_gb": 80.5,
                "available_gb": 34.5,
                "usage_pct": 70.0,
                "psi_some_avg10": 10.5,
                "psi_full_avg10": 2.3
            },
            "loaded_models": ["model1", "model2"],
            "healthy": True
        }

        with patch.object(vram_client.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_get.return_value.raise_for_status = MagicMock()

            result = await vram_client.get_status()

            assert result == mock_response
            assert result["memory"]["usage_pct"] == 70.0
            assert result["healthy"] is True
            mock_get.assert_called_once_with(
                "http://test-service:8000/internal/vram/status",
                headers={"X-Internal-API-Key": "test_api_key", "Content-Type": "application/json"}
            )

    @pytest.mark.asyncio
    async def test_list_models_success(self, vram_client):
        """Test successful model listing."""
        mock_response = {
            "models": [
                {
                    "model_id": "qwen2.5:72b",
                    "backend": "sglang",
                    "vram_size_gb": 42.5,
                    "priority": "HIGH",
                    "last_accessed": "2025-12-22T10:30:00Z",
                    "is_external": True
                }
            ]
        }

        with patch.object(vram_client.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_get.return_value.raise_for_status = MagicMock()

            result = await vram_client.list_models()

            assert result == mock_response
            assert len(result["models"]) == 1
            assert result["models"][0]["model_id"] == "qwen2.5:72b"

    @pytest.mark.asyncio
    async def test_list_available_models_success(self, vram_client):
        """Test successful available models listing."""
        mock_response = {
            "models": [
                {
                    "name": "qwen2.5:72b",
                    "vram_size_gb": 42.5,
                    "priority": "HIGH",
                    "backend": {"type": "sglang", "endpoint": "http://sglang:5000"},
                    "capabilities": ["chat", "completion"]
                }
            ]
        }

        with patch.object(vram_client.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_get.return_value.raise_for_status = MagicMock()

            result = await vram_client.list_available_models()

            assert result == mock_response["models"]
            assert len(result) == 1
            assert result[0]["name"] == "qwen2.5:72b"

    @pytest.mark.asyncio
    async def test_load_model_success(self, vram_client):
        """Test successful model loading."""
        mock_response = {
            "status": "success",
            "model_id": "qwen2.5:72b",
            "message": "Model loaded successfully"
        }

        with patch.object(vram_client.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = MagicMock()

            result = await vram_client.load_model("qwen2.5:72b", priority="HIGH")

            assert result["status"] == "success"
            assert result["model_id"] == "qwen2.5:72b"
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]["json"]["model_id"] == "qwen2.5:72b"
            assert call_args[1]["json"]["priority"] == "HIGH"

    @pytest.mark.asyncio
    async def test_load_model_failure(self, vram_client):
        """Test model loading failure with HTTP error."""
        error_detail = {"detail": "Insufficient VRAM"}

        with patch.object(vram_client.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock(
                status_code=400,
                content=b'{"detail": "Insufficient VRAM"}',
                json=lambda: error_detail
            )
            mock_post.return_value = mock_response
            mock_post.return_value.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError("Bad Request", request=MagicMock(), response=mock_response)
            )

            with pytest.raises(ValueError) as exc_info:
                await vram_client.load_model("qwen2.5:72b")
            
            assert "Insufficient VRAM" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unload_model_success(self, vram_client):
        """Test successful model unloading."""
        mock_response = {
            "status": "success",
            "model_id": "qwen2.5:72b",
            "message": "Model unloaded successfully"
        }

        with patch.object(vram_client.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = MagicMock()

            result = await vram_client.unload_model("qwen2.5:72b")

            assert result["status"] == "success"
            assert result["model_id"] == "qwen2.5:72b"

    @pytest.mark.asyncio
    async def test_emergency_evict_success(self, vram_client):
        """Test successful emergency eviction."""
        mock_response = {
            "evicted": True,
            "model_id": "qwen2.5:14b",
            "size_gb": 14.0,
            "reason": None
        }

        with patch.object(vram_client.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = MagicMock()

            result = await vram_client.emergency_evict("NORMAL")

            assert result["evicted"] is True
            assert result["model_id"] == "qwen2.5:14b"
            assert result["size_gb"] == 14.0

    @pytest.mark.asyncio
    async def test_emergency_evict_no_models(self, vram_client):
        """Test emergency eviction when no models available."""
        mock_response = {
            "evicted": False,
            "reason": "No models available at NORMAL priority"
        }

        with patch.object(vram_client.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = MagicMock()

            result = await vram_client.emergency_evict("NORMAL")

            assert result["evicted"] is False
            assert "No models available" in result["reason"]
