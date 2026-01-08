"""Unit tests for crypto utilities."""
import pytest
from app.utils.crypto import hash_password, verify_password


def test_hash_password():
    """Test password hashing."""
    password = "test_password_123"
    hashed = hash_password(password)

    # Assert hash is different from password
    assert hashed != password

    # Assert hash starts with bcrypt prefix
    assert hashed.startswith('$2b$')

    # Assert hash is consistent length
    assert len(hashed) == 60


def test_hash_password_different_each_time():
    """Test that hashing same password produces different hashes (due to salt)."""
    password = "test_password_123"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    # Should be different due to different salt
    assert hash1 != hash2

    # But both should verify correctly
    assert verify_password(password, hash1)
    assert verify_password(password, hash2)


def test_verify_password_success():
    """Test successful password verification."""
    password = "test_password_123"
    hashed = hash_password(password)

    result = verify_password(password, hashed)

    assert result is True


def test_verify_password_wrong_password():
    """Test password verification fails with wrong password."""
    password = "test_password_123"
    hashed = hash_password(password)

    result = verify_password("wrong_password", hashed)

    assert result is False


def test_verify_password_with_string_hash():
    """Test password verification works with string hash."""
    password = "test_password_123"
    hashed = hash_password(password)  # Returns string

    # Verify with string hash
    result = verify_password(password, hashed)

    assert result is True


def test_verify_password_with_bytes_hash():
    """Test password verification works with bytes hash."""
    password = "test_password_123"
    hashed = hash_password(password)
    hashed_bytes = hashed.encode('utf-8')

    # Verify with bytes hash
    result = verify_password(password, hashed_bytes)

    assert result is True


def test_verify_password_invalid_hash():
    """Test password verification handles invalid hash gracefully."""
    result = verify_password("password", "invalid_hash")

    assert result is False


def test_verify_password_empty_hash():
    """Test password verification handles empty hash gracefully."""
    result = verify_password("password", "")

    assert result is False
