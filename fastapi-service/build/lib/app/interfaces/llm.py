"""LLM interface for model abstraction."""
from abc import ABC, abstractmethod
from typing import List, Dict, AsyncIterator, Optional


class LLMInterface(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        context: List[Dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        user_base_prompt: Optional[str] = None
    ) -> Dict:
        """
        Generate complete response.

        Args:
            context: Conversation history
            model: Model to use (optional)
            temperature: Temperature for generation
            user_base_prompt: User's custom base prompt (optional)

        Returns:
            Dict with 'content', 'model', and optionally 'references' keys.
            'references' is a list of dicts with 'url' and 'title' keys for fetched webpages.
        """
        pass

    @abstractmethod
    async def generate_stream(
        self,
        context: List[Dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        user_base_prompt: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Generate streaming response (for future implementation).

        Args:
            context: Conversation history
            model: Model to use (optional)
            temperature: Temperature for generation
            user_base_prompt: User's custom base prompt (optional)

        Yields:
            Chunks of generated text
        """
        pass

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if LLM service is available."""
        pass

    @abstractmethod
    async def generate_with_planning(
        self,
        context: List[Dict],
        temperature: float = 0.7,
        user_base_prompt: Optional[str] = None
    ) -> Dict:
        """
        Generate response using multi-agent planning workflow.

        Args:
            context: Conversation history
            temperature: Temperature for generation
            user_base_prompt: User's custom base prompt (optional)

        Returns:
            Dict with 'content', 'model', 'references', and optionally 'plan' keys
        """
        pass
