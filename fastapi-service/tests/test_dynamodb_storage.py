"""Unit tests for DynamoDB storage implementation."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.implementations.dynamodb_storage import DynamoDBStorage


@pytest.fixture
def storage():
    """Create DynamoDBStorage instance with mocked session."""
    with patch('app.implementations.dynamodb_storage.aioboto3.Session'):
        storage = DynamoDBStorage()
        return storage


@pytest.mark.asyncio
async def test_create_user(storage):
    """Test user creation with default settings."""
    mock_table = AsyncMock()

    with patch.object(storage.session, 'resource') as mock_resource:
        mock_resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

        await storage.create_user(
            user_id="test_user_123",
            discord_username="TestUser",
            user_tier="free"
        )

        # Verify put_item was called
        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args
        item = call_args.kwargs['Item']

        assert item['user_id'] == "test_user_123"
        assert item['discord_username'] == "TestUser"
        assert item['user_tier'] == "free"
        assert item['weekly_token_budget'] == 100000  # Free tier budget


@pytest.mark.asyncio
async def test_get_user(storage):
    """Test retrieving user data."""
    mock_table = AsyncMock()
    mock_table.get_item.return_value = {
        'Item': {
            'user_id': 'test_user_123',
            'discord_username': 'TestUser',
            'tokens_remaining': 50000
        }
    }

    with patch.object(storage.session, 'resource') as mock_resource:
        mock_resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

        user = await storage.get_user("test_user_123")

        assert user is not None
        assert user['user_id'] == 'test_user_123'
        assert user['tokens_remaining'] == 50000


@pytest.mark.asyncio
async def test_add_message(storage):
    """Test adding a message to conversation."""
    mock_table = AsyncMock()

    with patch.object(storage.session, 'resource') as mock_resource:
        mock_resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

        await storage.add_message(
            thread_id="thread_123",
            message_id="msg_456",
            role="user",
            content="Hello, world!",
            token_count=5,
            user_id="user_789",
            model_used="gpt-oss:20b",
            is_summary=False
        )

        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args
        item = call_args.kwargs['Item']

        assert item['thread_id'] == "thread_123"
        assert item['role'] == "user"
        assert item['content'] == "Hello, world!"
        assert item['token_count'] == 5


@pytest.mark.asyncio
async def test_update_user_tokens(storage):
    """Test updating user token usage."""
    mock_table = AsyncMock()

    # Mock get_user to return existing user
    with patch.object(storage, 'get_user', return_value={
        'user_id': 'test_user',
        'tokens_used_this_week': 1000,
        'weekly_token_budget': 100000,
        'bonus_tokens': 0
    }):
        with patch.object(storage.session, 'resource') as mock_resource:
            mock_resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

            await storage.update_user_tokens("test_user", 500)

            mock_table.update_item.assert_called_once()
            call_args = mock_table.update_item.call_args

            # Check that tokens_used_this_week was updated
            assert ':used' in call_args.kwargs['ExpressionAttributeValues']
            assert call_args.kwargs['ExpressionAttributeValues'][':used'] == 1500


@pytest.mark.asyncio
async def test_grant_bonus_tokens(storage):
    """Test granting bonus tokens to user."""
    mock_table = AsyncMock()

    with patch.object(storage.session, 'resource') as mock_resource:
        mock_resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

        await storage.grant_bonus_tokens("test_user", 10000)

        mock_table.update_item.assert_called_once()
        call_args = mock_table.update_item.call_args

        assert ':amount' in call_args.kwargs['ExpressionAttributeValues']
        assert call_args.kwargs['ExpressionAttributeValues'][':amount'] == 10000


@pytest.mark.asyncio
async def test_get_thread_messages(storage):
    """Test retrieving thread messages."""
    mock_table = AsyncMock()
    mock_table.query.return_value = {
        'Items': [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi there!'}
        ]
    }

    with patch.object(storage.session, 'resource') as mock_resource:
        mock_resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

        messages = await storage.get_thread_messages("thread_123", limit=10)

        assert len(messages) == 2
        assert messages[0]['role'] == 'user'
        assert messages[1]['role'] == 'assistant'
