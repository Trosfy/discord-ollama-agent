"""Unit tests for Discord bot components."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.utils import split_message, track_code_block_state, find_stream_split_point


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


# Tests for track_code_block_state
def test_track_code_block_state_no_code():
    """Test content without code blocks."""
    is_open, lang = track_code_block_state("Hello world, no code here!")
    assert is_open is False
    assert lang is None


def test_track_code_block_state_open_block():
    """Test content with an open code block."""
    is_open, lang = track_code_block_state("```python\ndef foo():\n    pass")
    assert is_open is True
    assert lang == 'python'


def test_track_code_block_state_closed_block():
    """Test content with a closed code block."""
    is_open, lang = track_code_block_state("```python\ndef foo():\n    pass\n```")
    assert is_open is False
    assert lang is None


def test_track_code_block_state_no_language():
    """Test code block without language specifier."""
    is_open, lang = track_code_block_state("```\nsome code here")
    assert is_open is True
    assert lang == ''


def test_track_code_block_state_multiple_blocks():
    """Test multiple code blocks - last one open."""
    content = "```python\ncode1\n```\n\nText between\n\n```javascript\ncode2"
    is_open, lang = track_code_block_state(content)
    assert is_open is True
    assert lang == 'javascript'


def test_track_code_block_state_multiple_blocks_closed():
    """Test multiple code blocks - all closed."""
    content = "```python\ncode1\n```\n\n```javascript\ncode2\n```"
    is_open, lang = track_code_block_state(content)
    assert is_open is False
    assert lang is None


# Tests for find_stream_split_point
def test_find_stream_split_point_too_short():
    """Test that short content returns no split."""
    content = "A" * 1800
    split_at, suffix, prefix = find_stream_split_point(content, threshold=1800)
    assert split_at == 0
    assert suffix is None
    assert prefix is None


def test_find_stream_split_point_paragraph():
    """Test splitting at paragraph boundary."""
    content = "A" * 1700 + "\n\n" + "B" * 200
    split_at, suffix, prefix = find_stream_split_point(content, threshold=1800)
    assert split_at == 1702  # After the \n\n
    assert suffix is None
    assert prefix is None


def test_find_stream_split_point_line():
    """Test splitting at line boundary when no paragraph."""
    content = "A" * 1700 + "\n" + "B" * 200
    split_at, suffix, prefix = find_stream_split_point(content, threshold=1800)
    assert split_at == 1701  # After the \n
    assert suffix is None
    assert prefix is None


def test_find_stream_split_point_sentence():
    """Test splitting at sentence boundary."""
    content = "A" * 1700 + ". " + "B" * 200
    split_at, suffix, prefix = find_stream_split_point(content, threshold=1800)
    assert split_at == 1702  # After the ". "
    assert suffix is None
    assert prefix is None


def test_find_stream_split_point_word():
    """Test splitting at word boundary."""
    content = "A" * 1700 + " " + "B" * 200
    split_at, suffix, prefix = find_stream_split_point(content, threshold=1800)
    assert split_at == 1701  # After the space
    assert suffix is None
    assert prefix is None


def test_find_stream_split_point_with_code_block():
    """Test splitting inside a code block adds close/open markers."""
    content = "```python\n" + "x = 1\n" * 350  # ~2100 chars (must be > threshold + min_remaining)
    split_at, suffix, prefix = find_stream_split_point(content, threshold=1800, min_remaining=100)

    # Should have split point
    assert split_at > 0

    # Should have close/open markers for code block
    assert suffix == '\n```'
    assert prefix == '```python\n'


def test_find_stream_split_point_hard_split():
    """Test hard split when no natural boundaries exist."""
    content = "A" * 2000  # No spaces, newlines, or periods
    split_at, suffix, prefix = find_stream_split_point(content, threshold=1800)
    assert split_at == 1800  # Hard split at threshold
    assert suffix is None
    assert prefix is None
