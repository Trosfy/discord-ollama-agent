"""JWT token utilities"""
import jwt
from datetime import datetime, timedelta
from typing import Dict, Tuple
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(data: Dict) -> str:
    """Create JWT access token (short-lived: 8 hours)."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: Dict) -> str:
    """Create JWT refresh token (long-lived: 7 days)."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_token_pair(data: Dict) -> Tuple[str, str]:
    """Create both access and refresh tokens.

    Returns:
        Tuple of (access_token, refresh_token)
    """
    return create_access_token(data), create_refresh_token(data)


def verify_token(token: str) -> Dict:
    """Verify and decode JWT token."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def verify_refresh_token(token: str) -> Dict:
    """Verify refresh token and return payload if valid.

    Raises:
        jwt.ExpiredSignatureError: If token expired
        jwt.InvalidTokenError: If token is invalid or not a refresh token
    """
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("Not a refresh token")

    return payload
