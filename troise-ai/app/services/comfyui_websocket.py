"""WebSocket client for ComfyUI completion detection.

Implements IComfyUICompletionWaiter protocol for dependency inversion.
Provides real-time workflow completion detection instead of HTTP polling.

ComfyUI WebSocket Events:
- "executing": {prompt_id, node} - Node execution started (node=null means complete)
- "executed": {prompt_id, node, output} - Node finished with output
- "execution_success": {prompt_id} - Workflow completed successfully
- "execution_error": {prompt_id, exception_message} - Workflow failed
"""
import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

logger = logging.getLogger(__name__)


@dataclass
class ComfyUIProgress:
    """Progress event from ComfyUI WebSocket."""
    prompt_id: str
    node_id: Optional[str]
    event_type: str  # "executing", "executed", "execution_success", "execution_error"
    data: dict


class ComfyUIWebSocket:
    """WebSocket client for ComfyUI workflow completion detection.

    Implements IComfyUICompletionWaiter protocol (DIP).

    Usage:
        ws = ComfyUIWebSocket("http://localhost:8188")
        await ws.connect()
        success = await ws.wait_for_completion("prompt-123", timeout_seconds=900)
        await ws.disconnect()
    """

    # WebSocket keepalive settings
    PING_INTERVAL: int = 30
    PING_TIMEOUT: int = 10

    def __init__(self, host: str):
        """Initialize WebSocket client.

        Args:
            host: ComfyUI server URL (http:// or https://).
        """
        self._host = host.rstrip("/")

        # Convert HTTP URL to WebSocket URL
        ws_host = self._host.replace("http://", "ws://").replace("https://", "wss://")
        self._ws_url = ws_host

        self._websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._client_id: Optional[str] = None
        self._connected = False

    @property
    def client_id(self) -> Optional[str]:
        """Get the current client ID used for WebSocket connection."""
        return self._client_id

    async def connect(self) -> str:
        """Establish WebSocket connection to ComfyUI.

        Returns:
            The client_id used for this connection.

        Raises:
            WebSocketException: If connection fails.
        """
        self._client_id = str(uuid.uuid4())
        url = f"{self._ws_url}/ws?clientId={self._client_id}"

        logger.debug(f"Connecting to ComfyUI WebSocket: {url}")

        self._websocket = await websockets.connect(
            url,
            ping_interval=self.PING_INTERVAL,
            ping_timeout=self.PING_TIMEOUT,
        )
        self._connected = True

        logger.info(f"ComfyUI WebSocket connected (client_id={self._client_id})")
        return self._client_id

    async def disconnect(self) -> None:
        """Close WebSocket connection gracefully."""
        self._connected = False
        if self._websocket:
            try:
                await self._websocket.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket: {e}")
            finally:
                self._websocket = None
                logger.debug("ComfyUI WebSocket disconnected")

    async def wait_for_completion(
        self,
        prompt_id: str,
        timeout_seconds: float = 900
    ) -> bool:
        """Wait for a ComfyUI prompt to complete.

        Listens for WebSocket events and returns when the workflow finishes.
        Handles both successful completion and errors.

        Args:
            prompt_id: The ComfyUI prompt ID to wait for.
            timeout_seconds: Maximum time to wait (default 15 minutes).

        Returns:
            True if completed successfully, False on error/timeout.

        Raises:
            RuntimeError: If WebSocket is not connected.
        """
        if not self._connected or not self._websocket:
            raise RuntimeError("WebSocket not connected - call connect() first")

        start_time = asyncio.get_event_loop().time()
        logger.debug(f"Waiting for prompt {prompt_id} completion (timeout={timeout_seconds}s)")

        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            try:
                # Calculate remaining time
                elapsed = asyncio.get_event_loop().time() - start_time
                remaining = timeout_seconds - elapsed

                # Wait for message with timeout (use smaller chunk to stay responsive)
                message = await asyncio.wait_for(
                    self._websocket.recv(),
                    timeout=min(remaining, 60)  # Check at most every 60s
                )

                # Parse JSON message
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    # Binary data (preview images) - skip
                    continue

                event_type = data.get("type")
                event_data = data.get("data", {})

                # Check if this event is for our prompt
                event_prompt_id = event_data.get("prompt_id")
                if event_prompt_id != prompt_id:
                    continue

                # Log progress events
                node = event_data.get("node")
                if event_type == "executing":
                    if node:
                        logger.debug(f"Prompt {prompt_id}: executing node {node}")
                    else:
                        # node=null means execution complete
                        logger.info(f"Prompt {prompt_id}: execution complete (node=null)")
                        return True

                elif event_type == "execution_success":
                    logger.info(f"Prompt {prompt_id}: execution_success received")
                    return True

                elif event_type == "execution_error":
                    error_msg = event_data.get("exception_message", "Unknown error")
                    logger.error(f"Prompt {prompt_id}: execution_error - {error_msg}")
                    return False

                elif event_type == "executed":
                    # Node finished - log for debugging
                    logger.debug(f"Prompt {prompt_id}: node {node} executed")

            except asyncio.TimeoutError:
                # No message in 60s - continue waiting
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.debug(f"Prompt {prompt_id}: still waiting ({elapsed:.0f}s elapsed)")
                continue

            except ConnectionClosed as e:
                logger.error(f"WebSocket connection closed: {e}")
                self._connected = False
                return False

            except Exception as e:
                logger.error(f"Error receiving WebSocket message: {e}")
                return False

        # Timeout reached
        logger.warning(f"Prompt {prompt_id}: timeout after {timeout_seconds}s")
        return False

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is currently connected."""
        return self._connected and self._websocket is not None
