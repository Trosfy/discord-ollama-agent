"""WebSocket connection management interface."""
from abc import ABC, abstractmethod
from typing import Dict
from fastapi import WebSocket


class WebSocketInterface(ABC):
    """Abstract interface for WebSocket connection management."""

    @abstractmethod
    async def register(self, client_id: str, websocket: WebSocket) -> None:
        """Register a new WebSocket connection."""
        pass

    @abstractmethod
    async def unregister(self, client_id: str) -> None:
        """Unregister a WebSocket connection."""
        pass

    @abstractmethod
    async def send_to_client(
        self,
        client_id: str,
        message: Dict
    ) -> bool:
        """
        Send message to specific client.

        Returns:
            True if sent, False if client not connected
        """
        pass

    @abstractmethod
    async def broadcast(self, message: Dict) -> None:
        """Broadcast message to all connected clients."""
        pass

    @abstractmethod
    def is_connected(self, client_id: str) -> bool:
        """Check if client is connected."""
        pass

    @abstractmethod
    def count_connections(self) -> int:
        """Get number of active connections."""
        pass
