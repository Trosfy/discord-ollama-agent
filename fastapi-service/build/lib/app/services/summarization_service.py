"""Conversation summarization service."""
from typing import List, Dict

from app.interfaces.storage import StorageInterface
from app.interfaces.llm import LLMInterface
from app.config import settings


class SummarizationService:
    """Handles conversation summarization when context gets too large."""

    SUMMARIZATION_PROMPT = """
You are a conversation summarizer. Create a concise summary of the conversation below.

**Focus on:**
1. **What the user specifically requested** (their main goals/questions)
2. **What actions were taken** (code written, problems solved, decisions made)
3. **Key technical points** (important concepts, gotchas, edge cases discussed)
4. **Unresolved items** (anything left to address)

**Format:**
- Write in past tense
- Use bullet points for clarity
- Preserve technical terms and code snippets (summarized)
- Max 500 tokens

**Conversation to summarize:**
{conversation}

**Summary:**
"""

    def __init__(self, storage: StorageInterface, llm: LLMInterface):
        """
        Initialize summarization service.

        Args:
            storage: Storage interface for message persistence
            llm: LLM interface for generating summaries
        """
        self.storage = storage
        self.llm = llm

    async def summarize_and_prune(
        self,
        thread_id: str,
        messages: List[Dict],
        user_id: str
    ) -> List[Dict]:
        """
        Summarize conversation and prune old messages.
        Returns updated context with summary.

        Args:
            thread_id: Thread identifier
            messages: List of message dictionaries
            user_id: User ID for the summary attribution

        Returns:
            Updated context with summary replacing old messages
        """
        # Keep last 5 messages, summarize the rest
        messages_to_summarize = messages[:-5]
        messages_to_keep = messages[-5:]

        if not messages_to_summarize:
            return messages

        # Format conversation for summarization
        conversation_text = self._format_for_summary(messages_to_summarize)

        # Generate summary using same model
        summary_response = await self.llm.generate(
            context=[{
                'role': 'user',
                'content': self.SUMMARIZATION_PROMPT.format(
                    conversation=conversation_text
                )
            }],
            model=settings.OLLAMA_SUMMARIZATION_MODEL,
            temperature=0.3  # Lower temp for factual summary
        )

        summary_content = summary_response['content']

        # Delete old messages from database
        timestamps = [msg['message_timestamp'] for msg in messages_to_summarize]
        await self.storage.delete_messages(thread_id, timestamps)

        # Add summary to database
        await self.storage.add_message(
            thread_id=thread_id,
            message_id=f"summary_{thread_id}_{len(messages_to_summarize)}",
            role='system',
            content=f"[SUMMARY OF PREVIOUS CONVERSATION]\n{summary_content}",
            token_count=len(summary_content.split()),
            user_id=user_id,
            model_used=settings.OLLAMA_SUMMARIZATION_MODEL,
            is_summary=True
        )

        # Return updated context
        return [{
            'role': 'system',
            'content': f"[SUMMARY OF PREVIOUS CONVERSATION]\n{summary_content}",
            'token_count': len(summary_content.split()),
            'message_timestamp': 'summary'
        }] + messages_to_keep

    def _format_for_summary(self, messages: List[Dict]) -> str:
        """
        Format messages for summarization prompt.

        Args:
            messages: List of message dictionaries

        Returns:
            Formatted conversation string
        """
        formatted = []
        for msg in messages:
            role = msg['role'].upper()
            content = msg['content']
            formatted.append(f"{role}: {content}")
        return "\n\n".join(formatted)
