"""Unit tests for Discord bot components."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.utils import split_message


def test_split_message_no_split():
    """Test that short messages are not split."""
    content = "Hello, world!"
    chunks = split_message(content)

    assert len(chunks) == 1
    assert chunks[0] == content


def test_split_message_splits_correctly():
    """Test message splitting for long content."""
    content = "word " * 500  # Creates a long message
    chunks = split_message(content, max_length=2000)

    assert len(chunks) > 1

    # Verify each chunk is within limit
    for chunk in chunks:
        assert len(chunk) <= 2000

    # Verify part indicators
    for i, chunk in enumerate(chunks):
        assert chunk.startswith(f"[Part {i+1}/{len(chunks)}]")


def test_split_message_preserves_content():
    """Test that splitting preserves all content."""
    content = "word " * 500
    chunks = split_message(content, max_length=2000)

    # Reconstruct content (remove part indicators)
    reconstructed = ""
    for chunk in chunks:
        if chunk.startswith("[Part"):
            # Remove part indicator
            chunk = chunk.split("\n", 1)[1] if "\n" in chunk else chunk
        reconstructed += chunk + " "

    reconstructed = reconstructed.strip()

    # Should contain all words (approximately)
    assert len(reconstructed.split()) >= len(content.split()) - len(chunks)


@pytest.mark.asyncio
async def test_websocket_manager_connect():
    """Test WebSocket connection."""
    from bot.websocket_manager import WebSocketManager

    with patch('bot.websocket_manager.websockets.connect', new_callable=AsyncMock) as mock_connect:
        mock_ws = AsyncMock()
        mock_ws.recv.return_value = '{"type": "connected", "bot_id": "bot_123"}'
        mock_connect.return_value = mock_ws

        manager = WebSocketManager("ws://test")
        await manager.connect("bot_123")

        assert manager.connected is True
        mock_ws.send.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_manager_send_message():
    """Test sending message through WebSocket."""
    from bot.websocket_manager import WebSocketManager

    manager = WebSocketManager("ws://test")
    manager.connected = True
    manager.websocket = AsyncMock()

    data = {'type': 'message', 'content': 'Hello'}
    await manager.send_message(data)

    manager.websocket.send.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_manager_cancel_request():
    """Test sending cancellation request."""
    from bot.websocket_manager import WebSocketManager

    manager = WebSocketManager("ws://test")
    manager.connected = True
    manager.websocket = AsyncMock()

    await manager.cancel_request("req_123")

    manager.websocket.send.assert_called_once()
    call_args = manager.websocket.send.call_args[0][0]
    assert '"type": "cancel"' in call_args
    assert '"request_id": "req_123"' in call_args


@pytest.mark.asyncio
async def test_message_handler_handle_result():
    """Test handling result message from FastAPI."""
    from bot.message_handler import MessageHandler

    mock_bot = MagicMock()
    mock_channel = AsyncMock()
    mock_bot.get_channel.return_value = mock_channel

    mock_ws = MagicMock()

    handler = MessageHandler(mock_bot, mock_ws)

    data = {
        'type': 'result',
        'channel_id': '123',
        'response': 'Hello from bot!'
    }

    await handler.handle_response(data)

    mock_channel.send.assert_called_once_with('Hello from bot!')


@pytest.mark.asyncio
async def test_message_handler_handle_failed():
    """Test handling failed message from FastAPI."""
    from bot.message_handler import MessageHandler

    mock_bot = MagicMock()
    mock_channel = AsyncMock()
    mock_bot.get_channel.return_value = mock_channel

    mock_ws = MagicMock()

    handler = MessageHandler(mock_bot, mock_ws)

    data = {
        'type': 'failed',
        'channel_id': '123',
        'user_id': '456',
        'error': 'Test error',
        'attempts': 3
    }

    await handler.handle_response(data)

    mock_channel.send.assert_called_once()
    call_args = mock_channel.send.call_args[0][0]
    assert 'failed after 3 attempts' in call_args
    assert 'Test error' in call_args
