"""Response formatters for different client types.

Strategy Pattern implementation for formatting queue worker responses.
Separates client-specific formatting logic from business logic (SOLID compliance).
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class ResponseFormatter(ABC):
    """Abstract base class for response formatters.

    Each client type (Discord, Web UI, CLI, etc.) implements its own formatter.
    This follows the Strategy Pattern and Open/Closed Principle.
    """

    @abstractmethod
    async def format_queued(self, request_id: str, queue_position: int) -> Dict[str, Any]:
        """Format a queued response."""
        pass

    @abstractmethod
    async def format_processing(self, request_id: str) -> Dict[str, Any]:
        """Format a processing notification."""
        pass

    @abstractmethod
    async def format_stream_update(
        self,
        request_id: str,
        content: str,
        channel_id: str,
        message_id: str = None,
        message_channel_id: str = None
    ) -> Dict[str, Any]:
        """Format a streaming content update."""
        pass

    @abstractmethod
    async def format_completion(
        self,
        request_id: str,
        result: Dict[str, Any],
        channel_id: str,
        message_id: str = None,
        message_channel_id: str = None
    ) -> Dict[str, Any]:
        """Format a completion response."""
        pass

    @abstractmethod
    async def format_error(
        self,
        request_id: str,
        error: str,
        channel_id: str = None,
        message_id: str = None,
        message_channel_id: str = None
    ) -> Dict[str, Any]:
        """Format an error response."""
        pass

    @abstractmethod
    async def format_failed(
        self,
        request_id: str,
        error: str,
        attempts: int,
        channel_id: str = None,
        message_id: str = None,
        message_channel_id: str = None,
        user_id: str = None
    ) -> Dict[str, Any]:
        """Format a failed response after max retries."""
        pass


class DiscordFormatter(ResponseFormatter):
    """Response formatter for Discord bot clients.

    Uses stream_chunk format with snake_case field names.
    Includes Discord-specific fields like message_channel_id for reactions.
    """

    async def format_queued(self, request_id: str, queue_position: int) -> Dict[str, Any]:
        return {
            'type': 'queued',
            'request_id': request_id,
            'queue_position': queue_position
        }

    async def format_processing(self, request_id: str) -> Dict[str, Any]:
        return {
            'type': 'processing',
            'request_id': request_id
        }

    async def format_stream_update(
        self,
        request_id: str,
        content: str,
        channel_id: str,
        message_id: str = None,
        message_channel_id: str = None
    ) -> Dict[str, Any]:
        return {
            'type': 'stream_chunk',
            'request_id': request_id,
            'content': content,
            'is_complete': False,
            'channel_id': channel_id,
            'message_id': message_id,
            'message_channel_id': message_channel_id
        }

    async def format_completion(
        self,
        request_id: str,
        result: Dict[str, Any],
        channel_id: str,
        message_id: str = None,
        message_channel_id: str = None
    ) -> Dict[str, Any]:
        return {
            'type': 'stream_chunk',
            'request_id': request_id,
            'content': result['response'],
            'is_complete': True,
            'channel_id': channel_id,
            'message_id': message_id,
            'message_channel_id': message_channel_id,
            'artifacts': result.get('artifacts', [])
        }

    async def format_error(
        self,
        request_id: str,
        error: str,
        channel_id: str = None,
        message_id: str = None,
        message_channel_id: str = None
    ) -> Dict[str, Any]:
        return {
            'type': 'error',
            'request_id': request_id,
            'error': error,
            'channel_id': channel_id,
            'message_id': message_id,
            'message_channel_id': message_channel_id
        }

    async def format_failed(
        self,
        request_id: str,
        error: str,
        attempts: int,
        channel_id: str = None,
        message_id: str = None,
        message_channel_id: str = None,
        user_id: str = None
    ) -> Dict[str, Any]:
        return {
            'type': 'failed',
            'request_id': request_id,
            'error': error,
            'attempts': attempts,
            'channel_id': channel_id,
            'message_id': message_id,
            'message_channel_id': message_channel_id,
            'user_id': user_id
        }


class WebUIFormatter(ResponseFormatter):
    """Response formatter for Web UI clients.

    Uses TypeScript-friendly camelCase field names.
    Separates streaming updates from completion (different message types).
    """

    async def format_queued(self, request_id: str, queue_position: int) -> Dict[str, Any]:
        return {
            'type': 'queued',
            'requestId': request_id,
            'queuePosition': queue_position
        }

    async def format_processing(self, request_id: str) -> Dict[str, Any]:
        return {
            'type': 'processing',
            'requestId': request_id
        }

    async def format_stream_update(
        self,
        request_id: str,
        content: str,
        channel_id: str,
        message_id: str = None,
        message_channel_id: str = None
    ) -> Dict[str, Any]:
        """Web UI uses 'token' type for streaming updates."""
        return {
            'type': 'token',
            'content': content
        }

    async def format_completion(
        self,
        request_id: str,
        result: Dict[str, Any],
        channel_id: str,
        message_id: str = None,
        message_channel_id: str = None
    ) -> Dict[str, Any]:
        """Web UI uses 'done' type for completion."""
        return {
            'type': 'done',
            'requestId': request_id,
            'messageId': result.get('message_id'),
            'tokensUsed': result.get('tokens_used', 0),
            'outputTokens': result.get('output_tokens', 0),  # For display (visible tokens only)
            'totalTokensGenerated': result.get('total_tokens_generated', 0),  # For TPS (includes thinking)
            'generationTime': result.get('generation_time', 0),  # seconds
            'model': result.get('model'),  # Model used for this response
            'artifacts': result.get('artifacts', [])
        }

    async def format_error(
        self,
        request_id: str,
        error: str,
        channel_id: str = None,
        message_id: str = None,
        message_channel_id: str = None
    ) -> Dict[str, Any]:
        return {
            'type': 'error',
            'error': error
        }

    async def format_failed(
        self,
        request_id: str,
        error: str,
        attempts: int,
        channel_id: str = None,
        message_id: str = None,
        message_channel_id: str = None,
        user_id: str = None
    ) -> Dict[str, Any]:
        """Web UI doesn't need all Discord fields, simplified response."""
        return {
            'type': 'failed',
            'error': error,
            'attempts': attempts
        }


# Factory function for getting the appropriate formatter
def get_formatter(request: Dict[str, Any]) -> ResponseFormatter:
    """Factory function to get the appropriate formatter for a request.

    Args:
        request: Request dictionary containing client identification

    Returns:
        ResponseFormatter instance for the client type
    """
    if 'bot_id' in request or 'channel_id' in request:
        return DiscordFormatter()
    elif 'webui_client_id' in request:
        return WebUIFormatter()
    else:
        # Default to Discord format for backwards compatibility
        return DiscordFormatter()
