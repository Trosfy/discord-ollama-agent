"""Integration tests for API endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.main import app, auth_service
from app.domain.user import User
from app.domain.auth_method import AuthMethod


@pytest.fixture
def mock_auth_service():
    """Mock AuthenticationService for API tests."""
    with patch.object(auth_service, 'login', new=AsyncMock()) as mock_login, \
         patch.object(auth_service, 'register', new=AsyncMock()) as mock_register, \
         patch.object(auth_service, 'link_auth_method', new=AsyncMock()) as mock_link:

        yield {
            'login': mock_login,
            'register': mock_register,
            'link_auth_method': mock_link
        }


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'healthy'
    assert data['service'] == 'auth-service-v2'
    assert data['version'] == '2.0.0'


@pytest.mark.asyncio
async def test_login_success(mock_auth_service):
    """Test successful login."""
    # Setup mock
    mock_user = User(
        user_id="user_test123",
        display_name="Test User",
        email="test@example.com",
        role="standard",
        user_tier="standard",
        preferences={},
        weekly_token_budget=100000,
        tokens_remaining=100000,
        tokens_used_this_week=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    mock_auth_service['login'].return_value = {
        'access_token': 'test_token_123',
        'token_type': 'bearer',
        'user': mock_user,
        'auth_method': None
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/login",
            json={
                'provider': 'password',
                'identifier': 'testuser',
                'credentials': 'password'
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert data['access_token'] == 'test_token_123'
    assert data['token_type'] == 'bearer'
    assert data['user']['user_id'] == 'user_test123'
    assert data['user']['role'] == 'standard'


@pytest.mark.asyncio
async def test_login_invalid_credentials(mock_auth_service):
    """Test login with invalid credentials."""
    # Setup mock
    mock_auth_service['login'].return_value = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/login",
            json={
                'provider': 'password',
                'identifier': 'testuser',
                'credentials': 'wrongpassword'
            }
        )

    assert response.status_code == 401
    assert "Invalid credentials" in response.json()['detail']


@pytest.mark.asyncio
async def test_login_unknown_provider(mock_auth_service):
    """Test login with unknown provider."""
    # Setup mock
    mock_auth_service['login'].side_effect = ValueError("Unknown provider: unknown")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/login",
            json={
                'provider': 'unknown',
                'identifier': 'testuser',
                'credentials': 'password'
            }
        )

    assert response.status_code == 400
    assert "Unknown provider" in response.json()['detail']


@pytest.mark.asyncio
async def test_register_success(mock_auth_service):
    """Test successful user registration."""
    # Setup mock
    mock_user = User(
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

    mock_auth_service['register'].return_value = {
        'access_token': 'new_token_123',
        'token_type': 'bearer',
        'user': mock_user,
        'auth_method': None
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/register",
            json={
                'provider': 'password',
                'identifier': 'newuser',
                'credentials': 'password',
                'display_name': 'New User',
                'email': 'new@example.com'
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert data['access_token'] == 'new_token_123'
    assert data['user']['user_id'] == 'user_new123'
    assert data['user']['display_name'] == 'New User'


@pytest.mark.asyncio
async def test_register_duplicate_username(mock_auth_service):
    """Test registration with duplicate username."""
    # Setup mock
    mock_auth_service['register'].side_effect = ValueError("Auth method already exists")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/register",
            json={
                'provider': 'password',
                'identifier': 'existinguser',
                'credentials': 'password',
                'display_name': 'Test User'
            }
        )

    assert response.status_code == 400
    assert "already exists" in response.json()['detail']


@pytest.mark.asyncio
async def test_link_auth_method_success(mock_auth_service):
    """Test successfully linking auth method."""
    # Setup mock
    mock_auth_method = AuthMethod(
        auth_method_id="auth_linked123",
        user_id="user_test123",
        provider="password",
        provider_user_id="altusername",
        credentials={},
        metadata={},
        is_primary=False,
        is_verified=True,
        created_at=datetime.utcnow(),
        last_used_at=None
    )

    mock_auth_service['link_auth_method'].return_value = mock_auth_method

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/link-auth-method",
            json={
                'user_id': 'user_test123',
                'provider': 'password',
                'identifier': 'altusername',
                'credentials': 'password'
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'success'
    assert data['auth_method_id'] == 'auth_linked123'
    assert data['provider'] == 'password'


@pytest.mark.asyncio
async def test_link_auth_method_user_not_found(mock_auth_service):
    """Test linking auth method when user doesn't exist."""
    # Setup mock
    mock_auth_service['link_auth_method'].side_effect = ValueError("User not found")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/link-auth-method",
            json={
                'user_id': 'nonexistent',
                'provider': 'password',
                'identifier': 'username',
                'credentials': 'password'
            }
        )

    assert response.status_code == 400
    assert "User not found" in response.json()['detail']


@pytest.mark.asyncio
async def test_link_auth_method_already_linked(mock_auth_service):
    """Test linking auth method that's already linked to another user."""
    # Setup mock
    mock_auth_service['link_auth_method'].side_effect = ValueError(
        "This password account is already linked to another user"
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/link-auth-method",
            json={
                'user_id': 'user_test123',
                'provider': 'password',
                'identifier': 'taken_username',
                'credentials': 'password'
            }
        )

    assert response.status_code == 400
    assert "already linked" in response.json()['detail']
