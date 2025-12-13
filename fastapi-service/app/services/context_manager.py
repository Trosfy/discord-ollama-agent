"""Context management service."""
from typing import List, Dict

from app.interfaces.storage import IConversationStorage


class ContextManager:
    """Manages conversation context retrieval and formatting."""

    def __init__(self, storage: IConversationStorage):
        """
        Initialize context manager.

        Args:
            storage: Conversation storage interface for retrieving messages
        """
        self.storage = storage

    async def get_thread_context(
        self,
        thread_id: str,
        user_id: str
    ) -> List[Dict]:
        """
        Get conversation context for a thread.
        Returns messages formatted for LLM consumption.

        Args:
            thread_id: Unique identifier for the conversation thread
            user_id: User ID for authorization (currently unused)

        Returns:
            List of message dictionaries with role, content, token_count, etc.
        """
        messages = await self.storage.get_thread_messages(thread_id)

        # Format for LLM
        context = []
        for msg in messages:
            context.append({
                'role': msg['role'],
                'content': msg['content'],
                'token_count': msg['token_count'],
                'message_timestamp': msg['message_timestamp']
            })

        return context
