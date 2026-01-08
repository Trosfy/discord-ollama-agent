"""Unit tests for UserService.

Tests demonstrate Dependency Inversion Principle:
- UserService depends on IUserRepository interface (not concrete implementation)
- Tests use mock repository instead of mocking DynamoDB directly
- Easy to swap implementations (DynamoDB, PostgreSQL, in-memory, etc.)
- Much simpler tests - no complex async context manager mocking
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.user_service import UserService


@pytest.fixture
def mock_user_repository():
    """Fixture for mocked user repository (IUserRepository)."""
    return MagicMock()


@pytest.fixture
def user_service(mock_user_repository):
    """Fixture for UserService with mocked repository."""
    return UserService(user_repository=mock_user_repository)


class TestUserServiceGrantTokens:
    """Tests for grant_tokens functionality."""

    @pytest.mark.asyncio
    @patch('app.services.user_service.log_admin_action')
    async def test_grant_tokens_success(self, mock_log, user_service, mock_user_repository):
        """Test successful token granting with mock repository."""
        # Mock repository responses
        mock_user_repository.grant_tokens = AsyncMock(return_value=True)
        mock_user_repository.get_user = AsyncMock(return_value={
            'user_id': 'user123',
            'bonus_tokens': 15000  # After granting 10000 to initial 5000
        })

        result = await user_service.grant_tokens(
            user_id="user123",
            amount=10000,
            admin_user="admin456",
            reason="Good behavior"
        )

        assert result["status"] == "success"
        assert result["user_id"] == "user123"
        assert result["tokens_granted"] == 10000
        assert result["new_bonus_balance"] == 15000

        # Verify repository methods were called correctly
        mock_user_repository.grant_tokens.assert_called_once_with(
            user_id="user123",
            amount=10000,
            reason="Good behavior",
            admin_user="admin456"
        )
        mock_user_repository.get_user.assert_called_once_with("user123")

        # Verify audit log
        mock_log.assert_called_once()
        log_call = mock_log.call_args[1]
        assert log_call["admin_user"] == "admin456"
        assert log_call["action"] == "grant_tokens"
        assert log_call["result"] == "success"

    @pytest.mark.asyncio
    @patch('app.services.user_service.log_admin_action')
    async def test_grant_tokens_repository_failure(self, mock_log, user_service, mock_user_repository):
        """Test token granting when repository fails."""
        # Repository returns False (failure)
        mock_user_repository.grant_tokens = AsyncMock(return_value=False)

        with pytest.raises(ValueError) as exc_info:
            await user_service.grant_tokens(
                user_id="user123",
                amount=10000,
                admin_user="admin456"
            )

        assert "Failed to grant tokens" in str(exc_info.value)

        # Verify audit log recorded failure
        mock_log.assert_called_once()
        log_call = mock_log.call_args[1]
        assert log_call["result"].startswith("failure:")


class TestUserServiceBanUnban:
    """Tests for ban/unban functionality."""

    @pytest.mark.asyncio
    @patch('app.services.user_service.log_admin_action')
    async def test_ban_user_success(self, mock_log, user_service, mock_user_repository):
        """Test successful user ban with mock repository."""
        mock_user_repository.ban_user = AsyncMock(return_value=True)

        result = await user_service.ban_user(
            user_id="user123",
            admin_user="admin456",
            reason="Spam"
        )

        assert result["status"] == "success"
        assert result["user_id"] == "user123"
        assert result["reason"] == "Spam"

        # Verify repository was called
        mock_user_repository.ban_user.assert_called_once_with(
            user_id="user123",
            reason="Spam",
            admin_user="admin456"
        )

        # Verify audit log
        mock_log.assert_called_once()
        log_call = mock_log.call_args[1]
        assert log_call["action"] == "ban_user"
        assert log_call["result"] == "success"

    @pytest.mark.asyncio
    @patch('app.services.user_service.log_admin_action')
    async def test_ban_user_repository_failure(self, mock_log, user_service, mock_user_repository):
        """Test user ban when repository fails."""
        mock_user_repository.ban_user = AsyncMock(return_value=False)

        with pytest.raises(ValueError) as exc_info:
            await user_service.ban_user(
                user_id="user123",
                admin_user="admin456",
                reason="Spam"
            )

        assert "Failed to ban" in str(exc_info.value)

        # Verify audit log recorded failure
        mock_log.assert_called_once()
        log_call = mock_log.call_args[1]
        assert log_call["result"].startswith("failure:")

    @pytest.mark.asyncio
    @patch('app.services.user_service.log_admin_action')
    async def test_unban_user_success(self, mock_log, user_service, mock_user_repository):
        """Test successful user unban with mock repository."""
        mock_user_repository.unban_user = AsyncMock(return_value=True)

        result = await user_service.unban_user(
            user_id="user123",
            admin_user="admin456"
        )

        assert result["status"] == "success"
        assert result["user_id"] == "user123"

        # Verify repository was called
        mock_user_repository.unban_user.assert_called_once_with(
            user_id="user123",
            admin_user="admin456"
        )

        # Verify audit log
        mock_log.assert_called_once()
        log_call = mock_log.call_args[1]
        assert log_call["action"] == "unban_user"
        assert log_call["result"] == "success"

    @pytest.mark.asyncio
    @patch('app.services.user_service.log_admin_action')
    async def test_unban_user_repository_failure(self, mock_log, user_service, mock_user_repository):
        """Test user unban when repository fails."""
        mock_user_repository.unban_user = AsyncMock(return_value=False)

        with pytest.raises(ValueError) as exc_info:
            await user_service.unban_user(
                user_id="user123",
                admin_user="admin456"
            )

        assert "Failed to unban" in str(exc_info.value)

        # Verify audit log recorded failure
        mock_log.assert_called_once()
        log_call = mock_log.call_args[1]
        assert log_call["result"].startswith("failure:")


class TestUserServiceStats:
    """Tests for user stats and listing functionality."""

    @pytest.mark.asyncio
    async def test_get_user_stats_success(self, user_service, mock_user_repository):
        """Test getting user stats with mock repository."""
        mock_user_data = {
            'user_id': 'user123',
            'discord_username': 'testuser#1234',
            'user_tier': 'free',
            'weekly_token_budget': 50000,
            'bonus_tokens': 10000,
            'tokens_used_this_week': 15000,
            'tokens_remaining': 45000,
            'preferred_model': None,
            'temperature': None,
            'thinking_enabled': None,
            'is_banned': False,
            'created_at': '2025-01-01T00:00:00Z',
            'last_active': '2025-12-22T10:00:00Z'
        }

        mock_user_repository.get_user = AsyncMock(return_value=mock_user_data)

        result = await user_service.get_user_stats("user123")

        assert result["user_id"] == "user123"
        assert result["discord_username"] == "testuser#1234"
        assert result["tokens"]["weekly_budget"] == 50000
        assert result["tokens"]["bonus_tokens"] == 10000
        assert result["ban_status"]["is_banned"] is False

        # Verify repository was called
        mock_user_repository.get_user.assert_called_once_with("user123")

    @pytest.mark.asyncio
    async def test_get_user_stats_not_found(self, user_service, mock_user_repository):
        """Test getting stats for non-existent user."""
        mock_user_repository.get_user = AsyncMock(return_value=None)

        with pytest.raises(ValueError) as exc_info:
            await user_service.get_user_stats("nonexistent")

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_list_all_users_success(self, user_service, mock_user_repository):
        """Test listing users with mock repository."""
        mock_users = [
            {
                'user_id': 'user1',
                'discord_username': 'user1#1234',
                'user_tier': 'free',
                'tokens_remaining': 45000,
                'is_banned': False,
                'created_at': '2025-01-01T00:00:00Z',
                'last_active': '2025-12-22T10:00:00Z'
            },
            {
                'user_id': 'user2',
                'discord_username': 'user2#5678',
                'user_tier': 'admin',
                'tokens_remaining': 100000,
                'is_banned': False,
                'created_at': '2025-01-02T00:00:00Z',
                'last_active': '2025-12-22T11:00:00Z'
            }
        ]

        mock_user_repository.list_users = AsyncMock(return_value={
            'users': mock_users,
            'last_key': None
        })

        result = await user_service.list_all_users(limit=100, offset=0)

        assert result["total"] == 2
        assert len(result["users"]) == 2
        assert result["users"][0]["user_id"] in ["user1", "user2"]
        assert result["has_more"] is False

        # Verify repository was called
        mock_user_repository.list_users.assert_called_once()
