"""Real-time streaming support for TROISE AI agents.

Provides streaming from Strands agents to WebSocket with:
- Think tag filtering (removes <think>...</think> blocks)
- Content validation (prevents Discord error 50006)
- Graceful fallback to non-streaming on failure
- Tool call tracking during streaming
- Throttling to prevent Discord rate limiting
"""
import logging
import re
import time
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from app.adapters.websocket.factory import get_message_builder

# Minimum chars before first streaming update (prevents Discord error 50006)
MIN_CONTENT_LENGTH = 20


if TYPE_CHECKING:
    from .context import ExecutionContext
    from app.core.interfaces.websocket import IWebSocketMessageBuilder

logger = logging.getLogger(__name__)


class StreamFilter:
    """Filter streaming content to remove <think> tags and citation markers.

    Uses character-by-character buffering to handle tags that
    may be split across multiple chunks.

    Filters:
    - <think>...</think> blocks (model reasoning)
    - 【{"cursor":X,"id":Y}】 markers (Qwen-style citation artifacts)
    """

    THINK_OPEN = '<think>'
    THINK_CLOSE = '</think>'
    # East Asian lenticular brackets used by some models for inline citations
    CITATION_OPEN = '【'
    CITATION_CLOSE = '】'

    def __init__(self):
        self.inside_think = False
        self.inside_citation = False
        self.buffer = ""
        self.citation_buffer = ""

    def process(self, chunk: str) -> str:
        """
        Filter chunk, removing <think> tags and citation markers.

        Args:
            chunk: Text chunk from streaming response.

        Returns:
            Filtered text with <think> content and citation markers removed.
        """
        output = []
        for char in chunk:
            # Handle citation markers first (【...】)
            if self.inside_citation:
                self.citation_buffer += char
                if char == self.CITATION_CLOSE:
                    # End of citation marker - check if it looks like a citation
                    if self._is_citation_artifact(self.citation_buffer):
                        # Discard the entire citation marker
                        pass
                    else:
                        # Not a citation, output the buffered content
                        output.append(self.citation_buffer)
                    self.inside_citation = False
                    self.citation_buffer = ""
                continue
            elif char == self.CITATION_OPEN:
                # Start of potential citation marker
                self.inside_citation = True
                self.citation_buffer = char
                continue

            # Handle think tags
            self.buffer += char
            if self.inside_think:
                # Inside think block - check for closing tag
                if self.buffer.endswith(self.THINK_CLOSE):
                    self.inside_think = False
                    self.buffer = ""
            else:
                # Outside think block
                if self.buffer.endswith(self.THINK_OPEN):
                    # Entered think block
                    self.inside_think = True
                    self.buffer = ""
                elif not self._could_be_tag_start():
                    # Not a potential tag start - output buffer
                    output.append(self.buffer)
                    self.buffer = ""
        return ''.join(output)

    def _could_be_tag_start(self) -> bool:
        """Check if current buffer could be start of a tag."""
        return (
            self.THINK_OPEN.startswith(self.buffer) or
            self.THINK_CLOSE.startswith(self.buffer)
        )

    def _is_citation_artifact(self, content: str) -> bool:
        """Check if buffered content is a citation artifact to filter.

        Matches patterns like: 【{"cursor":2,"id":9}】 or 【4†source】

        Args:
            content: Buffered content including brackets.

        Returns:
            True if this looks like a citation marker to remove.
        """
        # Check for JSON-style citation markers: 【{"cursor":X,"id":Y}】
        if '"cursor"' in content or '"id"' in content:
            return True
        # Check for numbered source markers: 【4†source】 or 【1:2†source】
        if '†' in content:
            return True
        # Check for simple numeric citations: 【1】【2】etc
        inner = content.strip(self.CITATION_OPEN + self.CITATION_CLOSE)
        if inner.isdigit():
            return True
        return False

    def flush(self) -> str:
        """Flush remaining buffer content.

        Call this at end of stream to get any buffered content.

        Returns:
            Remaining buffer content (empty if inside think block or citation).
        """
        result_parts = []

        # Flush citation buffer if not inside an incomplete citation
        if self.citation_buffer and not self.inside_citation:
            result_parts.append(self.citation_buffer)
            self.citation_buffer = ""

        # Flush think buffer if not inside think block
        if not self.inside_think:
            result_parts.append(self.buffer)
            self.buffer = ""

        return ''.join(result_parts)


class AgentStreamHandler:
    """Handles streaming from Strands agent to WebSocket.

    Processes events from agent.stream_async() and:
    - Filters think tags (optional)
    - Sends chunks to WebSocket in real-time
    - Tracks tool calls for metadata
    - Accumulates full response for postprocessing

    Example:
        handler = AgentStreamHandler(context)
        async for event in agent.stream_async(input):
            await handler.stream_event(event)
        await handler.finalize()

        # Get accumulated data
        full_response = handler.full_response
        tool_calls = handler.tool_calls
    """

    def __init__(
        self,
        context: "ExecutionContext",
        enable_think_filter: bool = True,
    ):
        """
        Initialize stream handler.

        Args:
            context: Execution context with WebSocket connection.
            enable_think_filter: Whether to filter <think> tags.
        """
        self._context = context
        self._builder: "IWebSocketMessageBuilder" = get_message_builder(context)
        self._filter = StreamFilter() if enable_think_filter else None
        self._full_response = ""
        self._tool_calls: List[Dict[str, Any]] = []
        self._chunk_count = 0
        self._error_occurred = False
        self._first_meaningful_sent = False  # Track if we've sent first meaningful chunk

    async def stream_event(self, event: dict) -> None:
        """
        Process streaming event from agent.stream_async().

        Handles:
        - contentBlockDelta: Text chunks to stream
        - contentBlockStart: Tool call starts

        Args:
            event: Event dict from Strands agent streaming.
        """
        self._chunk_count += 1

        try:
            if "contentBlockDelta" in event:
                delta = event["contentBlockDelta"]["delta"]
                if "text" in delta:
                    text = delta["text"]
                    self._full_response += text

                    # Stream to WebSocket if connected
                    if self._context.websocket:
                        filtered = self._filter.process(text) if self._filter else text
                        if filtered:
                            # Validate content before sending (prevents Discord error 50006)
                            # Only send if we have meaningful content
                            full_text = self._full_response.strip()
                            has_alphanumeric = bool(re.search(r'[a-zA-Z0-9]', full_text))

                            if not self._first_meaningful_sent:
                                # Wait for MIN_CONTENT_LENGTH with alphanumeric chars
                                if len(full_text) >= MIN_CONTENT_LENGTH and has_alphanumeric:
                                    self._first_meaningful_sent = True
                                    # Send the FULL accumulated content for first chunk
                                    content_to_send = full_text
                                else:
                                    # Not enough content yet - skip this chunk
                                    return
                            else:
                                # Send individual filtered token
                                # Discord bot handles accumulation and throttling
                                content_to_send = filtered

                            # Build message with interface-appropriate metadata
                            msg = self._builder.build_stream_chunk(
                                content_to_send, self._context
                            )
                            await self._context.websocket.send_json(msg)

            elif "contentBlockStart" in event:
                start = event["contentBlockStart"].get("start", {})
                if "toolUse" in start:
                    tool_info = {
                        "name": start["toolUse"]["name"],
                        "id": start["toolUse"].get("toolUseId"),
                    }
                    self._tool_calls.append(tool_info)

                    # Notify WebSocket of tool start
                    if self._context.websocket:
                        msg = self._builder.build_message(
                            {"type": "tool_start", "tool_name": tool_info["name"]},
                            self._context,
                        )
                        await self._context.websocket.send_json(msg)

        except Exception as e:
            logger.warning(f"Error processing stream event: {e}")
            self._error_occurred = True

    async def finalize(self) -> None:
        """
        Finalize streaming, flush remaining content.

        Call this after all events have been processed to:
        - Flush any buffered content from filter
        - Send stream_end message to WebSocket
        """
        try:
            # Flush any remaining filtered content
            if self._filter and self._context.websocket:
                remaining = self._filter.flush()
                if remaining:
                    msg = self._builder.build_stream_chunk(remaining, self._context)
                    await self._context.websocket.send_json(msg)

            # Send stream end notification
            if self._context.websocket:
                msg = self._builder.build_stream_end(self._context)
                await self._context.websocket.send_json(msg)

        except Exception as e:
            logger.warning(f"Error finalizing stream: {e}")

        logger.debug(
            f"Streaming finalized: {self._chunk_count} chunks, "
            f"{len(self._full_response)} chars, "
            f"{len(self._tool_calls)} tool calls"
        )

    @property
    def full_response(self) -> str:
        """Get the full accumulated response."""
        return self._full_response

    @property
    def tool_calls(self) -> List[Dict[str, Any]]:
        """Get list of tool calls made during streaming."""
        return self._tool_calls

    @property
    def had_error(self) -> bool:
        """Check if any errors occurred during streaming."""
        return self._error_occurred

    @property
    def is_empty(self) -> bool:
        """Check if response is empty (streaming may have failed)."""
        return not self._full_response or not self._full_response.strip()


async def stream_agent_response(
    agent,
    input_text: str,
    context: "ExecutionContext",
    enable_think_filter: bool = True,
) -> tuple[str, List[Dict[str, Any]], bool]:
    """
    Stream agent response with fallback to non-streaming.

    Attempts streaming first. If streaming fails or returns empty,
    falls back to non-streaming mode.

    Args:
        agent: Strands Agent instance.
        input_text: User input to process.
        context: Execution context with WebSocket.
        enable_think_filter: Whether to filter <think> tags.

    Returns:
        Tuple of (response_content, tool_calls, used_streaming).
    """
    handler = AgentStreamHandler(context, enable_think_filter)
    used_streaming = True

    try:
        # Attempt streaming
        async for event in agent.stream_async(input_text):
            # Check for cancellation
            await context.check_cancelled()
            await handler.stream_event(event)

        await handler.finalize()

        # Check if streaming succeeded
        if not handler.is_empty:
            return handler.full_response, handler.tool_calls, True

        # Streaming returned empty - fall back to non-streaming
        logger.warning("Streaming returned empty response, falling back to non-streaming")
        used_streaming = False

    except Exception as e:
        logger.warning(f"Streaming failed: {e}, falling back to non-streaming")
        used_streaming = False

        # Notify WebSocket of fallback
        if context.websocket:
            try:
                builder = get_message_builder(context)
                msg = builder.build_message(
                    {"type": "stream_fallback", "message": "Retrying without streaming..."},
                    context,
                )
                await context.websocket.send_json(msg)
            except Exception:
                pass

    # Fallback: non-streaming mode
    try:
        logger.info("Using non-streaming fallback")

        # Non-streaming call
        result = await agent.invoke_async(input_text)

        # Extract response from result
        if isinstance(result, dict):
            response = result.get("content", "") or result.get("text", "") or str(result)
        else:
            response = str(result)

        # Send as single message if WebSocket connected
        if context.websocket and response:
            builder = get_message_builder(context)
            msg = builder.build_message(
                {"type": "response", "content": response},
                context,
            )
            await context.websocket.send_json(msg)

        return response, [], False

    except Exception as fallback_error:
        logger.error(f"Non-streaming fallback also failed: {fallback_error}")
        raise


class StreamingConfig:
    """Configuration for streaming behavior."""

    def __init__(
        self,
        enable_streaming: bool = True,
        enable_think_filter: bool = True,
        fallback_on_empty: bool = True,
        max_fallback_retries: int = 1,
    ):
        """
        Initialize streaming configuration.

        Args:
            enable_streaming: Whether to attempt streaming at all.
            enable_think_filter: Whether to filter <think> tags.
            fallback_on_empty: Whether to fall back if streaming returns empty.
            max_fallback_retries: Max retries for non-streaming fallback.
        """
        self.enable_streaming = enable_streaming
        self.enable_think_filter = enable_think_filter
        self.fallback_on_empty = fallback_on_empty
        self.max_fallback_retries = max_fallback_retries


class StreamingManager:
    """Manages global streaming state with automatic fallback.

    Tracks streaming failures and automatically disables streaming
    if it fails repeatedly. This provides a "circuit breaker" pattern.

    Example:
        manager = StreamingManager(failure_threshold=2)

        if manager.should_stream():
            # attempt streaming...
            if streaming_failed:
                manager.record_failure()
            else:
                manager.record_success()
    """

    def __init__(
        self,
        failure_threshold: int = 2,
        recovery_attempts: int = 10,
    ):
        """
        Initialize streaming manager.

        Args:
            failure_threshold: Number of consecutive failures before disabling streaming.
            recovery_attempts: After this many non-streaming successes, try streaming again.
        """
        self._failure_threshold = failure_threshold
        self._recovery_attempts = recovery_attempts
        self._consecutive_failures = 0
        self._streaming_disabled = False
        self._non_streaming_successes = 0

    def should_stream(self) -> bool:
        """Check if streaming should be attempted.

        Returns:
            True if streaming is enabled and not disabled due to failures.
        """
        if self._streaming_disabled:
            # Check if we should try streaming again
            if self._non_streaming_successes >= self._recovery_attempts:
                logger.info("Re-enabling streaming after successful recovery period")
                self._streaming_disabled = False
                self._consecutive_failures = 0
                self._non_streaming_successes = 0
                return True
            return False
        return True

    def record_failure(self) -> None:
        """Record a streaming failure.

        After threshold failures, streaming is disabled.
        """
        self._consecutive_failures += 1
        logger.warning(
            f"Streaming failure {self._consecutive_failures}/{self._failure_threshold}"
        )

        if self._consecutive_failures >= self._failure_threshold:
            logger.warning(
                f"Streaming disabled after {self._consecutive_failures} consecutive failures"
            )
            self._streaming_disabled = True
            self._non_streaming_successes = 0

    def record_success(self, used_streaming: bool) -> None:
        """Record a successful response.

        Args:
            used_streaming: Whether streaming was used for this response.
        """
        if used_streaming:
            self._consecutive_failures = 0
        else:
            # Track non-streaming successes for recovery
            if self._streaming_disabled:
                self._non_streaming_successes += 1
                logger.debug(
                    f"Non-streaming success {self._non_streaming_successes}/{self._recovery_attempts}"
                )

    @property
    def is_streaming_disabled(self) -> bool:
        """Check if streaming is currently disabled."""
        return self._streaming_disabled

    def force_disable(self) -> None:
        """Manually disable streaming."""
        self._streaming_disabled = True
        logger.info("Streaming manually disabled")

    def force_enable(self) -> None:
        """Manually enable streaming."""
        self._streaming_disabled = False
        self._consecutive_failures = 0
        logger.info("Streaming manually enabled")


# Global streaming manager instance
_streaming_manager: Optional[StreamingManager] = None


def get_streaming_manager() -> StreamingManager:
    """Get the global streaming manager instance.

    Returns:
        The global StreamingManager.
    """
    global _streaming_manager
    if _streaming_manager is None:
        _streaming_manager = StreamingManager()
    return _streaming_manager
