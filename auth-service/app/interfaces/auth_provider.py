"""Auth provider interface (DIP - Dependency Inversion)"""
from abc import ABC, abstractmethod
from typing import Optional
from app.domain.auth_method import AuthMethod


class IAuthProvider(ABC):
    """Interface for authentication providers"""

    @abstractmethod
    async def authenticate(
        self,
        identifier: str,
        credentials: str
    ) -> Optional[AuthMethod]:
        """
        Authenticate user with provider-specific credentials.

        Args:
            identifier: Username, email, Discord ID, etc.
            credentials: Password, token, etc.

        Returns:
            AuthMethod if valid, None otherwise
        """
        pass

    @abstractmethod
    async def create_auth_method(
        self,
        user_id: str,
        identifier: str,
        credentials: str,
        metadata: dict = None
    ) -> AuthMethod:
        """
        Create new auth method for user.

        Used for registration and account linking.
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider name ('password', 'discord', etc.)"""
        pass
