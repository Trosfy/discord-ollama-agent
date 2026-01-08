"""Background worker to process queue requests."""
import sys
sys.path.insert(0, '/shared')

import asyncio
import time
from typing import Optional

from app.interfaces.queue import QueueInterface
from app.interfaces.websocket import WebSocketInterface
from app.services.orchestrator import Orchestrator
from app.services.response_formatters import get_formatter
from app.implementations.websocket_manager import get_random_status_message
from app.config import settings, get_active_profile
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

        Handles both Discord (bot_id) and Web UI (webui_client_id) connections.
        Uses ws_manager for unified WebSocket management.

        Args:
            request: Request dictionary from queue
        """
        request_id = request['request_id']
        bot_id = request.get('bot_id')
        webui_client_id = request.get('webui_client_id')  # Web UI client ID

        # Check if streaming is enabled
        use_streaming = settings.ENABLE_STREAMING

        try:
            # Send processing notification using Strategy Pattern
            formatter = get_formatter(request)
            processing_msg = await formatter.format_processing(request_id)

            if bot_id:
                await self.ws_manager.send_to_client(bot_id, processing_msg)
            elif webui_client_id:
                await self.ws_manager.send_to_client(webui_client_id, processing_msg)

            # Process with streaming if enabled
            if use_streaming:
                logger.debug(f"📡 Processing request {request_id} with streaming enabled")
                result = await self._process_with_streaming(request)
            else:
                logger.debug(f"📡 Processing request {request_id} without streaming")
                result = await self.orchestrator.process_request(request)

            # Mark as complete
            await self.queue.mark_complete(request_id, result)

            # Send final result for non-streaming mode (streaming already sent in _process_with_streaming)
            if bot_id and not use_streaming:
                # Format completion response using Strategy Pattern
                completion_msg = await formatter.format_completion(
                    request_id,
                    result,
                    request['channel_id'],
                    request['message_id'],
                    request.get('message_channel_id')
                )
                await self.ws_manager.send_to_client(bot_id, completion_msg)
            # Note: Streaming mode already sends final chunk with artifacts in _process_with_streaming

        except Exception as e:
            logger.error(f"❌ Request {request_id} failed: {e}")

            # Mark as failed (handles retries)
            requeued = await self.queue.mark_failed(request_id, str(e))

            # Notify if failed after max retries using Strategy Pattern
            if not requeued and request['attempt'] >= 2:
                formatter = get_formatter(request)
                failed_msg = await formatter.format_failed(
                    request_id,
                    str(e),
                    request['attempt'] + 1,
                    request.get('channel_id'),
                    request.get('message_id'),
                    request.get('message_channel_id'),
                    request.get('user_id')
                )

                if bot_id:
                    await self.ws_manager.send_to_client(bot_id, failed_msg)
                elif webui_client_id:
                    await self.ws_manager.send_to_client(webui_client_id, failed_msg)

    async def _process_with_streaming(self, request: dict) -> dict:
        """
        Process request with streaming callback.

        Handles both Discord (bot_id) and Web UI (webui_client_id) connections.
        Uses ws_manager for unified WebSocket management.

        Args:
            request: Request dictionary

        Returns:
            Result dictionary with final response
        """
        request_id = request['request_id']
        bot_id = request.get('bot_id')
        webui_client_id = request.get('webui_client_id')  # Web UI client ID

        # Get formatter for this client type
        formatter = get_formatter(request)

        # Send "Thinking..." status immediately (before routing/processing)
        # Use stream_chunk to reuse existing "Processing files..." message if present
        if bot_id:
            thinking_msg = await formatter.format_stream_update(
                request_id,
                get_random_status_message('thinking'),
                request['channel_id'],
                request['message_id'],
                request.get('message_channel_id')
            )
            await self.ws_manager.send_to_client(bot_id, thinking_msg)
            logger.debug(f"📤 Sent thinking status as stream_chunk for request {request_id}")
        elif webui_client_id:
            # Web UI: no need for "thinking" message, start streaming immediately
            pass

        # Streaming state
        last_update_time = 0
        last_sent_length = 0  # Track what we've sent to Web UI (for delta calculation)
        UPDATE_INTERVAL = settings.STREAM_CHUNK_INTERVAL if bot_id else 0.05  # Web UI: faster updates

        async def stream_callback(content: str):
            """
            Called for each LLM chunk - throttled to avoid rate limits.

            Args:
                content: Full accumulated message content from orchestrator

            Behavior:
                - Discord: Sends full content (bot will edit message with full text)
                - Web UI: Sends only delta (frontend appends new tokens)
            """
            nonlocal last_update_time, last_sent_length

            # Throttle updates
            current_time = time.time()
            if current_time - last_update_time < UPDATE_INTERVAL:
                return  # Skip this update

            last_update_time = current_time

            # Determine what to send based on client type
            client_id = bot_id or webui_client_id
            if client_id:
                try:
                    # Discord: Send full content (bot will edit message with full text)
                    if bot_id:
                        chunk_msg = await formatter.format_stream_update(
                            request_id,
                            content,  # Full accumulated content
                            request.get('channel_id'),
                            request.get('message_id'),
                            request.get('message_channel_id')
                        )
                        await self.ws_manager.send_to_client(client_id, chunk_msg)

                    # Web UI: Send only delta (frontend will append to existing message)
                    elif webui_client_id:
                        if len(content) > last_sent_length:
                            # Calculate delta (new content since last send)
                            delta = content[last_sent_length:]
                            chunk_msg = await formatter.format_stream_update(
                                request_id,
                                delta,  # Only the new delta
                                request.get('channel_id'),
                                request.get('message_id'),
                                request.get('message_channel_id')
                            )
                            await self.ws_manager.send_to_client(client_id, chunk_msg)
                            last_sent_length = len(content)  # Update tracking

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
                        # Send retry status with attempt number using Strategy Pattern
                        retry_status = f'*Retrying with non-streaming mode (attempt {retry_attempt}/{MAX_RETRIES})...*\n\n'
                        retry_msg = await formatter.format_stream_update(
                            request_id,
                            retry_status,
                            request['channel_id'],
                            request['message_id'],
                            request.get('message_channel_id')
                        )
                        await self.ws_manager.send_to_client(bot_id, retry_msg)

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

                            # Send error message as last resort using Strategy Pattern
                            error_content = f"❌ _Unable to generate response (tried {MAX_RETRIES} times)_"
                            error_msg = await formatter.format_error(
                                request_id,
                                error_content,
                                request.get('channel_id'),
                                request.get('message_id'),
                                request.get('message_channel_id')
                            )
                            # Override type to indicate completion with error
                            error_msg['is_complete'] = True
                            error_msg['error'] = True
                            await self.ws_manager.send_to_client(bot_id, error_msg)
                            return result  # Return original failed result

                # Normal flow OR successful retry - send final chunk using Strategy Pattern
                completion_msg = await formatter.format_completion(
                    request_id,
                    result,
                    request['channel_id'],
                    request['message_id'],
                    request.get('message_channel_id')
                )
                await self.ws_manager.send_to_client(bot_id, completion_msg)

            elif webui_client_id:
                # Web UI: Send final "done" message using Strategy Pattern
                completion_msg = await formatter.format_completion(
                    request_id,
                    result,
                    request.get('channel_id'),
                    request.get('message_id'),
                    request.get('message_channel_id')
                )
                await self.ws_manager.send_to_client(webui_client_id, completion_msg)

            # Unload model after streaming complete (conservative mode only)
            route_config = result.get('route_config', {})
            if route_config.get('route') == 'SELF_HANDLE':
                model_to_unload = route_config.get('model')
                if model_to_unload == settings.ROUTER_MODEL:
                    if settings.VRAM_CONSERVATIVE_MODE:
                        # Conservative mode (16GB): Force-unload after each request
                        from app.utils.model_utils import force_unload_model
                        await force_unload_model(settings.ROUTER_MODEL)
                        logger.debug("🔽 Conservative mode: Unloaded router after streaming")
                    else:
                        # High-VRAM profiles (performance/balanced): Trust keep_alive + orchestrator
                        profile_name = get_active_profile().profile_name.title()
                        logger.debug(f"💤 {profile_name} profile: Router stays loaded (keep_alive=30m)")

            return result

        except Exception as e:
            # Streaming failed - check if circuit breaker can recover
            logger.error(f"❌ Streaming failed for request {request_id}: {e}")

            # Check if this is a circuit breaker-triggerable error (SGLang connection failure)
            error_msg_str = str(e).lower()
            is_sglang_error = (
                "connection" in error_msg_str or
                "connect" in error_msg_str or
                "refused" in error_msg_str
            )

            # If this might trigger circuit breaker, give it time to switch profile and retry
            if is_sglang_error and self.orchestrator.profile_manager:
                logger.info(f"🔄 SGLang connection error detected, waiting for circuit breaker...")

                # Wait for circuit breaker to trigger and profile switch to complete
                # The circuit breaker runs asynchronously via asyncio.create_task() and needs time to:
                # 1. Record crash (sync)
                # 2. Notify observers via create_task (async)
                # 3. ProfileManager acquires lock (async)
                # 4. Switch profile (sync)
                # Total time needed: ~1-2 seconds under load
                await asyncio.sleep(1.5)  # Increased to ensure circuit breaker completes

                # Check if we're now in fallback mode (circuit breaker triggered)
                if self.orchestrator.profile_manager.is_in_fallback():
                    logger.info(f"✅ Circuit breaker triggered during request - retrying with conservative profile...")

                    # Send retry status to user
                    client_id = bot_id or webui_client_id
                    if client_id:
                        retry_status = '*Falling back to alternative model...*\n\n'
                        retry_msg = await formatter.format_stream_update(
                            request_id,
                            retry_status,
                            request['channel_id'],
                            request['message_id'],
                            request.get('message_channel_id')
                        )
                        await self.ws_manager.send_to_client(client_id, retry_msg)

                    # Retry with conservative profile
                    try:
                        result = await self.orchestrator.process_request_stream(
                            request,
                            stream_callback
                        )

                        # SUCCESS! Send final chunk (format_completion expects full result dict)
                        if bot_id:
                            completion_msg = await formatter.format_completion(
                                request_id,
                                result,  # Pass full dict (formatter extracts result['response'])
                                request['channel_id'],
                                request.get('message_id'),
                                request.get('message_channel_id')
                            )
                            await self.ws_manager.send_to_client(bot_id, completion_msg)
                        elif webui_client_id:
                            completion_msg = await formatter.format_completion(
                                request_id,
                                result,  # Pass full dict (formatter extracts metadata)
                                request.get('conversation_id'),
                                request.get('message_id'),
                                request.get('message_channel_id')
                            )
                            await self.ws_manager.send_to_client(webui_client_id, completion_msg)

                        logger.info(f"✅ Circuit breaker retry successful - request completed with conservative profile")
                        return result  # Success - don't raise exception

                    except Exception as retry_error:
                        logger.error(f"❌ Circuit breaker retry failed: {retry_error}")
                        # Fall through to send error message below

            # No circuit breaker recovery - send error as normal
            client_id = bot_id or webui_client_id
            if client_id:
                error_msg = await formatter.format_error(
                    request_id,
                    f"Generation interrupted: {str(e)}",
                    request.get('channel_id'),
                    request.get('message_id'),
                    request.get('message_channel_id')
                )
                # For Discord, mark as complete with error
                if bot_id:
                    error_msg['is_complete'] = True
                    error_msg['error'] = True
                await self.ws_manager.send_to_client(client_id, error_msg)

            raise  # Re-raise for retry handling
