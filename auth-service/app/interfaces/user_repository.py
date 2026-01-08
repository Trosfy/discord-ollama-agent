"""User repository interface"""
from abc import ABC, abstractmethod
from typing import Optional
from app.domain.user import User


class IUserRepository(ABC):
    """Interface for user data access"""

    @abstractmethod
    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        pass

    @abstractmethod
    async def create(self, user: User) -> User:
        """Create new user"""
        pass

    @abstractmethod
    async def update(self, user: User) -> User:
        """Update existing user"""
        pass

    @abstractmethod
    async def delete(self, user_id: str) -> bool:
        """Delete user"""
        pass
