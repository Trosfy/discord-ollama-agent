"""WebSocket authentication protocol definitions (Strategy Pattern interface)."""
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable, Dict, Any


@dataclass
class AuthResult:
    """Result of authentication attempt."""

    authenticated: bool
    user_id: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class IAuthStrategy(Protocol):
    """Interface for authentication strategies (ISP).

    Each interface type (web, discord, cli, api) can have its own
    authentication strategy. This follows:
    - Strategy Pattern: Different auth methods for different contexts
    - Interface Segregation: Each strategy only implements what it needs
    - Open/Closed: Add new strategies without modifying existing ones
    """

    async def authenticate(
        self,
        token: Optional[str],
        interface: str,
        **kwargs: Any,
    ) -> AuthResult:
        """Authenticate the connection.

        Args:
            token: Authentication token (JWT, HMAC signature, etc.)
            interface: Interface type (web, discord, cli, api)
            **kwargs: Additional context (user_id, bot_id, etc.)

        Returns:
            AuthResult with authentication status and user info.
        """
        ...
