"""Unit tests for AuthenticationService."""
import pytest
from unittest.mock import AsyncMock
from datetime import datetime

from app.services.authentication_service import AuthenticationService
from app.domain.user import User
from app.domain.auth_method import AuthMethod


@pytest.mark.asyncio
async def test_login_success(mock_user_repository, mock_auth_method_repository, sample_user, sample_auth_method):
    """Test successful login."""
    # Setup mocks
    mock_password_provider = AsyncMock()
    mock_password_provider.authenticate.return_value = sample_auth_method

    mock_user_repository.get_by_id.return_value = sample_user

    auth_providers = {'password': mock_password_provider}
    service = AuthenticationService(auth_providers, mock_user_repository, mock_auth_method_repository)

    # Execute
    result = await service.login(
        provider='password',
        identifier='testuser',
        credentials='password'
    )

    # Assert
    assert result is not None
    assert 'access_token' in result
    assert 'user' in result
    assert result['user'].user_id == 'user_test123'
    assert result['token_type'] == 'bearer'
    mock_password_provider.authenticate.assert_called_once_with('testuser', 'password')
    mock_user_repository.get_by_id.assert_called_once_with('user_test123')


@pytest.mark.asyncio
async def test_login_invalid_credentials(mock_user_repository, mock_auth_method_repository):
    """Test login with invalid credentials."""
    # Setup mocks
    mock_password_provider = AsyncMock()
    mock_password_provider.authenticate.return_value = None

    auth_providers = {'password': mock_password_provider}
    service = AuthenticationService(auth_providers, mock_user_repository, mock_auth_method_repository)

    # Execute
    result = await service.login(
        provider='password',
        identifier='testuser',
        credentials='wrongpassword'
    )

    # Assert
    assert result is None
    mock_user_repository.get_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_login_unknown_provider(mock_user_repository, mock_auth_method_repository):
    """Test login with unknown provider raises ValueError."""
    # Setup
    service = AuthenticationService({}, mock_user_repository, mock_auth_method_repository)

    # Execute & Assert
    with pytest.raises(ValueError, match="Unknown provider"):
        await service.login(
            provider='unknown',
            identifier='testuser',
            credentials='password'
        )


@pytest.mark.asyncio
async def test_register_success(mock_user_repository, mock_auth_method_repository):
    """Test successful user registration."""
    # Setup mocks
    mock_password_provider = AsyncMock()
    created_user = User(
        user_id="user_new123",
        display_name="New User",
        email="new@example.com",
        role="standard",
        user_tier="standard",
        preferences={},
        weekly_token_budget=100000,
        tokens_remaining=100000,
        tokens_used_this_week=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    created_auth_method = AuthMethod(
        auth_method_id="auth_new123",
        user_id="user_new123",
        provider="password",
        provider_user_id="newuser",
        credentials={'password_hash': 'hashed'},
        metadata={},
        is_primary=True,
        is_verified=True,
        created_at=datetime.utcnow(),
        last_used_at=None
    )

    mock_auth_method_repository.get_by_provider_and_identifier.return_value = None
    mock_user_repository.create.return_value = created_user
    mock_password_provider.create_auth_method.return_value = created_auth_method

    auth_providers = {'password': mock_password_provider}
    service = AuthenticationService(auth_providers, mock_user_repository, mock_auth_method_repository)

    # Execute
    result = await service.register(
        provider='password',
        identifier='newuser',
        credentials='password',
        display_name='New User',
        email='new@example.com'
    )

    # Assert
    assert result is not None
    assert 'access_token' in result
    assert result['user'].user_id == 'user_new123'
    mock_user_repository.create.assert_called_once()
    mock_password_provider.create_auth_method.assert_called_once()


@pytest.mark.asyncio
async def test_register_duplicate_username(mock_user_repository, mock_auth_method_repository, sample_auth_method):
    """Test registration fails with duplicate username."""
    # Setup mocks
    mock_password_provider = AsyncMock()
    mock_auth_method_repository.get_by_provider_and_identifier.return_value = sample_auth_method

    auth_providers = {'password': mock_password_provider}
    service = AuthenticationService(auth_providers, mock_user_repository, mock_auth_method_repository)

    # Execute & Assert
    with pytest.raises(ValueError, match="already exists"):
        await service.register(
            provider='password',
            identifier='testuser',
            credentials='password',
            display_name='Test User'
        )

    mock_user_repository.create.assert_not_called()


@pytest.mark.asyncio
async def test_link_auth_method_success(mock_user_repository, mock_auth_method_repository, sample_user):
    """Test successfully linking new auth method."""
    # Setup mocks
    mock_password_provider = AsyncMock()
    new_auth_method = AuthMethod(
        auth_method_id="auth_linked123",
        user_id="user_test123",
        provider="password",
        provider_user_id="altusername",
        credentials={'password_hash': 'hashed'},
        metadata={},
        is_primary=False,
        is_verified=True,
        created_at=datetime.utcnow(),
        last_used_at=None
    )

    mock_user_repository.get_by_id.return_value = sample_user
    mock_auth_method_repository.get_by_provider_and_identifier.return_value = None
    mock_password_provider.create_auth_method.return_value = new_auth_method

    auth_providers = {'password': mock_password_provider}
    service = AuthenticationService(auth_providers, mock_user_repository, mock_auth_method_repository)

    # Execute
    result = await service.link_auth_method(
        user_id='user_test123',
        provider='password',
        identifier='altusername',
        credentials='newpassword'
    )

    # Assert
    assert result is not None
    assert result.auth_method_id == 'auth_linked123'
    assert result.user_id == 'user_test123'
    mock_password_provider.create_auth_method.assert_called_once()


@pytest.mark.asyncio
async def test_link_auth_method_user_not_found(mock_user_repository, mock_auth_method_repository):
    """Test linking auth method fails when user doesn't exist."""
    # Setup mocks
    mock_password_provider = AsyncMock()
    mock_user_repository.get_by_id.return_value = None

    auth_providers = {'password': mock_password_provider}
    service = AuthenticationService(auth_providers, mock_user_repository, mock_auth_method_repository)

    # Execute & Assert
    with pytest.raises(ValueError, match="User not found"):
        await service.link_auth_method(
            user_id='nonexistent',
            provider='password',
            identifier='username',
            credentials='password'
        )


@pytest.mark.asyncio
async def test_link_auth_method_already_linked_to_another_user(
    mock_user_repository, mock_auth_method_repository, sample_user, sample_auth_method
):
    """Test linking fails when auth method belongs to another user."""
    # Setup mocks
    mock_password_provider = AsyncMock()
    sample_auth_method.user_id = "other_user"  # Different user

    mock_user_repository.get_by_id.return_value = sample_user
    mock_auth_method_repository.get_by_provider_and_identifier.return_value = sample_auth_method

    auth_providers = {'password': mock_password_provider}
    service = AuthenticationService(auth_providers, mock_user_repository, mock_auth_method_repository)

    # Execute & Assert
    with pytest.raises(ValueError, match="already linked to another user"):
        await service.link_auth_method(
            user_id='user_test123',
            provider='password',
            identifier='testuser',
            credentials='password'
        )
