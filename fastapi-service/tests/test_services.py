"""Unit tests for business logic services."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.context_manager import ContextManager
from app.services.token_tracker import TokenTracker
from app.services.summarization_service import SummarizationService


@pytest.mark.asyncio
async def test_context_manager_get_thread_context():
    """Test retrieving thread context."""
    mock_storage = AsyncMock()
    mock_storage.get_thread_messages.return_value = [
        {
            'role': 'user',
            'content': 'Hello',
            'token_count': 5,
            'message_timestamp': '2024-01-01T00:00:00'
        },
        {
            'role': 'assistant',
            'content': 'Hi there!',
            'token_count': 10,
            'message_timestamp': '2024-01-01T00:00:01'
        }
    ]

    context_manager = ContextManager(storage=mock_storage)
    context = await context_manager.get_thread_context("thread_123", "user_456")

    assert len(context) == 2
    assert context[0]['role'] == 'user'
    assert context[1]['role'] == 'assistant'
    mock_storage.get_thread_messages.assert_called_once_with("thread_123")


@pytest.mark.asyncio
async def test_token_tracker_count_tokens():
    """Test token counting."""
    mock_storage = AsyncMock()
    mock_llm = AsyncMock()
    mock_llm.count_tokens.return_value = 42

    tracker = TokenTracker(storage=mock_storage, llm=mock_llm)
    count = await tracker.count_tokens("Hello, world!")

    assert count == 42
    mock_llm.count_tokens.assert_called_once_with("Hello, world!")


@pytest.mark.asyncio
async def test_token_tracker_has_budget():
    """Test checking if user has token budget."""
    mock_storage = AsyncMock()
    mock_llm = AsyncMock()

    tracker = TokenTracker(storage=mock_storage, llm=mock_llm)

    # User with sufficient budget
    user = {'tokens_remaining': 1000}
    assert await tracker.has_budget(user, 500) is True

    # User with insufficient budget
    user = {'tokens_remaining': 100}
    assert await tracker.has_budget(user, 500) is False


@pytest.mark.asyncio
async def test_token_tracker_update_usage():
    """Test updating token usage."""
    mock_storage = AsyncMock()
    mock_llm = AsyncMock()

    tracker = TokenTracker(storage=mock_storage, llm=mock_llm)
    await tracker.update_usage("user_123", 500)

    mock_storage.update_user_tokens.assert_called_once_with("user_123", 500)


@pytest.mark.asyncio
async def test_summarization_service_summarize_and_prune():
    """Test conversation summarization."""
    mock_storage = AsyncMock()
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = {
        'content': 'Summary: User asked about weather, assistant provided forecast.',
        'model': 'gpt-oss:20b'
    }

    service = SummarizationService(storage=mock_storage, llm=mock_llm)

    # Create 10 messages
    messages = [
        {
            'role': 'user' if i % 2 == 0 else 'assistant',
            'content': f'Message {i}',
            'token_count': 10,
            'message_timestamp': f'2024-01-01T00:00:{i:02d}'
        }
        for i in range(10)
    ]

    result = await service.summarize_and_prune(
        thread_id="thread_123",
        messages=messages,
        user_id="user_456"
    )

    # Should keep last 5 messages + add summary
    assert len(result) == 6  # 1 summary + 5 kept messages
    assert result[0]['role'] == 'system'
    assert 'SUMMARY' in result[0]['content']

    # Verify old messages were deleted
    mock_storage.delete_messages.assert_called_once()
    deleted_timestamps = mock_storage.delete_messages.call_args[0][1]
    assert len(deleted_timestamps) == 5  # First 5 messages

    # Verify summary was saved
    mock_storage.add_message.assert_called_once()
    call_args = mock_storage.add_message.call_args
    assert call_args.kwargs['role'] == 'system'
    assert call_args.kwargs['is_summary'] is True


@pytest.mark.asyncio
async def test_summarization_no_prune_if_few_messages():
    """Test that summarization doesn't happen with few messages."""
    mock_storage = AsyncMock()
    mock_llm = AsyncMock()

    service = SummarizationService(storage=mock_storage, llm=mock_llm)

    # Only 3 messages - not enough to summarize
    messages = [
        {'role': 'user', 'content': 'Hi', 'token_count': 5, 'message_timestamp': '1'},
        {'role': 'assistant', 'content': 'Hello', 'token_count': 5, 'message_timestamp': '2'},
        {'role': 'user', 'content': 'How are you?', 'token_count': 10, 'message_timestamp': '3'}
    ]

    result = await service.summarize_and_prune(
        thread_id="thread_123",
        messages=messages,
        user_id="user_456"
    )

    # Should return original messages unchanged
    assert result == messages
    mock_llm.generate.assert_not_called()
    mock_storage.delete_messages.assert_not_called()
