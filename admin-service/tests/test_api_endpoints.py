"""Integration tests for admin API endpoints."""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from jose import jwt
from unittest.mock import AsyncMock, patch, MagicMock

from app.main import app
from app.config import settings


@pytest.fixture
def client():
    """Fixture for FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def admin_token():
    """Fixture for admin JWT token."""
    payload = {
        "user_id": "admin_user_123",
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture
def discord_admin_token():
    """Fixture for Discord admin token."""
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": "discord_admin_456",
        "role_id": "admin_role_789",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "nonce": "test_nonce_123"
    }
    return jwt.encode(payload, settings.BOT_SECRET, algorithm=settings.JWT_ALGORITHM)


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health check endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "admin-service"


class TestModelManagementEndpoints:
    """Tests for model management API endpoints."""

    @patch('app.services.model_service.ModelService.list_available_models')
    def test_list_available_models_success(self, mock_list, client, admin_token):
        """Test listing available models with admin auth."""
        mock_list.return_value = [
            {
                "name": "qwen2.5:72b",
                "vram_size_gb": 42.5,
                "priority": "HIGH",
                "backend": {"type": "sglang", "endpoint": "http://sglang:5000"},
                "capabilities": ["chat", "completion"]
            }
        ]

        response = client.get(
            "/admin/models/list",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["models"]) == 1
        assert data["models"][0]["name"] == "qwen2.5:72b"

    def test_list_available_models_unauthorized(self, client):
        """Test listing models without auth fails."""
        response = client.get("/admin/models/list")
        assert response.status_code == 401

    @patch('app.services.model_service.ModelService.list_loaded_models')
    def test_list_loaded_models_success(self, mock_list, client, admin_token):
        """Test listing loaded models with admin auth."""
        mock_list.return_value = [
            {
                "model_id": "qwen2.5:72b",
                "vram_size_gb": 42.5,
                "priority": "HIGH",
                "backend": "sglang",
                "last_accessed": "2025-12-22T10:30:00Z"
            }
        ]

        response = client.get(
            "/admin/models/loaded",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["models"][0]["is_loaded"] is True

    @patch('app.services.model_service.ModelService.load_model')
    def test_load_model_success(self, mock_load, client, admin_token):
        """Test loading a model."""
        mock_load.return_value = {
            "status": "success",
            "model_id": "qwen2.5:72b",
            "message": "Model loaded successfully",
            "details": {}
        }

        response = client.post(
            "/admin/models/load",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"model_id": "qwen2.5:72b", "priority": "HIGH"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["model_id"] == "qwen2.5:72b"

    @patch('app.services.model_service.ModelService.unload_model')
    def test_unload_model_success(self, mock_unload, client, admin_token):
        """Test unloading a model."""
        mock_unload.return_value = {
            "status": "success",
            "model_id": "qwen2.5:72b",
            "message": "Model unloaded successfully",
            "details": {}
        }

        response = client.post(
            "/admin/models/unload",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"model_id": "qwen2.5:72b"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    @patch('app.services.model_service.ModelService.emergency_evict')
    def test_emergency_evict_success(self, mock_evict, client, admin_token):
        """Test emergency eviction."""
        mock_evict.return_value = {
            "status": "success",
            "evicted": True,
            "model_id": "qwen2.5:14b",
            "size_gb": 14.0,
            "message": "Evicted qwen2.5:14b (14.0GB)"
        }

        response = client.post(
            "/admin/models/evict",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"priority": "NORMAL"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["evicted"] is True
        assert data["model_id"] == "qwen2.5:14b"


class TestVRAMMonitoringEndpoints:
    """Tests for VRAM monitoring API endpoints."""

    @patch('app.clients.vram_client.VRAMClient.get_status')
    def test_get_vram_status_success(self, mock_status, client, admin_token):
        """Test getting VRAM status."""
        mock_status.return_value = {
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

        response = client.get(
            "/admin/vram/status",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["memory"]["usage_pct"] == 70.0
        assert data["healthy"] is True

    @patch('app.clients.vram_client.VRAMClient.get_status')
    def test_get_vram_health_success(self, mock_status, client, admin_token):
        """Test getting VRAM health check."""
        mock_status.return_value = {
            "memory": {
                "usage_pct": 70.0,
                "psi_full_avg10": 2.3,
                "available_gb": 34.5
            },
            "loaded_models": ["model1", "model2"],
            "healthy": True
        }

        response = client.get(
            "/admin/vram/health",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["healthy"] is True
        assert data["usage_pct"] == 70.0
        assert data["loaded_models_count"] == 2


class TestUserManagementEndpoints:
    """Tests for user management API endpoints."""

    @patch('app.services.user_service.UserService.grant_tokens')
    def test_grant_tokens_success(self, mock_grant, client, admin_token):
        """Test granting tokens to a user."""
        mock_grant.return_value = {
            "status": "success",
            "user_id": "user123",
            "tokens_granted": 5000,
            "new_bonus_balance": 10000,
            "message": "Granted 5000 tokens to user123"
        }

        response = client.post(
            "/admin/users/user123/grant-tokens",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"amount": 5000, "reason": "Good behavior"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tokens_granted"] == 5000
        assert data["user_id"] == "user123"

    @patch('app.services.user_service.UserService.ban_user')
    def test_ban_user_success(self, mock_ban, client, admin_token):
        """Test banning a user."""
        mock_ban.return_value = {
            "status": "success",
            "user_id": "user123",
            "message": "User user123 has been banned",
            "reason": "Spam"
        }

        response = client.post(
            "/admin/users/user123/ban",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "Spam"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["user_id"] == "user123"

    @patch('app.services.user_service.UserService.unban_user')
    def test_unban_user_success(self, mock_unban, client, admin_token):
        """Test unbanning a user."""
        mock_unban.return_value = {
            "status": "success",
            "user_id": "user123",
            "message": "User user123 has been unbanned"
        }

        response = client.post(
            "/admin/users/user123/unban",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    @patch('app.services.user_service.UserService.get_user_stats')
    def test_get_user_stats_success(self, mock_stats, client, admin_token):
        """Test getting user stats."""
        mock_stats.return_value = {
            "user_id": "user123",
            "discord_username": "testuser#1234",
            "user_tier": "free",
            "tokens": {
                "weekly_budget": 50000,
                "bonus_tokens": 10000,
                "used_this_week": 15000,
                "remaining": 45000
            },
            "ban_status": {
                "is_banned": False
            }
        }

        response = client.get(
            "/admin/users/user123",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user123"
        assert data["tokens"]["weekly_budget"] == 50000

    @patch('app.services.user_service.UserService.list_all_users')
    def test_list_users_success(self, mock_list, client, admin_token):
        """Test listing all users."""
        mock_list.return_value = {
            "users": [
                {
                    "user_id": "user1",
                    "discord_username": "user1#1234",
                    "user_tier": "free",
                    "tokens_remaining": 45000,
                    "is_banned": False
                }
            ],
            "total": 1,
            "limit": 100,
            "offset": 0,
            "has_more": False
        }

        response = client.get(
            "/admin/users/list?limit=100&offset=0",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["users"]) == 1


class TestDiscordTokenAuth:
    """Tests for Discord token authentication."""

    @patch('app.clients.vram_client.VRAMClient.get_status')
    def test_discord_token_authentication(self, mock_status, client, discord_admin_token):
        """Test that Discord tokens work for API authentication."""
        mock_status.return_value = {"healthy": True, "memory": {}, "loaded_models": []}

        response = client.get(
            "/admin/vram/status",
            headers={"Authorization": f"Bearer {discord_admin_token}"}
        )

        assert response.status_code == 200
