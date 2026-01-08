"""Unit tests for auth middleware."""

import pytest
from datetime import datetime, timedelta, timezone
from jose import jwt
from fastapi import HTTPException

from app.middleware.auth import verify_jwt_token, verify_discord_token
from app.config import settings


class TestJWTVerification:
    """Tests for JWT token verification."""

    def test_valid_jwt_token_admin_role(self):
        """Test valid JWT with admin role."""
        payload = {
            "user_id": "test_user_123",
            "role": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

        result = verify_jwt_token(token)
        assert result["user_id"] == "test_user_123"
        assert result["role"] == "admin"

    def test_jwt_token_non_admin_role(self):
        """Test JWT with non-admin role should fail."""
        payload = {
            "user_id": "test_user_123",
            "role": "user",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token(token)
        assert exc_info.value.status_code == 403
        assert "Admin role required" in str(exc_info.value.detail)

    def test_jwt_token_expired(self):
        """Test expired JWT token should fail."""
        payload = {
            "user_id": "test_user_123",
            "role": "admin",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1)  # Expired
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token(token)
        assert exc_info.value.status_code == 401
        assert "expired" in str(exc_info.value.detail).lower()

    def test_jwt_token_invalid_signature(self):
        """Test JWT with invalid signature should fail."""
        payload = {
            "user_id": "test_user_123",
            "role": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        }
        token = jwt.encode(payload, "wrong_secret", algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token(token)
        assert exc_info.value.status_code == 401

    def test_jwt_token_missing_fields(self):
        """Test JWT missing required fields should fail."""
        payload = {
            "user_id": "test_user_123",
            # Missing 'role' field
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token(token)
        assert exc_info.value.status_code == 401


class TestDiscordTokenVerification:
    """Tests for Discord bot token verification."""

    def test_valid_discord_token(self):
        """Test valid Discord bot token."""
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": "discord_user_456",
            "role_id": "admin_role_789",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "nonce": "random_nonce_123"
        }
        token = jwt.encode(payload, settings.BOT_SECRET, algorithm=settings.JWT_ALGORITHM)

        result = verify_discord_token(token)
        assert result["user_id"] == "discord_user_456"
        assert result["role_id"] == "admin_role_789"

    def test_discord_token_expired(self):
        """Test Discord token older than 5 minutes should fail."""
        old_timestamp = datetime.now(timezone.utc) - timedelta(minutes=10)
        payload = {
            "user_id": "discord_user_456",
            "role_id": "admin_role_789",
            "iat": int(old_timestamp.timestamp()),
            "exp": int((old_timestamp + timedelta(minutes=5)).timestamp()),
            "nonce": "random_nonce_123"
        }
        token = jwt.encode(payload, settings.BOT_SECRET, algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            verify_discord_token(token)
        assert exc_info.value.status_code == 401
        assert "expired" in str(exc_info.value.detail).lower()

    def test_discord_token_invalid_signature(self):
        """Test Discord token with invalid signature should fail."""
        payload = {
            "user_id": "discord_user_456",
            "role_id": "admin_role_789",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nonce": "random_nonce_123"
        }
        token = jwt.encode(payload, "wrong_bot_secret", algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            verify_discord_token(token)
        assert exc_info.value.status_code == 401

    def test_discord_token_missing_fields(self):
        """Test Discord token missing required fields should fail."""
        payload = {
            "user_id": "discord_user_456",
            # Missing 'role_id' field
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nonce": "random_nonce_123"
        }
        token = jwt.encode(payload, settings.BOT_SECRET, algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            verify_discord_token(token)
        assert exc_info.value.status_code == 401


class TestRequireAdmin:
    """Tests for require_admin dependency."""

    @pytest.mark.asyncio
    async def test_require_admin_with_valid_jwt(self):
        """Test require_admin with valid JWT token."""
        from app.middleware.auth import require_admin

        payload = {
            "user_id": "test_user_123",
            "role": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        auth_header = f"Bearer {token}"

        result = await require_admin(authorization=auth_header)
        assert result["user_id"] == "test_user_123"
        assert result["role"] == "admin"

    @pytest.mark.asyncio
    async def test_require_admin_with_valid_discord_token(self):
        """Test require_admin with valid Discord token."""
        from app.middleware.auth import require_admin

        now = datetime.now(timezone.utc)
        payload = {
            "user_id": "discord_user_456",
            "role_id": "admin_role_789",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "nonce": "random_nonce_123"
        }
        token = jwt.encode(payload, settings.BOT_SECRET, algorithm=settings.JWT_ALGORITHM)
        auth_header = f"Bearer {token}"

        result = await require_admin(authorization=auth_header)
        assert result["user_id"] == "discord_user_456"
        assert result["role_id"] == "admin_role_789"

    @pytest.mark.asyncio
    async def test_require_admin_missing_authorization_header(self):
        """Test require_admin without authorization header."""
        from app.middleware.auth import require_admin

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(authorization=None)
        assert exc_info.value.status_code == 401
        assert "Missing Authorization header" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_require_admin_invalid_bearer_format(self):
        """Test require_admin with invalid Bearer format."""
        from app.middleware.auth import require_admin

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(authorization="InvalidFormat token123")
        assert exc_info.value.status_code == 401
        assert "Invalid Authorization header" in str(exc_info.value.detail)
