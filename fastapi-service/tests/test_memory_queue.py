"""Unit tests for in-memory queue implementation."""
import pytest
import asyncio
from datetime import datetime

from app.implementations.memory_queue import MemoryQueue


@pytest.fixture
async def queue():
    """Create and start a MemoryQueue instance."""
    q = MemoryQueue()
    await q.start()
    yield q
    await q.stop()


@pytest.mark.asyncio
async def test_enqueue_dequeue(queue):
    """Test basic enqueue and dequeue operations."""
    request = {
        'user_id': 'user_123',
        'message': 'Hello',
        'estimated_tokens': 10
    }

    request_id = await queue.enqueue(request)

    assert request_id is not None
    assert queue.size() == 1

    dequeued = await queue.dequeue()

    assert dequeued is not None
    assert dequeued['request_id'] == request_id
    assert dequeued['user_id'] == 'user_123'
    assert dequeued['state'] == 'processing'


@pytest.mark.asyncio
async def test_queue_fifo_order(queue):
    """Test that queue maintains FIFO order."""
    request_ids = []

    for i in range(3):
        request = {
            'user_id': f'user_{i}',
            'message': f'Message {i}',
            'estimated_tokens': 10
        }
        request_id = await queue.enqueue(request)
        request_ids.append(request_id)

    # Dequeue and verify order
    for i in range(3):
        dequeued = await queue.dequeue()
        assert dequeued['request_id'] == request_ids[i]
        assert dequeued['user_id'] == f'user_{i}'


@pytest.mark.asyncio
async def test_queue_full(queue):
    """Test queue full condition."""
    # Fill the queue
    for i in range(50):  # MAX_QUEUE_SIZE is 50
        request = {
            'user_id': f'user_{i}',
            'message': 'Test',
            'estimated_tokens': 10
        }
        await queue.enqueue(request)

    assert queue.is_full()

    # Try to add one more
    with pytest.raises(Exception, match="Queue is full"):
        await queue.enqueue({'user_id': 'overflow', 'message': 'Test', 'estimated_tokens': 10})


@pytest.mark.asyncio
async def test_mark_complete(queue):
    """Test marking request as complete."""
    request = {'user_id': 'user_123', 'message': 'Hello', 'estimated_tokens': 10}
    request_id = await queue.enqueue(request)

    dequeued = await queue.dequeue()

    result = {'response': 'Hi there!', 'tokens_used': 20}
    await queue.mark_complete(request_id, result)

    status = await queue.get_status(request_id)

    assert status['status'] == 'completed'
    assert status['result'] == result
    assert request_id not in queue.in_flight


@pytest.mark.asyncio
async def test_mark_failed_with_retry(queue):
    """Test marking request as failed and retry logic."""
    request = {'user_id': 'user_123', 'message': 'Hello', 'estimated_tokens': 10}
    request_id = await queue.enqueue(request)

    dequeued = await queue.dequeue()

    # First failure should retry
    requeued = await queue.mark_failed(request_id, "Temporary error")

    assert requeued is True
    assert request_id not in queue.in_flight

    # Wait for retry delay
    await asyncio.sleep(0.1)

    # Should be able to dequeue again
    dequeued_again = await queue.dequeue()
    assert dequeued_again['request_id'] == request_id
    assert dequeued_again['attempt'] == 1


@pytest.mark.asyncio
async def test_mark_failed_max_retries(queue):
    """Test that max retries are respected."""
    request = {'user_id': 'user_123', 'message': 'Hello', 'estimated_tokens': 10}
    request_id = await queue.enqueue(request)

    # Fail 3 times (MAX_RETRIES)
    for i in range(3):
        dequeued = await queue.dequeue()
        requeued = await queue.mark_failed(request_id, f"Error {i+1}")

        if i < 2:
            assert requeued is True
            await asyncio.sleep(0.1)  # Wait for retry delay
        else:
            assert requeued is False

    # Should be in failed dict
    status = await queue.get_status(request_id)
    assert status['status'] == 'failed'


@pytest.mark.asyncio
async def test_cancel_queued_request(queue):
    """Test cancelling a queued request."""
    request = {'user_id': 'user_123', 'message': 'Hello', 'estimated_tokens': 10}
    request_id = await queue.enqueue(request)

    cancelled = await queue.cancel(request_id)

    assert cancelled is True

    status = await queue.get_status(request_id)
    assert status['status'] == 'failed'
    assert 'Cancelled by user' in status['error']['error']


@pytest.mark.asyncio
async def test_cannot_cancel_processing(queue):
    """Test that processing requests cannot be cancelled."""
    request = {'user_id': 'user_123', 'message': 'Hello', 'estimated_tokens': 10}
    request_id = await queue.enqueue(request)

    await queue.dequeue()  # Start processing

    cancelled = await queue.cancel(request_id)

    assert cancelled is False


@pytest.mark.asyncio
async def test_get_position(queue):
    """Test getting queue position."""
    # Add multiple requests
    request_ids = []
    for i in range(3):
        request = {'user_id': f'user_{i}', 'message': 'Test', 'estimated_tokens': 10}
        req_id = await queue.enqueue(request)
        request_ids.append(req_id)

    # Position should reflect queue size
    position = await queue.get_position(request_ids[0])
    assert position > 0  # Approximate, as we can't peek into asyncio.Queue
