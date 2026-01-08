"""AuthMethod repository interface"""
from abc import ABC, abstractmethod
from typing import Optional, List
from app.domain.auth_method import AuthMethod


class IAuthMethodRepository(ABC):
    """Interface for auth method data access"""

    @abstractmethod
    async def get_by_id(self, auth_method_id: str) -> Optional[AuthMethod]:
        """Get auth method by ID"""
        pass

    @abstractmethod
    async def get_by_provider_and_identifier(
        self,
        provider: str,
        provider_user_id: str
    ) -> Optional[AuthMethod]:
        """Get auth method by provider + identifier"""
        pass

    @abstractmethod
    async def get_all_for_user(self, user_id: str) -> List[AuthMethod]:
        """Get all auth methods for a user"""
        pass

    @abstractmethod
    async def create(self, auth_method: AuthMethod) -> AuthMethod:
        """Create new auth method"""
        pass

    @abstractmethod
    async def update(self, auth_method: AuthMethod) -> AuthMethod:
        """Update auth method"""
        pass

    @abstractmethod
    async def delete(self, auth_method_id: str) -> bool:
        """Delete auth method"""
        pass
