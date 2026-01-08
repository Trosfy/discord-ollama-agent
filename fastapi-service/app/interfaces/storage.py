"""Storage interfaces following SOLID principles (Interface Segregation, Dependency Inversion)."""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Protocol
from pydantic import BaseModel


# SOLID: Interface Segregation Principle
# Split monolithic storage into focused interfaces with Single Responsibility


class IConversationStorage(Protocol):
    """Conversation management (Single Responsibility)."""

    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get messages for a conversation, ordered by timestamp."""
        ...

    async def add_message(
        self,
        conversation_id: str,
        message_id: str,
        role: str,
        content: str,
        token_count: int,
        user_id: str,
        model_used: str,
        is_summary: bool = False,
        generation_time: Optional[float] = None
    ) -> None:
        """Add a message to a conversation."""
        ...

    async def delete_messages(
        self,
        conversation_id: str,
        message_timestamps: List[str]
    ) -> None:
        """Delete multiple messages from a conversation."""
        ...

    async def get_user_conversations(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[str]:
        """Get list of conversation IDs for a user."""
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


class VectorChunk(BaseModel):
    """Represents a stored chunk with embedding vector."""
    chunk_id: str  # Unique chunk identifier (UUID)
    chunk_text: str  # The actual text content
    embedding_vector: List[float]  # Embedding vector
    chunk_index: int  # Position in original document (0-based)
    token_count: int  # Number of tokens in chunk
    source_url: str  # Original source URL
    created_at: str  # ISO timestamp
    url_hash: str  # SHA256 hash of URL (partition key)


class IVectorStorage(Protocol):
    """Vector storage for webpage chunks with embeddings (Single Responsibility)."""

    async def store_chunks(
        self,
        url: str,
        chunks: List[Dict],
        ttl_hours: int
    ) -> int:
        """Store webpage chunks with embeddings and TTL.

        Args:
            url: Source URL (will be hashed for partition key)
            chunks: List of dicts with keys: chunk_id, chunk_text, embedding_vector,
                   chunk_index, token_count
            ttl_hours: Time-to-live in hours

        Returns:
            Number of chunks stored

        Raises:
            ValueError: If url or chunks are invalid
        """
        ...

    async def get_chunks_by_url(self, url: str) -> Optional[List[VectorChunk]]:
        """Retrieve all chunks for a URL (cache check).

        Args:
            url: Source URL to look up

        Returns:
            List of VectorChunk objects if found and not expired, None otherwise
        """
        ...

    async def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[VectorChunk]:
        """Search for most similar chunks using cosine similarity.

        Args:
            query_embedding: Query vector to compare against
            top_k: Number of top results to return

        Returns:
            List of VectorChunk objects sorted by similarity (highest first)

        Note:
            Uses client-side cosine similarity computation.
            For production scale, consider Pinecone/Weaviate/pgvector.
        """
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
