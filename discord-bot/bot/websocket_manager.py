"""WebSocket manager for Discord bot."""
import sys
sys.path.insert(0, '/shared')

import websockets
import json
import asyncio
from typing import Callable, Optional
import logging_client

# Initialize logger
logger = logging_client.setup_logger('discord-bot')


class WebSocketManager:
    """Manages WebSocket connection to FastAPI."""

    def __init__(self, fastapi_url: str):
        self.fastapi_url = fastapi_url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.reconnect_delay = 5
        self.bot_id: Optional[str] = None  # Store for reconnection
        self.max_reconnect_delay = 60  # Cap exponential backoff
        self.ping_task: Optional[asyncio.Task] = None  # Heartbeat task

    async def connect(self, bot_id: str):
        """
        Connect to FastAPI WebSocket.

        Args:
            bot_id: Bot identifier for registration
        """
        # Store bot_id for reconnection
        self.bot_id = bot_id

        try:
            # Connect with longer ping interval (60s) and timeout (120s)
            self.websocket = await websockets.connect(
                self.fastapi_url,
                ping_interval=60,
                ping_timeout=120
            )

            # Send identification
            await self.websocket.send(json.dumps({'bot_id': bot_id}))

            # Wait for acknowledgment
            response = await self.websocket.recv()
            data = json.loads(response)

            if data.get('type') == 'connected':
                self.connected = True
                logger.info(f"✅ WebSocket connected to FastAPI")

                # Start heartbeat task
                self._start_heartbeat()
            else:
                raise Exception("Failed to connect to FastAPI")

        except Exception as e:
            logger.error(f"❌ WebSocket connection error: {e}")
            await asyncio.sleep(self.reconnect_delay)
            await self.connect(bot_id)

    async def disconnect(self):
        """Disconnect from FastAPI WebSocket."""
        self.connected = False

        # Stop heartbeat task
        if self.ping_task:
            self.ping_task.cancel()
            try:
                await self.ping_task
            except asyncio.CancelledError:
                pass
            self.ping_task = None

        if self.websocket:
            await self.websocket.close()

    async def send_message(self, data: dict):
        """
        Send message request to FastAPI.

        Args:
            data: Message data dictionary

        Raises:
            Exception: If not connected
        """
        if not self.connected or not self.websocket:
            raise Exception("Not connected to FastAPI")

        await self.websocket.send(json.dumps(data))

    async def cancel_request(self, request_id: str):
        """
        Send cancellation request to FastAPI.

        Args:
            request_id: Request ID to cancel
        """
        if not self.connected or not self.websocket:
            return

        await self.websocket.send(json.dumps({
            'type': 'cancel',
            'request_id': request_id
        }))

    async def listen_for_responses(self, callback: Callable):
        """
        Listen for responses from FastAPI.

        Args:
            callback: Async function to call with received messages
        """
        current_delay = self.reconnect_delay  # Track current backoff delay

        while True:  # Always loop, don't depend on self.connected
            try:
                if not self.connected or not self.websocket:
                    await asyncio.sleep(1)
                    continue

                message = await self.websocket.recv()
                data = json.loads(message)

                # Pass to callback
                await callback(data)

                # Reset delay on successful message
                current_delay = self.reconnect_delay

            except websockets.ConnectionClosed:
                logger.warning("❌ WebSocket connection closed, reconnecting...")
                self.connected = False

                # Actually reconnect instead of breaking
                if self.bot_id:
                    try:
                        await asyncio.sleep(current_delay)
                        await self.connect(self.bot_id)

                        # Connection successful, reset delay
                        current_delay = self.reconnect_delay
                        logger.info("✅ Reconnected successfully")

                    except Exception as e:
                        # Exponential backoff
                        logger.error(f"❌ Reconnection failed: {e}")
                        current_delay = min(current_delay * 2, self.max_reconnect_delay)
                        logger.info(f"🔄 Next retry in {current_delay}s...")
                else:
                    logger.error("❌ Cannot reconnect: bot_id not set")
                    break  # Only break if we have no way to reconnect

            except Exception as e:
                logger.error(f"❌ WebSocket listen error: {e}")
                await asyncio.sleep(1)

    def _start_heartbeat(self):
        """Start heartbeat task to keep connection alive."""
        if self.ping_task:
            self.ping_task.cancel()

        self.ping_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        """Send periodic pings to keep WebSocket alive."""
        try:
            while self.connected and self.websocket:
                await asyncio.sleep(30)  # Ping every 30 seconds
                if self.connected and self.websocket:
                    try:
                        await self.websocket.send(json.dumps({'type': 'ping'}))
                    except Exception as e:
                        logger.warning(f"⚠️  Heartbeat ping failed: {e}")
                        break
        except asyncio.CancelledError:
            pass  # Task cancelled during disconnect
