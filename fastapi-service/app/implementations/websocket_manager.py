"""WebSocket connection management."""
import sys
sys.path.insert(0, '/shared')

import random
from typing import Dict, Literal
from fastapi import WebSocket

from app.interfaces.websocket import WebSocketInterface
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')


def get_random_status_message(status_type: str) -> str:
    """
    Get randomized status message for given type.

    Args:
        status_type: Type of status ('processing_files', 'thinking', 'retrying')

    Returns:
        Formatted status message with newlines
    """
    message_pools = {
        'processing_files': [
            '*Processing files...*',
            '*Analyzing files...*',
            '*Reading your files...*',
            '*Examining attachments...*',
        ],
        'thinking': [
            '*Thinking...*',
            '*Processing...*',
            '*Working on it...*',
            '*One moment...*',
            '*Analyzing...*',
        ],
        'retrying': [
            '*Retrying with non-streaming mode...*'  # Single option (no randomization)
        ]
    }

    messages = message_pools.get(status_type, ['*Processing...*'])
    return random.choice(messages) + '\n\n'


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

    async def send_status_indicator(
        self,
        bot_id: str,
        channel_id: str,
        message_id: str,
        status_type: Literal['processing_files', 'thinking', 'retrying'],
        request_id: str = 'pending',
        message_channel_id: str = None
    ) -> None:
        """
        Send status indicator message (centralized status message logic).

        Args:
            bot_id: Bot ID to send to
            channel_id: Thread/channel ID
            message_id: Original user message ID
            status_type: Type of status to send
            request_id: Request ID ('pending' for pre-queue, actual ID for queue processing)
            message_channel_id: Original message channel (defaults to channel_id)

        Status types:
            - 'processing_files': File attachment processing (OCR, images)
            - 'thinking': Request queued and being routed/processed
            - 'retrying': Streaming failed, retrying with non-streaming
        """
        # Get randomized status message
        status_message = get_random_status_message(status_type)

        await self.send_to_client(bot_id, {
            'type': 'early_status',
            'request_id': request_id,
            'content': status_message,
            'channel_id': channel_id,
            'message_id': message_id,
            'message_channel_id': message_channel_id or channel_id
        })
