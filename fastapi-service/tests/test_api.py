"""Unit tests for API endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app


@pytest.fixture
def mock_dependencies():
    """Mock all dependencies using FastAPI's dependency_overrides."""
    from app.dependencies import get_queue, get_token_tracker, get_storage

    # Create mocks
    mock_queue = MagicMock()
    # Non-async methods
    mock_queue.is_full.return_value = False
    mock_queue.size.return_value = 1
    # Async methods
    mock_queue.enqueue = AsyncMock(return_value="req_123")
    mock_queue.get_position = AsyncMock(return_value=1)
    mock_queue.cancel = AsyncMock(return_value=True)
    mock_queue.get_status = AsyncMock(return_value={
        'status': 'processing',
        'request_id': 'req_123'
    })
    mock_queue.dequeue = AsyncMock(return_value=None)
    mock_queue.mark_complete = AsyncMock()
    mock_queue.mark_failed = AsyncMock(return_value=False)

    mock_tracker = AsyncMock()
    mock_tracker.count_tokens.return_value = 10

    mock_storage = AsyncMock()
    mock_storage.get_user.return_value = {
        'user_id': 'user_123',
        'tokens_remaining': 10000
    }

    # Override dependencies
    app.dependency_overrides[get_queue] = lambda: mock_queue
    app.dependency_overrides[get_token_tracker] = lambda: mock_tracker
    app.dependency_overrides[get_storage] = lambda: mock_storage

    yield {
        'queue': mock_queue,
        'tracker': mock_tracker,
        'storage': mock_storage
    }

    # Cleanup
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test root endpoint returns service info."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data['message'] == "Discord-Ollama Agent API"
    assert 'version' in data
    assert 'health' in data


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint."""
    with patch('app.main.check_dynamodb', return_value=True), \
         patch('app.main.check_ollama', return_value=True), \
         patch('app.main.check_ollama_model_loaded', return_value=True):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert data['services']['dynamodb'] is True
        assert data['services']['ollama'] is True


@pytest.mark.asyncio
async def test_submit_message_success(mock_dependencies):
    """Test submitting a message via REST API."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/discord/message",
            json={
                'user_id': 'user_123',
                'thread_id': 'thread_456',
                'message': 'Hello, bot!',
                'message_id': 'msg_789',
                'channel_id': 'channel_012'
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert data['request_id'] == 'req_123'
    assert data['status'] == 'queued'
    assert 'queue_position' in data


@pytest.mark.asyncio
async def test_submit_message_queue_full(mock_dependencies):
    """Test submitting message when queue is full."""
    mock_dependencies['queue'].is_full.return_value = True

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/discord/message",
            json={
                'user_id': 'user_123',
                'thread_id': 'thread_456',
                'message': 'Hello, bot!',
                'message_id': 'msg_789',
                'channel_id': 'channel_012'
            }
        )

    assert response.status_code == 429
    assert "Queue is full" in response.json()['detail']


@pytest.mark.asyncio
async def test_get_request_status(mock_dependencies):
    """Test getting request status."""
    mock_dependencies['queue'].get_status.return_value = {
        'status': 'processing',
        'request_id': 'req_123'
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/discord/status/req_123")

    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'processing'
    assert data['request_id'] == 'req_123'


@pytest.mark.asyncio
async def test_cancel_request_success(mock_dependencies):
    """Test cancelling a request."""
    mock_dependencies['queue'].cancel.return_value = True

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/api/discord/cancel/req_123")

    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'cancelled'


@pytest.mark.asyncio
async def test_cancel_request_already_processing(mock_dependencies):
    """Test cancelling a request that's already processing."""
    mock_dependencies['queue'].cancel.return_value = False

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/api/discord/cancel/req_123")

    assert response.status_code == 400
    assert "cannot be cancelled" in response.json()['detail']
