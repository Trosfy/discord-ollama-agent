"""Queue interface for request management."""
from abc import ABC, abstractmethod
from typing import Optional, Dict


class QueueInterface(ABC):
    """Abstract interface for request queue with visibility timeout."""

    @abstractmethod
    async def enqueue(self, request: Dict) -> str:
        """
        Add request to queue.

        Returns:
            request_id: Unique identifier for tracking
        """
        pass

    @abstractmethod
    async def dequeue(self) -> Optional[Dict]:
        """
        Get next request from queue.
        Marks request as in-flight with visibility timeout.

        Returns:
            Request dict or None if queue empty
        """
        pass

    @abstractmethod
    async def get_status(self, request_id: str) -> Dict:
        """Get current status of a request."""
        pass

    @abstractmethod
    async def get_position(self, request_id: str) -> int:
        """Get queue position (0 = not in queue, 1 = next, etc.)"""
        pass

    @abstractmethod
    async def mark_complete(
        self,
        request_id: str,
        result: Dict
    ) -> None:
        """Mark request as completed successfully."""
        pass

    @abstractmethod
    async def mark_failed(
        self,
        request_id: str,
        error: str
    ) -> bool:
        """
        Mark request as failed and handle retry logic.

        Returns:
            True if requeued, False if max retries exceeded
        """
        pass

    @abstractmethod
    async def cancel(self, request_id: str) -> bool:
        """
        Cancel a queued request.

        Returns:
            True if cancelled, False if already processing
        """
        pass

    @abstractmethod
    def size(self) -> int:
        """Get current queue size."""
        pass

    @abstractmethod
    def is_full(self) -> bool:
        """Check if queue is at capacity."""
        pass
