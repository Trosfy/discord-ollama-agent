"""Unit tests for QueueManager and WorkerPool."""
import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from app.core.config import QueueConfig
from app.core.queue import RequestQueue
from app.core.interfaces.queue import QueuedRequest, UserTier
from app.services.queue_manager import QueueWorker, WorkerPool, QueueManager


# =============================================================================
# Test Fixtures
# =============================================================================

def create_mock_routing_result(name: str = "test_skill", type: str = "skill"):
    """Create a mock routing result."""
    result = MagicMock()
    result.name = name
    result.type = type
    return result


def create_mock_context():
    """Create a mock execution context."""
    context = MagicMock()
    context.cancellation_token = MagicMock()
    context.cancellation_token.is_set.return_value = False
    return context


def create_queued_request(
    request_id: str = "test-request-1",
    user_tier: UserTier = UserTier.NORMAL,
    routing_type: str = "skill",
) -> QueuedRequest:
    """Create a QueuedRequest for testing."""
    return QueuedRequest(
        request_id=request_id,
        user_id="user-1",
        session_id="session-1",
        user_tier=user_tier,
        routing_result=create_mock_routing_result(type=routing_type),
        user_input="test input",
        context=create_mock_context(),
        queued_at=datetime.now(timezone.utc),
    )


def create_mock_executor(result=None, error=None, delay=0):
    """Create a mock executor."""
    executor = MagicMock()

    async def execute_fn(*args, **kwargs):
        if delay:
            await asyncio.sleep(delay)
        if error:
            raise error
        return result or MagicMock(content="test result")

    executor.execute = AsyncMock(side_effect=execute_fn)
    return executor


def create_queue_config(**overrides):
    """Create QueueConfig with optional overrides."""
    defaults = {
        "worker_count": 2,
        "default_timeout_seconds": 60,
        "skill_timeout_seconds": 30,
        "agent_timeout_seconds": 120,
        "timeout_buffer_seconds": 0,  # No buffer for tests
        "visibility_timeout_seconds": 60,
        "result_ttl_seconds": 60,
        "alert_queue_depth": 10,
    }
    defaults.update(overrides)
    return QueueConfig(**defaults)


# =============================================================================
# QueueWorker Tests
# =============================================================================

class TestQueueWorker:
    """Tests for individual queue worker."""

    @pytest.mark.asyncio
    async def test_worker_processes_request(self):
        """Worker processes request and marks complete."""
        queue = RequestQueue()
        executor = create_mock_executor()
        config = create_queue_config()

        worker = QueueWorker(
            worker_id=0,
            queue=queue,
            executor=executor,
            config=config,
        )

        # Submit request
        request = create_queued_request(request_id="1")
        await queue.submit(request)

        # Run worker briefly
        worker_task = asyncio.create_task(worker.run())

        # Wait for processing
        result = await asyncio.wait_for(
            queue.wait_result("1", timeout=5.0),
            timeout=5.0,
        )

        # Stop worker
        await worker.stop()
        await asyncio.sleep(0.1)
        await queue.shutdown()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Verify executor was called
        executor.execute.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_worker_handles_execution_error(self):
        """Worker marks request failed on execution error."""
        queue = RequestQueue()
        executor = create_mock_executor(error=RuntimeError("Test error"))
        config = create_queue_config()

        worker = QueueWorker(
            worker_id=0,
            queue=queue,
            executor=executor,
            config=config,
        )

        # Submit request
        request = create_queued_request(request_id="1")
        await queue.submit(request)

        # Run worker briefly
        worker_task = asyncio.create_task(worker.run())

        # Wait for failure
        with pytest.raises(RuntimeError) as exc_info:
            await asyncio.wait_for(
                queue.wait_result("1", timeout=5.0),
                timeout=5.0,
            )

        assert "Test error" in str(exc_info.value)

        # Stop worker
        await worker.stop()
        await queue.shutdown()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Verify metrics
        metrics = queue.get_metrics()
        assert metrics.total_failed == 1

    @pytest.mark.asyncio
    async def test_worker_respects_timeout(self):
        """Worker times out slow execution."""
        queue = RequestQueue()
        # Executor that takes 10 seconds (will timeout)
        executor = create_mock_executor(delay=10)
        # Very short timeout
        config = create_queue_config(skill_timeout_seconds=1)

        worker = QueueWorker(
            worker_id=0,
            queue=queue,
            executor=executor,
            config=config,
        )

        # Submit skill request (uses skill_timeout)
        request = create_queued_request(request_id="1", routing_type="skill")
        await queue.submit(request)

        # Run worker
        worker_task = asyncio.create_task(worker.run())

        # Wait for timeout failure
        with pytest.raises(RuntimeError) as exc_info:
            await asyncio.wait_for(
                queue.wait_result("1", timeout=10.0),
                timeout=10.0,
            )

        assert "timeout" in str(exc_info.value).lower()

        # Stop worker
        await worker.stop()
        await queue.shutdown()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_worker_checks_cancellation_before_execution(self):
        """Worker skips cancelled requests."""
        queue = RequestQueue()
        executor = create_mock_executor()
        config = create_queue_config()

        worker = QueueWorker(
            worker_id=0,
            queue=queue,
            executor=executor,
            config=config,
        )

        # Create request with cancelled context
        request = create_queued_request(request_id="1")
        request.context.cancellation_token.is_set.return_value = True

        await queue.submit(request)

        # Run worker
        worker_task = asyncio.create_task(worker.run())

        # Wait for failure (cancelled)
        with pytest.raises(RuntimeError) as exc_info:
            await asyncio.wait_for(
                queue.wait_result("1", timeout=5.0),
                timeout=5.0,
            )

        assert "cancelled" in str(exc_info.value).lower()

        # Executor should NOT have been called
        executor.execute.assert_not_called()

        # Stop
        await worker.stop()
        await queue.shutdown()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_worker_is_busy_tracking(self):
        """Worker tracks busy state correctly."""
        queue = RequestQueue()
        # Slow executor
        executor = create_mock_executor(delay=0.5)
        config = create_queue_config()

        worker = QueueWorker(
            worker_id=0,
            queue=queue,
            executor=executor,
            config=config,
        )

        assert worker.is_busy is False
        assert worker.current_request_id is None

        # Submit and start processing
        request = create_queued_request(request_id="test-id")
        await queue.submit(request)

        worker_task = asyncio.create_task(worker.run())

        # Give time for worker to pick up request
        await asyncio.sleep(0.1)

        assert worker.is_busy is True
        assert worker.current_request_id == "test-id"

        # Wait for completion
        await asyncio.wait_for(
            queue.wait_result("test-id", timeout=5.0),
            timeout=5.0,
        )

        await asyncio.sleep(0.1)

        assert worker.is_busy is False
        assert worker.current_request_id is None

        # Cleanup
        await worker.stop()
        await queue.shutdown()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


# =============================================================================
# WorkerPool Tests
# =============================================================================

class TestWorkerPool:
    """Tests for worker pool management."""

    @pytest.mark.asyncio
    async def test_pool_starts_workers(self):
        """Pool starts specified number of workers."""
        queue = RequestQueue()
        executor = create_mock_executor()
        config = create_queue_config()

        pool = WorkerPool(
            worker_count=3,
            queue=queue,
            executor=executor,
            config=config,
        )

        await pool.start()

        assert pool.total_workers == 3
        assert pool.idle_workers == 3
        assert pool.busy_workers == 0

        await pool.stop()
        await queue.shutdown()

    @pytest.mark.asyncio
    async def test_pool_tracks_busy_workers(self):
        """Pool tracks busy worker count."""
        queue = RequestQueue()
        # Slow executor
        executor = create_mock_executor(delay=0.5)
        config = create_queue_config()

        pool = WorkerPool(
            worker_count=2,
            queue=queue,
            executor=executor,
            config=config,
        )

        await pool.start()

        # Submit two requests
        await queue.submit(create_queued_request(request_id="1"))
        await queue.submit(create_queued_request(request_id="2"))

        # Wait for workers to pick up
        await asyncio.sleep(0.1)

        assert pool.busy_workers == 2
        assert pool.idle_workers == 0

        # Wait for completion
        await asyncio.gather(
            queue.wait_result("1", timeout=5.0),
            queue.wait_result("2", timeout=5.0),
        )

        await asyncio.sleep(0.1)

        assert pool.busy_workers == 0
        assert pool.idle_workers == 2

        await pool.stop()
        await queue.shutdown()

    @pytest.mark.asyncio
    async def test_pool_get_worker_status(self):
        """Pool returns worker status list."""
        queue = RequestQueue()
        executor = create_mock_executor()
        config = create_queue_config()

        pool = WorkerPool(
            worker_count=2,
            queue=queue,
            executor=executor,
            config=config,
        )

        await pool.start()

        status = pool.get_worker_status()

        assert len(status) == 2
        assert status[0]["id"] == 0
        assert status[1]["id"] == 1
        assert all(not w["busy"] for w in status)

        await pool.stop()
        await queue.shutdown()

    @pytest.mark.asyncio
    async def test_pool_graceful_shutdown(self):
        """Pool waits for workers to finish on shutdown."""
        queue = RequestQueue()
        # Slow executor
        executor = create_mock_executor(delay=0.3)
        config = create_queue_config()

        pool = WorkerPool(
            worker_count=1,
            queue=queue,
            executor=executor,
            config=config,
        )

        await pool.start()

        # Submit request
        await queue.submit(create_queued_request(request_id="1"))

        # Give time for processing to start
        await asyncio.sleep(0.1)
        assert pool.busy_workers == 1

        # Stop should wait for worker to finish
        await pool.stop(timeout=5.0)

        # Pool should be empty
        assert pool.total_workers == 0

        await queue.shutdown()


# =============================================================================
# QueueManager Tests
# =============================================================================

class TestQueueManager:
    """Tests for queue manager orchestration."""

    @pytest.mark.asyncio
    async def test_manager_start_stop(self):
        """Manager starts and stops cleanly."""
        queue = RequestQueue()
        executor = create_mock_executor()

        # Create mock config
        config = MagicMock()
        config.queue = create_queue_config(worker_count=2)
        config.execution_timeout = 60

        manager = QueueManager(
            queue=queue,
            executor=executor,
            config=config,
        )

        assert manager.is_running is False

        await manager.start()
        assert manager.is_running is True

        await manager.stop()
        assert manager.is_running is False

    @pytest.mark.asyncio
    async def test_manager_submit_and_wait(self):
        """Manager handles submit and wait_for_result."""
        queue = RequestQueue()
        mock_result = MagicMock(content="success")
        executor = create_mock_executor(result=mock_result)

        config = MagicMock()
        config.queue = create_queue_config(worker_count=1)
        config.execution_timeout = 60

        manager = QueueManager(
            queue=queue,
            executor=executor,
            config=config,
        )

        await manager.start()

        # Submit request
        request = create_queued_request(request_id="test-1")
        request_id = await manager.submit(request)

        assert request_id == "test-1"

        # Wait for result
        result = await manager.wait_for_result(request_id, timeout=5.0)

        assert result.content == "success"

        await manager.stop()

    @pytest.mark.asyncio
    async def test_manager_cancel(self):
        """Manager can cancel requests."""
        queue = RequestQueue()
        executor = create_mock_executor()

        config = MagicMock()
        config.queue = create_queue_config(worker_count=1)
        config.execution_timeout = 60

        manager = QueueManager(
            queue=queue,
            executor=executor,
            config=config,
        )

        await manager.start()

        # Submit and immediately cancel
        request = create_queued_request(request_id="cancel-me")
        await manager.submit(request)

        result = await manager.cancel("cancel-me")
        assert result is True

        await manager.stop()

    @pytest.mark.asyncio
    async def test_manager_get_position(self):
        """Manager returns queue position."""
        queue = RequestQueue()
        # Slow executor
        executor = create_mock_executor(delay=1.0)

        config = MagicMock()
        config.queue = create_queue_config(worker_count=1)
        config.execution_timeout = 60

        manager = QueueManager(
            queue=queue,
            executor=executor,
            config=config,
        )

        await manager.start()

        # Submit two requests (first will start processing)
        await manager.submit(create_queued_request(request_id="first"))
        await asyncio.sleep(0.1)  # Let first get picked up

        await manager.submit(create_queued_request(request_id="second"))

        # Second should be in queue at position 0
        position = manager.get_position("second")
        assert position == 0

        await manager.stop()

    @pytest.mark.asyncio
    async def test_manager_get_metrics(self):
        """Manager returns queue metrics."""
        queue = RequestQueue()
        executor = create_mock_executor()

        config = MagicMock()
        config.queue = create_queue_config(worker_count=1)
        config.execution_timeout = 60

        manager = QueueManager(
            queue=queue,
            executor=executor,
            config=config,
        )

        await manager.start()

        metrics = manager.get_metrics()

        assert hasattr(metrics, "queue_depth")
        assert hasattr(metrics, "total_enqueued")

        await manager.stop()

    @pytest.mark.asyncio
    async def test_manager_get_status(self):
        """Manager returns full status."""
        queue = RequestQueue()
        executor = create_mock_executor()

        config = MagicMock()
        config.queue = create_queue_config(worker_count=2)
        config.execution_timeout = 60

        manager = QueueManager(
            queue=queue,
            executor=executor,
            config=config,
        )

        await manager.start()

        status = manager.get_status()

        assert "queue_depth" in status
        assert "in_flight" in status
        assert "workers" in status
        assert "metrics" in status

        assert status["workers"]["total"] == 2

        await manager.stop()

    @pytest.mark.asyncio
    async def test_manager_worker_status(self):
        """Manager returns worker status."""
        queue = RequestQueue()
        executor = create_mock_executor()

        config = MagicMock()
        config.queue = create_queue_config(worker_count=3)
        config.execution_timeout = 60

        manager = QueueManager(
            queue=queue,
            executor=executor,
            config=config,
        )

        await manager.start()

        status = manager.get_worker_status()

        assert status["total"] == 3
        assert status["busy"] == 0
        assert status["idle"] == 3
        assert len(status["workers"]) == 3

        await manager.stop()

    @pytest.mark.asyncio
    async def test_manager_not_running_worker_status(self):
        """Manager returns empty status when not running."""
        queue = RequestQueue()
        executor = create_mock_executor()

        config = MagicMock()
        config.queue = create_queue_config()
        config.execution_timeout = 60

        manager = QueueManager(
            queue=queue,
            executor=executor,
            config=config,
        )

        # Not started
        status = manager.get_worker_status()

        assert status["total"] == 0
        assert status["busy"] == 0
        assert status["idle"] == 0
        assert status["workers"] == []


# =============================================================================
# Concurrent Processing Tests
# =============================================================================

class TestConcurrentProcessing:
    """Tests for concurrent request processing."""

    @pytest.mark.asyncio
    async def test_multiple_workers_process_concurrently(self):
        """Multiple workers process requests in parallel."""
        queue = RequestQueue()

        # Track execution order
        execution_order = []

        async def track_execution(*args, **kwargs):
            request_id = args[1]  # user_input contains request_id
            execution_order.append(f"start-{request_id}")
            await asyncio.sleep(0.1)
            execution_order.append(f"end-{request_id}")
            return MagicMock(content=request_id)

        executor = MagicMock()
        executor.execute = AsyncMock(side_effect=track_execution)

        config = MagicMock()
        config.queue = create_queue_config(worker_count=3)
        config.execution_timeout = 60

        manager = QueueManager(
            queue=queue,
            executor=executor,
            config=config,
        )

        await manager.start()

        # Submit 3 requests
        requests = []
        for i in range(3):
            req = create_queued_request(request_id=str(i))
            req.user_input = str(i)  # Use input to track
            requests.append(req)
            await manager.submit(req)

        # Wait for all
        await asyncio.gather(*[
            manager.wait_for_result(str(i), timeout=5.0)
            for i in range(3)
        ])

        await manager.stop()

        # All starts should happen before all ends (concurrent processing)
        # At least 2 should start before first ends
        start_before_first_end = 0
        first_end_idx = next(
            i for i, x in enumerate(execution_order) if x.startswith("end-")
        )
        for i in range(first_end_idx):
            if execution_order[i].startswith("start-"):
                start_before_first_end += 1

        assert start_before_first_end >= 2  # At least 2 concurrent
