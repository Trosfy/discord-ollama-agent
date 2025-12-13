"""WebSocket connection management."""
import sys
sys.path.insert(0, '/shared')

from typing import Dict
from fastapi import WebSocket

from app.interfaces.websocket import WebSocketInterface
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')


class WebSocketManager(WebSocketInterface):
    """Manages WebSocket connections to Discord bots."""

    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}

    async def register(self, client_id: str, websocket: WebSocket) -> None:
        """
        Register a new WebSocket connection.

        Args:
            client_id: Unique identifier for the client
            websocket: FastAPI WebSocket instance
        """
        self.connections[client_id] = websocket

    async def unregister(self, client_id: str) -> None:
        """
        Unregister a WebSocket connection.

        Args:
            client_id: Client identifier to unregister
        """
        if client_id in self.connections:
            del self.connections[client_id]

    async def send_to_client(self, client_id: str, message: Dict) -> bool:
        """
        Send message to specific client.

        Args:
            client_id: Client identifier
            message: Message dictionary to send

        Returns:
            True if sent successfully, False if client not connected
        """
        if client_id not in self.connections:
            return False

        try:
            await self.connections[client_id].send_json(message)
            return True
        except Exception as e:
            logger.error(f"Error sending to client {client_id}: {e}")
            await self.unregister(client_id)
            return False

    async def broadcast(self, message: Dict) -> None:
        """
        Broadcast message to all connected clients.

        Args:
            message: Message dictionary to broadcast
        """
        disconnected = []

        for client_id, websocket in self.connections.items():
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected:
            await self.unregister(client_id)

    def is_connected(self, client_id: str) -> bool:
        """
        Check if client is connected.

        Args:
            client_id: Client identifier

        Returns:
            True if connected, False otherwise
        """
        return client_id in self.connections

    def count_connections(self) -> int:
        """
        Get number of active connections.

        Returns:
            Number of active WebSocket connections
        """
        return len(self.connections)
