"""Storage interfaces following SOLID principles (Interface Segregation, Dependency Inversion)."""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Protocol


# SOLID: Interface Segregation Principle
# Split monolithic storage into focused interfaces with Single Responsibility


class IConversationStorage(Protocol):
    """Conversation and thread management (Single Responsibility)."""

    async def get_thread_messages(
        self,
        thread_id: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get messages for a thread, ordered by timestamp."""
        ...

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
        ...

    async def delete_messages(
        self,
        thread_id: str,
        message_timestamps: List[str]
    ) -> None:
        """Delete multiple messages from a thread."""
        ...

    async def get_user_threads(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[str]:
        """Get list of thread IDs for a user."""
        ...


class IUserStorage(Protocol):
    """User settings and preferences (Single Responsibility)."""

    async def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """
        Get user preferences including model, temperature, thinking_enabled.

        Returns:
            Dict with keys: preferred_model, temperature, thinking_enabled, base_prompt
            None if user doesn't exist
        """
        ...

    async def create_user(
        self,
        user_id: str,
        discord_username: str,
        user_tier: str = 'free'
    ) -> None:
        """Create a new user with default settings."""
        ...

    async def update_temperature(
        self,
        user_id: str,
        temperature: Optional[float]
    ) -> None:
        """
        Update user's preferred temperature.

        Args:
            temperature: None for system default, or float value
        """
        ...

    async def update_thinking(
        self,
        user_id: str,
        enabled: Optional[bool]
    ) -> None:
        """
        Update user's thinking mode preference.

        Args:
            enabled: None for auto (route-based), True to force on, False to force off
        """
        ...

    async def update_model(
        self,
        user_id: str,
        model: Optional[str]
    ) -> None:
        """
        Update user's preferred model.

        Args:
            model: Model name, 'trollama' for router, or None for default
        """
        ...

    async def reset_preferences(self, user_id: str) -> None:
        """
        Reset all user preferences to system defaults.

        Resets temperature, thinking_enabled, preferred_model, and base_prompt to None.
        """
        ...


class ITokenTrackingStorage(Protocol):
    """Token budgets and usage tracking (Single Responsibility)."""

    async def get_user_tokens(self, user_id: str) -> Optional[Dict]:
        """
        Get user's token budget and usage.

        Returns:
            Dict with keys: weekly_token_budget, tokens_used_this_week,
                           tokens_remaining, bonus_tokens
        """
        ...

    async def update_user_tokens(
        self,
        user_id: str,
        tokens_used: int
    ) -> None:
        """Update user's token usage."""
        ...

    async def grant_bonus_tokens(
        self,
        user_id: str,
        amount: int
    ) -> None:
        """Grant bonus tokens to a user."""
        ...

    async def reset_weekly_tokens(self) -> None:
        """Reset weekly token counters for all users."""
        ...


# Legacy interface for backwards compatibility
# TODO: Migrate all code to use the new focused interfaces above
class StorageInterface(ABC):
    """
    Abstract interface for conversation and user storage.

    DEPRECATED: Use IConversationStorage, IUserPreferencesStorage,
                and ITokenTrackingStorage instead.
    """

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
