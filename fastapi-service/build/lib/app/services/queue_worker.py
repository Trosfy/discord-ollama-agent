"""Background worker to process queue requests."""
import sys
sys.path.insert(0, '/shared')

import asyncio
from typing import Optional

from app.interfaces.queue import QueueInterface
from app.interfaces.websocket import WebSocketInterface
from app.services.orchestrator import Orchestrator
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')


class QueueWorker:
    """Background worker that processes queued requests."""

    def __init__(
        self,
        queue: QueueInterface,
        orchestrator: Orchestrator,
        ws_manager: WebSocketInterface
    ):
        """
        Initialize queue worker.

        Args:
            queue: Queue interface for retrieving requests
            orchestrator: Orchestrator for processing requests
            ws_manager: WebSocket manager for sending results
        """
        self.queue = queue
        self.orchestrator = orchestrator
        self.ws_manager = ws_manager
        self.worker_task: Optional[asyncio.Task] = None
        self.running = False

    async def start(self):
        """Start the worker."""
        self.running = True
        self.worker_task = asyncio.create_task(self._process_loop())

    async def stop(self):
        """Stop the worker gracefully."""
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

    async def _process_loop(self):
        """Main processing loop."""
        while self.running:
            try:
                # Get next request
                request = await self.queue.dequeue()

                if not request:
                    await asyncio.sleep(1)
                    continue

                # Process request
                await self._process_request(request)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(1)

    async def _process_request(self, request: dict):
        """
        Process a single request.

        Args:
            request: Request dictionary from queue
        """
        request_id = request['request_id']
        bot_id = request.get('bot_id')

        try:
            # Send processing notification
            if bot_id:
                await self.ws_manager.send_to_client(bot_id, {
                    'type': 'processing',
                    'request_id': request_id
                })

            # Process via orchestrator
            result = await self.orchestrator.process_request(request)

            # Mark as complete
            await self.queue.mark_complete(request_id, result)

            # Send result to Discord bot
            if bot_id:
                await self.ws_manager.send_to_client(bot_id, {
                    'type': 'result',
                    'request_id': request_id,
                    'response': result['response'],
                    'tokens_used': result['tokens_used'],
                    'channel_id': request['channel_id'],
                    'message_id': request['message_id']
                })

        except Exception as e:
            # Mark as failed (handles retries)
            requeued = await self.queue.mark_failed(request_id, str(e))

            # Notify if failed after max retries
            if not requeued and request['attempt'] >= 2:
                if bot_id:
                    await self.ws_manager.send_to_client(bot_id, {
                        'type': 'failed',
                        'request_id': request_id,
                        'error': str(e),
                        'attempts': request['attempt'] + 1,
                        'channel_id': request['channel_id'],
                        'user_id': request['user_id']
                    })
