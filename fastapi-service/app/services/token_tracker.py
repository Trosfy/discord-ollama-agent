"""Token tracking and budget management."""
from typing import Dict

from app.interfaces.storage import ITokenTrackingStorage
from app.interfaces.llm import LLMInterface


class TokenTracker:
    """Manages token counting and budget tracking."""

    def __init__(self, storage: ITokenTrackingStorage, llm: LLMInterface):
        """
        Initialize token tracker.

        Args:
            storage: Token tracking storage interface
            llm: LLM interface for token counting
        """
        self.storage = storage
        self.llm = llm

    async def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        return await self.llm.count_tokens(text)

    async def has_budget(self, user: Dict, estimated_tokens: int) -> bool:
        """
        Check if user has sufficient token budget.

        Args:
            user: User data dictionary
            estimated_tokens: Estimated tokens needed

        Returns:
            True if user has sufficient budget, False otherwise
        """
        return user['tokens_remaining'] >= estimated_tokens

    async def update_usage(self, user_id: str, tokens_used: int) -> None:
        """
        Update user's token usage.

        Args:
            user_id: User ID
            tokens_used: Number of tokens consumed
        """
        await self.storage.update_user_tokens(user_id, tokens_used)

    async def get_remaining(self, user_id: str) -> int:
        """
        Get user's remaining tokens.

        Args:
            user_id: User ID

        Returns:
            Remaining tokens in budget
        """
        tokens = await self.storage.get_user_tokens(user_id)
        return tokens['tokens_remaining'] if tokens else 0
