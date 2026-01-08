"""Authentication middleware for admin service."""
import jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, Header, Depends, Query
from typing import Optional, Dict
import logging_client

from app.config import settings

logger = logging_client.setup_logger('admin-auth')


def verify_jwt_token(token: str) -> Dict:
    """
    Verify JWT token from auth-service.

    Args:
        token: JWT token string

    Returns:
        dict: Decoded token with user_id and role

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        # Decode and verify JWT
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )

        # Validate required fields exist first
        user_id = payload.get("user_id")
        role = payload.get("role")

        if not user_id or not role:
            logger.warning("JWT token missing required fields (user_id or role)")
            raise HTTPException(
                status_code=401,
                detail="Token missing required fields"
            )

        # Check role value
        if role != "admin":
            logger.warning(f"User {user_id} attempted admin access with role={role}")
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions. Admin role required."
            )

        logger.debug(f"JWT verified: user_id={user_id}, role={role}")
        return {
            "user_id": user_id,
            "role": role,
            "auth_type": "jwt"
        }

    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


def verify_discord_token(token: str) -> Dict:
    """
    Verify Discord bot-signed token.

    Args:
        token: JWT token signed by Discord bot

    Returns:
        dict: Decoded token with user_id and role_id

    Raises:
        HTTPException: If token is invalid, expired, or too old
    """
    if not settings.BOT_SECRET:
        logger.error("BOT_SECRET not configured - cannot verify Discord tokens")
        raise HTTPException(
            status_code=500,
            detail="Discord authentication not configured"
        )

    try:
        # Decode and verify token signed by Discord bot
        payload = jwt.decode(
            token,
            settings.BOT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )

        # Check timestamp (must be <5 minutes old to prevent replay attacks)
        issued_at = payload.get("iat")
        if not issued_at:
            raise HTTPException(status_code=401, detail="Token missing timestamp")

        token_age = datetime.utcnow().timestamp() - issued_at
        if token_age > settings.DISCORD_TOKEN_EXPIRY_SECONDS:
            logger.warning(f"Discord token too old: {token_age}s")
            raise HTTPException(status_code=401, detail="Token expired")

        logger.debug(f"Discord token verified: user_id={payload.get('user_id')}, role_id={payload.get('role_id')}")
        return {
            "user_id": payload.get("user_id"),
            "role_id": payload.get("role_id"),
            "auth_type": "discord"
        }

    except jwt.ExpiredSignatureError:
        logger.warning("Discord token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid Discord token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_admin(
    authorization: Optional[str] = Header(None)
) -> Dict:
    """
    Dependency to require admin authentication.

    Checks Authorization header for Bearer token and verifies it.
    Supports both JWT tokens (from auth-service) and Discord tokens (from bot).

    Args:
        authorization: Authorization header value

    Returns:
        dict: User info with user_id, role/role_id, auth_type

    Raises:
        HTTPException: If not authorized
    """
    if not authorization:
        logger.warning("Request missing Authorization header")
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )

    # Parse Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning(f"Invalid Authorization format: {authorization[:20]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected: Bearer <token>"
        )

    token = parts[1]

    # Try to decode to determine token type
    try:
        # First, try to decode without verification to peek at payload
        unverified = jwt.decode(token, options={"verify_signature": False})

        # Determine token type based on payload structure
        if "role_id" in unverified:
            # Discord token (has role_id field)
            return verify_discord_token(token)
        else:
            # JWT token from auth-service (has role field)
            return verify_jwt_token(token)

    except Exception as e:
        logger.error(f"Failed to decode token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token format")


async def require_admin_sse(
    token: Optional[str] = Query(None, description="JWT token for SSE authentication"),
    authorization: Optional[str] = Header(None)
) -> Dict:
    """
    Admin authentication for SSE endpoints.

    Supports both Authorization header (for non-SSE requests) and
    ?token query parameter (for SSE EventSource which can't set headers).

    Args:
        token: JWT token from query parameter
        authorization: Authorization header value

    Returns:
        dict: User info with user_id, role, auth_type

    Raises:
        HTTPException: If not authorized
    """
    # Try header first (for backward compatibility)
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return verify_jwt_token(parts[1])

    # Fallback to query parameter (for SSE)
    if not token:
        logger.warning("Request missing both Authorization header and token query parameter")
        raise HTTPException(
            status_code=401,
            detail="Missing authentication. Provide either Authorization header or ?token query parameter"
        )

    logger.debug(f"Authenticating SSE request with query parameter token")
    return verify_jwt_token(token)
