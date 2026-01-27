"""Tests for visibility monitor implementation."""
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.visibility_monitor import VisibilityMonitor
from app.core.interfaces.queue import QueuedRequest, UserTier


@pytest.fixture
def mock_config():
    """Create a mock config with queue settings."""
    config = MagicMock()
    config.queue.visibility_timeout_seconds = 1.0  # Short timeout for testing
    config.queue.visibility_check_interval_seconds = 0.1  # Short interval for testing
    config.queue.max_retries = 2
    # Classification-aware visibility timeout method (returns default for non-IMAGE)
    config.queue.get_visibility_timeout_for_classification = MagicMock(
        side_effect=lambda classification: 900 if classification == "IMAGE" else 5.0
    )
    return config


@pytest.fixture
def mock_queue():
    """Create a mock queue with async methods."""
    queue = MagicMock()
    queue.get_in_flight_snapshot = MagicMock(return_value={})
    queue.requeue_for_retry = AsyncMock(return_value=True)
    queue.mark_failed = AsyncMock()
    return queue


@pytest.fixture
def mock_circuit_registry():
    """Create a mock circuit breaker registry."""
    registry = MagicMock()
    registry.record_failure = MagicMock()
    return registry


@pytest.fixture
def mock_request():
    """Create a mock queued request."""
    request = MagicMock(spec=QueuedRequest)
    request.request_id = "test-request-id"
    request.user_id = "test-user"
    request.session_id = "test-session"
    request.user_tier = UserTier.NORMAL
    request.routing_type = "agent"
    request.routing_result = None  # No routing result (uses default timeout)
    request.retry_count = 0
    request.started_at = datetime.now(timezone.utc) - timedelta(seconds=10)  # Started 10s ago
    return request


class TestVisibilityMonitorInit:
    """Test VisibilityMonitor initialization."""

    def test_init_with_all_dependencies(self, mock_queue, mock_config, mock_circuit_registry):
        """Test initialization with all dependencies."""
        monitor = VisibilityMonitor(
            queue=mock_queue,
            config=mock_config,
            circuit_registry=mock_circuit_registry,
        )

        assert monitor._queue == mock_queue
        assert monitor._config == mock_config
        assert monitor._circuit_registry == mock_circuit_registry
        assert monitor._running is False
        assert monitor._task is None

    def test_init_without_circuit_registry(self, mock_queue, mock_config):
        """Test initialization without circuit registry."""
        monitor = VisibilityMonitor(
            queue=mock_queue,
            config=mock_config,
        )

        assert monitor._circuit_registry is None


class TestVisibilityMonitorStartStop:
    """Test VisibilityMonitor start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self, mock_queue, mock_config):
        """Test start sets running flag."""
        monitor = VisibilityMonitor(queue=mock_queue, config=mock_config)

        await monitor.start()
        assert monitor._running is True
        assert monitor._task is not None

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self, mock_queue, mock_config):
        """Test stop clears running flag."""
        monitor = VisibilityMonitor(queue=mock_queue, config=mock_config)

        await monitor.start()
        await monitor.stop()

        assert monitor._running is False
        assert monitor._task is None

    @pytest.mark.asyncio
    async def test_double_start_logs_warning(self, mock_queue, mock_config, caplog):
        """Test double start logs warning."""
        monitor = VisibilityMonitor(queue=mock_queue, config=mock_config)

        await monitor.start()
        await monitor.start()  # Second start

        assert "already running" in caplog.text.lower()
        await monitor.stop()


class TestVisibilityMonitorStuckDetection:
    """Test stuck request detection."""

    @pytest.mark.asyncio
    async def test_no_stuck_requests_does_nothing(self, mock_queue, mock_config):
        """Test no action when no requests are stuck."""
        mock_queue.get_in_flight_snapshot.return_value = {}

        monitor = VisibilityMonitor(queue=mock_queue, config=mock_config)
        await monitor._check_stuck_requests(default_timeout=1.0)

        mock_queue.requeue_for_retry.assert_not_called()
        mock_queue.mark_failed.assert_not_called()

    @pytest.mark.asyncio
    async def test_detects_stuck_request(self, mock_queue, mock_config, mock_request):
        """Test detection of stuck request."""
        # Request started 10 seconds ago
        mock_request.started_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        mock_queue.get_in_flight_snapshot.return_value = {"test-id": mock_request}

        monitor = VisibilityMonitor(queue=mock_queue, config=mock_config)
        await monitor._check_stuck_requests(default_timeout=5.0)  # 5s timeout, request is 10s old

        # Should trigger requeue since retry_count < max_retries
        mock_queue.requeue_for_retry.assert_called_once_with("test-id")

    @pytest.mark.asyncio
    async def test_ignores_recent_request(self, mock_queue, mock_config, mock_request):
        """Test ignores recent requests."""
        # Request started 1 second ago
        mock_request.started_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        mock_queue.get_in_flight_snapshot.return_value = {"test-id": mock_request}

        monitor = VisibilityMonitor(queue=mock_queue, config=mock_config)
        await monitor._check_stuck_requests(default_timeout=10.0)  # 10s timeout, request is 1s old

        mock_queue.requeue_for_retry.assert_not_called()
        mock_queue.mark_failed.assert_not_called()

    @pytest.mark.asyncio
    async def test_requeues_retriable_request(self, mock_queue, mock_config, mock_request):
        """Test requeues request when retry count < max."""
        mock_request.started_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        mock_request.retry_count = 0  # Can retry
        mock_queue.get_in_flight_snapshot.return_value = {"test-id": mock_request}

        monitor = VisibilityMonitor(queue=mock_queue, config=mock_config)
        await monitor._check_stuck_requests(default_timeout=5.0)

        mock_queue.requeue_for_retry.assert_called_once_with("test-id")
        mock_queue.mark_failed.assert_not_called()

    @pytest.mark.asyncio
    async def test_fails_exhausted_request(self, mock_queue, mock_config, mock_request, mock_circuit_registry):
        """Test fails request when retries exhausted."""
        mock_request.started_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        mock_request.retry_count = 2  # At max retries
        mock_queue.get_in_flight_snapshot.return_value = {"test-id": mock_request}

        monitor = VisibilityMonitor(
            queue=mock_queue,
            config=mock_config,
            circuit_registry=mock_circuit_registry,
        )
        await monitor._check_stuck_requests(default_timeout=5.0)

        mock_queue.requeue_for_retry.assert_not_called()
        mock_queue.mark_failed.assert_called_once()
        mock_circuit_registry.record_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_timezone_naive_started_at(self, mock_queue, mock_config, mock_request):
        """Test handles timezone-naive started_at datetime.

        Implementation assumes naive datetimes are in UTC.
        """
        # Use timezone-naive datetime in UTC (not local time)
        # datetime.utcnow() is deprecated but works for testing
        utc_now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        mock_request.started_at = utc_now_naive - timedelta(seconds=10)
        mock_queue.get_in_flight_snapshot.return_value = {"test-id": mock_request}

        monitor = VisibilityMonitor(queue=mock_queue, config=mock_config)
        await monitor._check_stuck_requests(default_timeout=5.0)

        # Should still detect as stuck
        mock_queue.requeue_for_retry.assert_called_once()

    @pytest.mark.asyncio
    async def test_ignores_request_without_started_at(self, mock_queue, mock_config, mock_request):
        """Test ignores requests without started_at timestamp."""
        mock_request.started_at = None
        mock_queue.get_in_flight_snapshot.return_value = {"test-id": mock_request}

        monitor = VisibilityMonitor(queue=mock_queue, config=mock_config)
        await monitor._check_stuck_requests(default_timeout=5.0)

        mock_queue.requeue_for_retry.assert_not_called()
        mock_queue.mark_failed.assert_not_called()


class TestVisibilityMonitorCircuitBreakerIntegration:
    """Test circuit breaker integration."""

    @pytest.mark.asyncio
    async def test_signals_circuit_breaker_on_timeout(self, mock_queue, mock_config, mock_request, mock_circuit_registry):
        """Test signals circuit breaker when request times out permanently."""
        mock_request.started_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        mock_request.retry_count = 2  # At max
        mock_queue.get_in_flight_snapshot.return_value = {"test-id": mock_request}

        monitor = VisibilityMonitor(
            queue=mock_queue,
            config=mock_config,
            circuit_registry=mock_circuit_registry,
        )
        await monitor._check_stuck_requests(default_timeout=5.0)

        mock_circuit_registry.record_failure.assert_called_once()
        assert "Visibility timeout" in mock_circuit_registry.record_failure.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_circuit_breaker_signal_on_requeue(self, mock_queue, mock_config, mock_request, mock_circuit_registry):
        """Test no circuit breaker signal when request is requeued."""
        mock_request.started_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        mock_request.retry_count = 0  # Can still retry
        mock_queue.get_in_flight_snapshot.return_value = {"test-id": mock_request}

        monitor = VisibilityMonitor(
            queue=mock_queue,
            config=mock_config,
            circuit_registry=mock_circuit_registry,
        )
        await monitor._check_stuck_requests(default_timeout=5.0)

        # Should not signal circuit breaker since request is being retried
        mock_circuit_registry.record_failure.assert_not_called()


class TestVisibilityMonitorMultipleRequests:
    """Test handling multiple in-flight requests."""

    @pytest.mark.asyncio
    async def test_processes_multiple_stuck_requests(self, mock_queue, mock_config):
        """Test processes multiple stuck requests."""
        # Create multiple stuck requests
        request1 = MagicMock(spec=QueuedRequest)
        request1.request_id = "request-1"
        request1.started_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        request1.retry_count = 0
        request1.routing_result = None

        request2 = MagicMock(spec=QueuedRequest)
        request2.request_id = "request-2"
        request2.started_at = datetime.now(timezone.utc) - timedelta(seconds=15)
        request2.retry_count = 0
        request2.routing_result = None

        mock_queue.get_in_flight_snapshot.return_value = {
            "request-1": request1,
            "request-2": request2,
        }

        monitor = VisibilityMonitor(queue=mock_queue, config=mock_config)
        await monitor._check_stuck_requests(default_timeout=5.0)

        assert mock_queue.requeue_for_retry.call_count == 2

    @pytest.mark.asyncio
    async def test_handles_mixed_states(self, mock_queue, mock_config, mock_circuit_registry):
        """Test handles mix of retriable and exhausted requests."""
        # Request that can be retried
        retriable = MagicMock(spec=QueuedRequest)
        retriable.request_id = "retriable"
        retriable.started_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        retriable.retry_count = 0
        retriable.routing_result = None

        # Request that is exhausted
        exhausted = MagicMock(spec=QueuedRequest)
        exhausted.request_id = "exhausted"
        exhausted.started_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        exhausted.retry_count = 2  # At max
        exhausted.routing_result = None

        # Recent request (not stuck)
        recent = MagicMock(spec=QueuedRequest)
        recent.request_id = "recent"
        recent.started_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        recent.retry_count = 0
        recent.routing_result = None

        mock_queue.get_in_flight_snapshot.return_value = {
            "retriable": retriable,
            "exhausted": exhausted,
            "recent": recent,
        }

        monitor = VisibilityMonitor(
            queue=mock_queue,
            config=mock_config,
            circuit_registry=mock_circuit_registry,
        )
        await monitor._check_stuck_requests(default_timeout=5.0)

        # Should requeue retriable
        mock_queue.requeue_for_retry.assert_called_once_with("retriable")

        # Should fail exhausted
        mock_queue.mark_failed.assert_called_once()
        assert "exhausted" in str(mock_queue.mark_failed.call_args)

        # Should signal circuit breaker for exhausted
        mock_circuit_registry.record_failure.assert_called_once()
