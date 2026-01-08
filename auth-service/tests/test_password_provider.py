"""Unit tests for PasswordAuthProvider."""
import pytest
from unittest.mock import AsyncMock
from datetime import datetime

from app.providers.password_provider import PasswordAuthProvider
from app.domain.auth_method import AuthMethod


@pytest.mark.asyncio
async def test_authenticate_success(mock_auth_method_repository, sample_auth_method):
    """Test successful authentication with correct password."""
    # Setup
    mock_auth_method_repository.get_by_provider_and_identifier.return_value = sample_auth_method
    mock_auth_method_repository.update.return_value = sample_auth_method

    provider = PasswordAuthProvider(mock_auth_method_repository)

    # Execute
    result = await provider.authenticate("testuser", "password")

    # Assert
    assert result is not None
    assert result.user_id == "user_test123"
    assert result.provider == "password"
    mock_auth_method_repository.get_by_provider_and_identifier.assert_called_once_with(
        provider='password',
        provider_user_id='testuser'
    )
    mock_auth_method_repository.update.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_wrong_password(mock_auth_method_repository, sample_auth_method):
    """Test authentication fails with wrong password."""
    # Setup
    mock_auth_method_repository.get_by_provider_and_identifier.return_value = sample_auth_method

    provider = PasswordAuthProvider(mock_auth_method_repository)

    # Execute
    result = await provider.authenticate("testuser", "wrongpassword")

    # Assert
    assert result is None
    mock_auth_method_repository.update.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_user_not_found(mock_auth_method_repository):
    """Test authentication fails when user doesn't exist."""
    # Setup
    mock_auth_method_repository.get_by_provider_and_identifier.return_value = None

    provider = PasswordAuthProvider(mock_auth_method_repository)

    # Execute
    result = await provider.authenticate("nonexistent", "password")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_no_password_hash(mock_auth_method_repository, sample_auth_method):
    """Test authentication fails when auth method has no password hash."""
    # Setup
    sample_auth_method.credentials = {}  # No password_hash
    mock_auth_method_repository.get_by_provider_and_identifier.return_value = sample_auth_method

    provider = PasswordAuthProvider(mock_auth_method_repository)

    # Execute
    result = await provider.authenticate("testuser", "password")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_create_auth_method(mock_auth_method_repository):
    """Test creating a new password auth method."""
    # Setup
    created_auth_method = AuthMethod(
        auth_method_id="auth_new123",
        user_id="user_test123",
        provider="password",
        provider_user_id="newuser",
        credentials={'password_hash': 'hashed'},
        metadata={},
        is_primary=True,
        is_verified=True,
        created_at=datetime.utcnow(),
        last_used_at=None
    )
    mock_auth_method_repository.create.return_value = created_auth_method

    provider = PasswordAuthProvider(mock_auth_method_repository)

    # Execute
    result = await provider.create_auth_method(
        user_id="user_test123",
        identifier="newuser",
        credentials="newpassword",
        metadata={}
    )

    # Assert
    assert result is not None
    assert result.user_id == "user_test123"
    assert result.provider == "password"
    assert result.provider_user_id == "newuser"
    assert 'password_hash' in result.credentials
    assert result.credentials['password_hash'] != "newpassword"  # Should be hashed
    mock_auth_method_repository.create.assert_called_once()


@pytest.mark.asyncio
async def test_get_provider_name(mock_auth_method_repository):
    """Test getting provider name."""
    provider = PasswordAuthProvider(mock_auth_method_repository)

    assert provider.get_provider_name() == 'password'
