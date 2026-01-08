"""Pytest configuration and shared fixtures for auth-service tests."""
import pytest
import asyncio
import sys
from unittest.mock import Mock
from datetime import datetime
import uuid

# Mock logging_client from shared module before any imports
mock_logging = Mock()
mock_logging.setup_logger = Mock(return_value=Mock())
sys.modules['logging_client'] = mock_logging


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def anyio_backend():
    """Use asyncio as the async backend."""
    return 'asyncio'


@pytest.fixture
def sample_user():
    """Fixture for a sample User domain object."""
    from app.domain.user import User
    return User(
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


@pytest.fixture
def sample_admin_user():
    """Fixture for a sample admin User domain object."""
    from app.domain.user import User
    return User(
        user_id="user_admin123",
        display_name="Admin User",
        email="admin@example.com",
        role="admin",
        user_tier="admin",
        preferences={},
        weekly_token_budget=1000000,
        tokens_remaining=1000000,
        tokens_used_this_week=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_auth_method():
    """Fixture for a sample AuthMethod domain object."""
    from app.domain.auth_method import AuthMethod
    from app.utils.crypto import hash_password

    # Generate a fresh password hash for "password"
    password_hash = hash_password("password")

    return AuthMethod(
        auth_method_id="auth_test123",
        user_id="user_test123",
        provider="password",
        provider_user_id="testuser",
        credentials={'password_hash': password_hash},
        metadata={},
        is_primary=True,
        is_verified=True,
        created_at=datetime.utcnow(),
        last_used_at=None
    )


@pytest.fixture
def mock_user_repository():
    """Mock UserRepository for testing."""
    from unittest.mock import AsyncMock
    mock_repo = AsyncMock()
    return mock_repo


@pytest.fixture
def mock_auth_method_repository():
    """Mock AuthMethodRepository for testing."""
    from unittest.mock import AsyncMock
    mock_repo = AsyncMock()
    return mock_repo
