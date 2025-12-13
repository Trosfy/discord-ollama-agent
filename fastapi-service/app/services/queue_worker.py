"""Background worker to process queue requests."""
import sys
sys.path.insert(0, '/shared')

import asyncio
import time
from typing import Optional

from app.interfaces.queue import QueueInterface
from app.interfaces.websocket import WebSocketInterface
from app.services.orchestrator import Orchestrator
from app.implementations.websocket_manager import get_random_status_message
from app.config import settings
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
        Process a single request with streaming support.

        Args:
            request: Request dictionary from queue
        """
        request_id = request['request_id']
        bot_id = request.get('bot_id')

        # Check if streaming is enabled
        use_streaming = settings.ENABLE_STREAMING

        try:
            # Send processing notification
            if bot_id:
                await self.ws_manager.send_to_client(bot_id, {
                    'type': 'processing',
                    'request_id': request_id
                })

            # Process with streaming if enabled
            if use_streaming:
                logger.debug(f"📡 Processing request {request_id} with streaming enabled")
                result = await self._process_with_streaming(request)
            else:
                logger.debug(f"📡 Processing request {request_id} without streaming")
                result = await self.orchestrator.process_request(request)

            # Mark as complete
            await self.queue.mark_complete(request_id, result)

            # Send final result (unified for both streaming and non-streaming)
            # Both modes now use 'stream_chunk' - streaming already sent chunks, non-streaming sends 1 chunk
            if bot_id and not use_streaming:
                # For non-streaming, send as single complete chunk (same as streaming final chunk)
                await self.ws_manager.send_to_client(bot_id, {
                    'type': 'stream_chunk',  # ✅ Unified message type
                    'request_id': request_id,
                    'content': result['response'],  # ✅ Use 'content' key (same as streaming)
                    'is_complete': True,  # ✅ Single chunk = complete
                    'artifacts': result.get('artifacts', []),  # ✅ Include artifacts in final chunk
                    'channel_id': request['channel_id'],
                    'message_id': request['message_id'],
                    'message_channel_id': request.get('message_channel_id')
                })
            # Note: Streaming mode already sends final chunk with artifacts in _process_with_streaming (line 269)

        except Exception as e:
            logger.error(f"❌ Request {request_id} failed: {e}")

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
                        'message_id': request['message_id'],
                        'message_channel_id': request.get('message_channel_id'),
                        'user_id': request['user_id']
                    })

    async def _process_with_streaming(self, request: dict) -> dict:
        """
        Process request with streaming callback.

        Args:
            request: Request dictionary

        Returns:
            Result dictionary with final response
        """
        request_id = request['request_id']
        bot_id = request.get('bot_id')

        # Send "Thinking..." status immediately (before routing/processing)
        # Use stream_chunk to reuse existing "Processing files..." message if present
        if bot_id:
            await self.ws_manager.send_to_client(bot_id, {
                'type': 'stream_chunk',  # ✅ Changed from early_status to stream_chunk
                'request_id': request_id,
                'content': get_random_status_message('thinking'),
                'is_complete': False,
                'channel_id': request['channel_id'],
                'message_id': request['message_id'],
                'message_channel_id': request.get('message_channel_id')
            })
            logger.debug(f"📤 Sent thinking status as stream_chunk for request {request_id}")

        # Streaming state
        last_update_time = 0
        UPDATE_INTERVAL = settings.STREAM_CHUNK_INTERVAL  # Default 0.5 seconds

        async def stream_callback(content: str):
            """Called for each LLM chunk - throttled to avoid Discord rate limits."""
            nonlocal last_update_time

            # Throttle updates
            current_time = time.time()
            if current_time - last_update_time < UPDATE_INTERVAL:
                return  # Skip this update

            last_update_time = current_time

            # Send chunk to Discord bot
            if bot_id:
                try:
                    await self.ws_manager.send_to_client(bot_id, {
                        'type': 'stream_chunk',
                        'request_id': request_id,
                        'content': content,
                        'is_complete': False,
                        'channel_id': request['channel_id'],
                        'message_id': request['message_id'],
                        'message_channel_id': request.get('message_channel_id')
                    })
                except Exception as e:
                    logger.warning(f"⚠️  Failed to send stream chunk: {e}")

        # Process with streaming
        try:
            result = await self.orchestrator.process_request_stream(
                request,
                stream_callback
            )

            # Send final chunk with complete flag
            if bot_id:
                final_content = result['response']

                # Check if response is empty (stuck on status indicator)
                if not final_content or not final_content.strip():
                    logger.warning(f"⚠️  Streaming returned empty response, retrying with non-streaming mode")

                    # Get route_config from streaming result to reuse
                    route_config = result.get('route_config')
                    if not route_config:
                        logger.warning(f"⚠️  No route_config in streaming result, will route again")

                    # Retry up to 3 times with non-streaming mode
                    MAX_RETRIES = 3
                    final_content = None

                    for retry_attempt in range(1, MAX_RETRIES + 1):
                        # Send retry status with attempt number
                        retry_status = f'*Retrying with non-streaming mode (attempt {retry_attempt}/{MAX_RETRIES})...*\n\n'
                        await self.ws_manager.send_to_client(bot_id, {
                            'type': 'stream_chunk',  # ✅ Updates existing "Thinking..." message
                            'request_id': request_id,
                            'content': retry_status,
                            'is_complete': False,
                            'channel_id': request['channel_id'],
                            'message_id': request['message_id'],
                            'message_channel_id': request.get('message_channel_id')
                        })

                        # Retry with non-streaming (bypasses SDK streaming bug)
                        try:
                            # Pass route_config to skip routing (saves ~7 seconds)
                            result = await self.orchestrator.process_request(
                                request,
                                route_config=route_config  # ✅ Reuse route from streaming
                            )
                            final_content = result['response']

                            # Check if retry succeeded
                            if final_content and final_content.strip():
                                logger.info(f"✅ Non-streaming retry attempt {retry_attempt} successful: {len(final_content)} chars")
                                break  # Success - exit retry loop
                            else:
                                logger.warning(f"⚠️  Retry attempt {retry_attempt} returned empty response")
                                final_content = None  # Reset for next attempt

                        except Exception as e:
                            logger.error(f"❌ Non-streaming retry attempt {retry_attempt} failed: {e}")
                            final_content = None

                        # If this was the last attempt and still failed, show error
                        if retry_attempt == MAX_RETRIES and (not final_content or not final_content.strip()):
                            logger.error(f"❌ All {MAX_RETRIES} retry attempts failed for request {request_id}")

                            # Send error message as last resort
                            error_content = f"❌ _Unable to generate response (tried {MAX_RETRIES} times)_"
                            await self.ws_manager.send_to_client(bot_id, {
                                'type': 'stream_chunk',
                                'request_id': request_id,
                                'content': error_content,
                                'is_complete': True,
                                'channel_id': request['channel_id'],
                                'message_id': request['message_id'],
                                'message_channel_id': request.get('message_channel_id'),
                                'error': True
                            })
                            return result  # Return original failed result

                # Normal flow OR successful retry - send final chunk
                await self.ws_manager.send_to_client(bot_id, {
                    'type': 'stream_chunk',
                    'request_id': request_id,
                    'content': final_content,
                    'is_complete': True,
                    'channel_id': request['channel_id'],
                    'message_id': request['message_id'],
                    'message_channel_id': request.get('message_channel_id'),
                    'artifacts': result.get('artifacts', [])
                })

                # Unload model after streaming is complete and transmitted
                # This prevents race condition where model is unloaded while chunks are still queued
                route_config = result.get('route_config', {})
                if route_config.get('route') == 'SELF_HANDLE':
                    model_to_unload = route_config.get('model')
                    if model_to_unload == settings.ROUTER_MODEL:
                        from app.utils.model_utils import force_unload_model
                        await force_unload_model(settings.ROUTER_MODEL)
                        logger.debug("🔽 Unloaded router after streaming transmission complete")

            return result

        except Exception as e:
            # Streaming failed - send error as final chunk
            logger.error(f"❌ Streaming failed for request {request_id}: {e}")

            if bot_id:
                await self.ws_manager.send_to_client(bot_id, {
                    'type': 'stream_chunk',
                    'request_id': request_id,
                    'content': f"❌ Generation interrupted: {str(e)}",
                    'is_complete': True,
                    'channel_id': request['channel_id'],
                    'message_id': request['message_id'],
                    'message_channel_id': request.get('message_channel_id'),
                    'error': True
                })

            raise  # Re-raise for retry handling
