"""WebSocket authentication strategies and factory (Strategy Pattern + OCP).

Each interface type has its own authentication strategy:
- web: JWT token validation (same secret as auth-service)
- discord: HMAC signature validation
- cli/api: Passthrough (development) or JWT

This follows SOLID principles:
- SRP: Each strategy handles one type of authentication
- OCP: Add new strategies without modifying existing code
- DIP: Depend on IAuthStrategy interface
"""
import hashlib
import hmac
import os
from typing import Any, Dict, Optional, Type

import jwt

from app.core.interfaces.auth import AuthResult, IAuthStrategy


class JWTAuthStrategy:
    """JWT authentication for web interface.

    Uses the same secret key as auth-service to validate access tokens.
    """

    def __init__(self) -> None:
        self.secret_key = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
        self.algorithm = "HS256"

    async def authenticate(
        self,
        token: Optional[str],
        interface: str,
        **kwargs: Any,
    ) -> AuthResult:
        """Authenticate using JWT token."""
        if not token:
            return AuthResult(authenticated=False, error="Missing JWT token")

        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Verify it's an access token (not refresh)
            if payload.get("type") != "access":
                return AuthResult(authenticated=False, error="Invalid token type")

            return AuthResult(
                authenticated=True,
                user_id=payload.get("user_id"),
                metadata={
                    "role": payload.get("role"),
                    "username": payload.get("username"),
                },
            )
        except jwt.ExpiredSignatureError:
            return AuthResult(authenticated=False, error="Token expired")
        except jwt.InvalidTokenError as e:
            return AuthResult(authenticated=False, error=f"Invalid token: {e}")


class BotSecretAuthStrategy:
    """HMAC authentication for Discord bot.

    Bot generates HMAC signature using shared secret and bot_id.
    This prevents unauthorized clients from impersonating the bot.
    """

    def __init__(self) -> None:
        self.bot_secret = os.getenv("BOT_SECRET", "")

    async def authenticate(
        self,
        token: Optional[str],
        interface: str,
        **kwargs: Any,
    ) -> AuthResult:
        """Authenticate using HMAC signature."""
        if not self.bot_secret:
            # If no secret configured, allow passthrough (development)
            return AuthResult(
                authenticated=True,
                user_id=kwargs.get("user_id", "discord-bot"),
                metadata={"is_bot": True, "auth_mode": "passthrough"},
            )

        if not token:
            return AuthResult(authenticated=False, error="Missing bot token")

        bot_id = kwargs.get("bot_id") or kwargs.get("user_id")
        if not bot_id:
            return AuthResult(authenticated=False, error="Missing bot_id")

        # Compute expected HMAC
        expected = hmac.new(
            self.bot_secret.encode(),
            bot_id.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(token, expected):
            return AuthResult(authenticated=False, error="Invalid bot signature")

        return AuthResult(
            authenticated=True,
            user_id=f"discord-bot:{bot_id}",
            metadata={"is_bot": True},
        )


class NoAuthStrategy:
    """Pass-through authentication for CLI/development.

    Accepts any connection without validation.
    Use only in trusted environments.
    """

    async def authenticate(
        self,
        token: Optional[str],
        interface: str,
        **kwargs: Any,
    ) -> AuthResult:
        """Allow all connections."""
        return AuthResult(
            authenticated=True,
            user_id=kwargs.get("user_id", "anonymous"),
            metadata={"auth_mode": "none"},
        )


# ============================================================================
# Strategy Registry (OCP - add new strategies without modifying existing code)
# ============================================================================

_STRATEGIES: Dict[str, Type[IAuthStrategy]] = {
    "web": JWTAuthStrategy,
    "discord": BotSecretAuthStrategy,
    "cli": NoAuthStrategy,
    "api": JWTAuthStrategy,
}

_CACHE: Dict[str, IAuthStrategy] = {}


def get_auth_strategy(interface: str) -> IAuthStrategy:
    """Get auth strategy for interface (Factory Pattern).

    Args:
        interface: Interface type (web, discord, cli, api)

    Returns:
        Appropriate auth strategy instance (cached).
    """
    if interface not in _CACHE:
        strategy_class = _STRATEGIES.get(interface, NoAuthStrategy)
        _CACHE[interface] = strategy_class()
    return _CACHE[interface]


def is_auth_required(interface: str) -> bool:
    """Check if authentication is required for interface.

    Auth can be globally disabled via DISABLE_WS_AUTH=true for development.

    Args:
        interface: Interface type

    Returns:
        True if auth should be enforced.
    """
    # Global disable for development
    if os.getenv("DISABLE_WS_AUTH", "false").lower() == "true":
        return False

    # Web always requires auth
    if interface == "web":
        return True

    # Discord requires auth only if BOT_SECRET is configured
    if interface == "discord":
        return bool(os.getenv("BOT_SECRET"))

    # CLI and others don't require auth
    return False
