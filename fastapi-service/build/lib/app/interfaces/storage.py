"""Storage interface following Dependency Inversion Principle."""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class StorageInterface(ABC):
    """Abstract interface for conversation and user storage."""

    @abstractmethod
    async def get_thread_messages(
        self,
        thread_id: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get messages for a thread, ordered by timestamp."""
        pass

    @abstractmethod
    async def add_message(
        self,
        thread_id: str,
        message_id: str,
        role: str,
        content: str,
        token_count: int,
        user_id: str,
        model_used: str,
        is_summary: bool = False
    ) -> None:
        """Add a message to a thread."""
        pass

    @abstractmethod
    async def delete_messages(
        self,
        thread_id: str,
        message_timestamps: List[str]
    ) -> None:
        """Delete multiple messages from a thread."""
        pass

    @abstractmethod
    async def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user data including preferences and token info."""
        pass

    @abstractmethod
    async def create_user(
        self,
        user_id: str,
        discord_username: str,
        user_tier: str = 'free'
    ) -> None:
        """Create a new user with default settings."""
        pass

    @abstractmethod
    async def update_user_tokens(
        self,
        user_id: str,
        tokens_used: int
    ) -> None:
        """Update user's token usage."""
        pass

    @abstractmethod
    async def grant_bonus_tokens(
        self,
        user_id: str,
        amount: int
    ) -> None:
        """Grant bonus tokens to a user."""
        pass

    @abstractmethod
    async def get_user_threads(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[str]:
        """Get list of thread IDs for a user."""
        pass
