"""Unit tests for JWT utilities."""
import pytest
import jwt as pyjwt
from datetime import datetime, timedelta

from app.utils.jwt import create_access_token, verify_token, SECRET_KEY, ALGORITHM


def test_create_access_token():
    """Test creating JWT access token."""
    data = {
        "user_id": "user_123",
        "display_name": "Test User",
        "role": "standard"
    }

    token = create_access_token(data)

    # Assert token is a string
    assert isinstance(token, str)

    # Assert token has 3 parts (header.payload.signature)
    assert len(token.split('.')) == 3

    # Decode and verify contents
    decoded = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded['user_id'] == 'user_123'
    assert decoded['display_name'] == 'Test User'
    assert decoded['role'] == 'standard'
    assert 'exp' in decoded


def test_create_access_token_with_expiry():
    """Test token includes expiry time."""
    data = {"user_id": "user_123"}

    before = datetime.now(datetime.UTC if hasattr(datetime, 'UTC') else None)
    token = create_access_token(data)
    after = datetime.now(datetime.UTC if hasattr(datetime, 'UTC') else None)

    decoded = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    # Check expiry is set
    assert 'exp' in decoded

    # Check expiry is in the future (approximately 8 hours from now)
    exp_time = datetime.fromtimestamp(decoded['exp'])

    # Calculate expected expiry range (8 hours from before/after)
    expected_min = before + timedelta(hours=7, minutes=59)
    expected_max = after + timedelta(hours=8, minutes=1)

    # Should be around 8 hours (give or take for timing)
    assert expected_min <= exp_time <= expected_max


def test_verify_token_success():
    """Test successful token verification."""
    data = {
        "user_id": "user_123",
        "display_name": "Test User",
        "role": "admin"
    }

    token = create_access_token(data)
    decoded = verify_token(token)

    assert decoded['user_id'] == 'user_123'
    assert decoded['display_name'] == 'Test User'
    assert decoded['role'] == 'admin'


def test_verify_token_invalid():
    """Test verification fails with invalid token."""
    with pytest.raises(pyjwt.InvalidTokenError):
        verify_token("invalid_token")


def test_verify_token_wrong_signature():
    """Test verification fails with wrong signature."""
    # Create token with different secret
    token = pyjwt.encode(
        {"user_id": "user_123"},
        "wrong_secret",
        algorithm=ALGORITHM
    )

    with pytest.raises(pyjwt.InvalidSignatureError):
        verify_token(token)


def test_verify_token_expired():
    """Test verification fails with expired token."""
    # Create token that's already expired
    data = {"user_id": "user_123"}
    expired_time = datetime.utcnow() - timedelta(hours=1)
    data['exp'] = expired_time

    token = pyjwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

    with pytest.raises(pyjwt.ExpiredSignatureError):
        verify_token(token)


def test_token_contains_all_user_data():
    """Test token preserves all user data."""
    data = {
        "user_id": "user_123",
        "display_name": "Test User",
        "role": "admin",
        "email": "test@example.com",
        "custom_field": "custom_value"
    }

    token = create_access_token(data)
    decoded = verify_token(token)

    # All original data should be preserved
    assert decoded['user_id'] == data['user_id']
    assert decoded['display_name'] == data['display_name']
    assert decoded['role'] == data['role']
    assert decoded['email'] == data['email']
    assert decoded['custom_field'] == data['custom_field']
