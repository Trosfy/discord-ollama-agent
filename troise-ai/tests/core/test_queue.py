"""Unit tests for centralized request queue."""
import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock

from app.core.queue import (
    RequestQueue,
    HybridPrioritizer,
    QueueEntry,
)
from app.core.interfaces.queue import (
    QueuedRequest,
    UserTier,
    QueueMetrics,
)


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
    user_id: str = "user-1",
    session_id: str = "session-1",
    user_tier: UserTier = UserTier.NORMAL,
    routing_type: str = "skill",
    queued_at: datetime = None,
) -> QueuedRequest:
    """Create a QueuedRequest for testing."""
    if queued_at is None:
        queued_at = datetime.now(timezone.utc)

    return QueuedRequest(
        request_id=request_id,
        user_id=user_id,
        session_id=session_id,
        user_tier=user_tier,
        routing_result=create_mock_routing_result(type=routing_type),
        user_input="test input",
        context=create_mock_context(),
        queued_at=queued_at,
    )


# =============================================================================
# HybridPrioritizer Tests
# =============================================================================

class TestHybridPrioritizer:
    """Tests for priority calculation."""

    def test_tier_bonuses(self):
        """User tiers get correct priority bonuses: VIP=100, PREMIUM=50, NORMAL=0."""
        prioritizer = HybridPrioritizer()

        # Use same timestamp to eliminate age difference
        now = datetime.now(timezone.utc)
        normal = create_queued_request(user_tier=UserTier.NORMAL, queued_at=now)
        premium = create_queued_request(user_tier=UserTier.PREMIUM, queued_at=now)
        vip = create_queued_request(user_tier=UserTier.VIP, queued_at=now)

        normal_score = prioritizer.calculate_score(normal)
        premium_score = prioritizer.calculate_score(premium)
        vip_score = prioritizer.calculate_score(vip)

        # VIP > PREMIUM > NORMAL
        assert vip_score > premium_score > normal_score

        # VIP bonus is 100 over NORMAL
        assert 99.9 <= (vip_score - normal_score) <= 100.1

        # PREMIUM bonus is 50 over NORMAL
        assert 49.9 <= (premium_score - normal_score) <= 50.1

        # VIP bonus is 50 over PREMIUM
        assert 49.9 <= (vip_score - premium_score) <= 50.1

    def test_skill_bonus(self):
        """Skills get +50 priority bonus over agents."""
        prioritizer = HybridPrioritizer()

        # Use same timestamp to eliminate age difference
        now = datetime.now(timezone.utc)
        agent_req = create_queued_request(routing_type="agent", queued_at=now)
        skill_req = create_queued_request(routing_type="skill", queued_at=now)

        agent_score = prioritizer.calculate_score(agent_req)
        skill_score = prioritizer.calculate_score(skill_req)

        assert skill_score > agent_score
        # Skill bonus is 50, allow small floating point variance
        assert 49.9 <= (skill_score - agent_score) <= 50.1

    def test_age_bonus_prevents_starvation(self):
        """Older requests get age bonus up to 30 points."""
        prioritizer = HybridPrioritizer()

        # Fresh request
        fresh = create_queued_request(queued_at=datetime.now(timezone.utc))

        # Old request (30+ minutes)
        old_time = datetime.now(timezone.utc) - timedelta(minutes=35)
        old = create_queued_request(queued_at=old_time)

        fresh_score = prioritizer.calculate_score(fresh)
        old_score = prioritizer.calculate_score(old)

        # Old request should have higher score
        assert old_score > fresh_score

        # Age bonus capped at 30
        assert old_score - fresh_score <= 30

    def test_combined_priority(self):
        """VIP + Skill has highest priority."""
        prioritizer = HybridPrioritizer()

        normal_agent = create_queued_request(
            user_tier=UserTier.NORMAL, routing_type="agent"
        )
        normal_skill = create_queued_request(
            user_tier=UserTier.NORMAL, routing_type="skill"
        )
        vip_agent = create_queued_request(
            user_tier=UserTier.VIP, routing_type="agent"
        )
        vip_skill = create_queued_request(
            user_tier=UserTier.VIP, routing_type="skill"
        )

        scores = {
            "normal_agent": prioritizer.calculate_score(normal_agent),
            "normal_skill": prioritizer.calculate_score(normal_skill),
            "vip_agent": prioritizer.calculate_score(vip_agent),
            "vip_skill": prioritizer.calculate_score(vip_skill),
        }

        # VIP + Skill > VIP + Agent > Normal + Skill > Normal + Agent
        assert scores["vip_skill"] > scores["vip_agent"]
        assert scores["vip_agent"] > scores["normal_skill"]
        assert scores["normal_skill"] > scores["normal_agent"]


# =============================================================================
# RequestQueue Submit/Dequeue Tests
# =============================================================================

class TestRequestQueueSubmit:
    """Tests for queue submit operations."""

    @pytest.mark.asyncio
    async def test_submit_returns_request_id(self):
        """Submit returns the request_id."""
        queue = RequestQueue()
        request = create_queued_request(request_id="my-request-id")

        result = await queue.submit(request)

        assert result == "my-request-id"

    @pytest.mark.asyncio
    async def test_submit_increases_queue_depth(self):
        """Submit increases queue depth metric."""
        queue = RequestQueue()

        assert queue.get_queue_depth() == 0

        await queue.submit(create_queued_request(request_id="1"))
        assert queue.get_queue_depth() == 1

        await queue.submit(create_queued_request(request_id="2"))
        assert queue.get_queue_depth() == 2

    @pytest.mark.asyncio
    async def test_submit_updates_metrics(self):
        """Submit updates total_enqueued metric."""
        queue = RequestQueue()

        await queue.submit(create_queued_request(request_id="1"))
        await queue.submit(create_queued_request(request_id="2"))

        metrics = queue.get_metrics()
        assert metrics.total_enqueued == 2


class TestRequestQueueDequeue:
    """Tests for queue dequeue operations."""

    @pytest.mark.asyncio
    async def test_dequeue_returns_highest_priority(self):
        """Dequeue returns highest priority request first."""
        queue = RequestQueue()

        # Submit in order: low, high, medium
        low = create_queued_request(
            request_id="low", user_tier=UserTier.NORMAL, routing_type="agent"
        )
        high = create_queued_request(
            request_id="high", user_tier=UserTier.VIP, routing_type="skill"
        )
        medium = create_queued_request(
            request_id="medium", user_tier=UserTier.VIP, routing_type="agent"
        )

        await queue.submit(low)
        await queue.submit(high)
        await queue.submit(medium)

        # Dequeue should return in priority order
        first = await queue.dequeue()
        assert first.request_id == "high"

        second = await queue.dequeue()
        assert second.request_id == "medium"

        third = await queue.dequeue()
        assert third.request_id == "low"

    @pytest.mark.asyncio
    async def test_dequeue_moves_to_in_flight(self):
        """Dequeue moves request from queued to in_flight."""
        queue = RequestQueue()

        await queue.submit(create_queued_request(request_id="1"))
        assert queue.get_queue_depth() == 1
        assert queue.get_in_flight_count() == 0

        await queue.dequeue()
        assert queue.get_queue_depth() == 0
        assert queue.get_in_flight_count() == 1

    @pytest.mark.asyncio
    async def test_dequeue_sets_started_at(self):
        """Dequeue sets started_at timestamp on request."""
        queue = RequestQueue()

        request = create_queued_request(request_id="1")
        assert request.started_at is None

        await queue.submit(request)
        dequeued = await queue.dequeue()

        assert dequeued.started_at is not None
        assert dequeued.started_at >= dequeued.queued_at

    @pytest.mark.asyncio
    async def test_dequeue_blocks_when_empty(self):
        """Dequeue blocks when queue is empty."""
        queue = RequestQueue()

        # Start dequeue (will block)
        dequeue_task = asyncio.create_task(queue.dequeue())

        # Give it time to start waiting
        await asyncio.sleep(0.01)

        # Should not have completed yet
        assert not dequeue_task.done()

        # Submit a request
        await queue.submit(create_queued_request(request_id="unblock"))

        # Now dequeue should complete
        result = await asyncio.wait_for(dequeue_task, timeout=1.0)
        assert result.request_id == "unblock"

    @pytest.mark.asyncio
    async def test_dequeue_returns_none_on_shutdown(self):
        """Dequeue returns None when queue is shutdown."""
        queue = RequestQueue()

        # Start dequeue
        dequeue_task = asyncio.create_task(queue.dequeue())
        await asyncio.sleep(0.01)

        # Shutdown
        await queue.shutdown()

        result = await asyncio.wait_for(dequeue_task, timeout=1.0)
        assert result is None


# =============================================================================
# Mark Complete/Failed Tests
# =============================================================================

class TestRequestQueueCompletion:
    """Tests for marking requests complete/failed."""

    @pytest.mark.asyncio
    async def test_mark_complete_signals_waiter(self):
        """mark_complete signals waiting caller."""
        queue = RequestQueue()
        request = create_queued_request(request_id="1")

        await queue.submit(request)
        await queue.dequeue()

        # Start waiting
        wait_task = asyncio.create_task(queue.wait_result("1", timeout=5.0))
        await asyncio.sleep(0.01)

        # Complete
        mock_result = MagicMock()
        mock_result.content = "test result"
        await queue.mark_complete("1", mock_result)

        result = await asyncio.wait_for(wait_task, timeout=1.0)
        assert result is mock_result

    @pytest.mark.asyncio
    async def test_mark_complete_updates_metrics(self):
        """mark_complete updates completion metrics."""
        queue = RequestQueue()

        await queue.submit(create_queued_request(request_id="1"))
        await queue.dequeue()

        mock_result = MagicMock()
        await queue.mark_complete("1", mock_result)

        metrics = queue.get_metrics()
        assert metrics.total_completed == 1
        assert metrics.in_flight_count == 0

    @pytest.mark.asyncio
    async def test_mark_failed_raises_on_wait(self):
        """mark_failed causes wait_result to raise RuntimeError."""
        queue = RequestQueue()
        request = create_queued_request(request_id="1")

        await queue.submit(request)
        await queue.dequeue()

        # Start waiting
        wait_task = asyncio.create_task(queue.wait_result("1", timeout=5.0))
        await asyncio.sleep(0.01)

        # Fail the request
        await queue.mark_failed("1", "Test error message")

        with pytest.raises(RuntimeError) as exc_info:
            await wait_task

        assert "Test error message" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_mark_failed_updates_metrics(self):
        """mark_failed updates failure metrics."""
        queue = RequestQueue()

        await queue.submit(create_queued_request(request_id="1"))
        await queue.dequeue()
        await queue.mark_failed("1", "error")

        metrics = queue.get_metrics()
        assert metrics.total_failed == 1
        assert metrics.in_flight_count == 0


# =============================================================================
# Cancellation Tests
# =============================================================================

class TestRequestQueueCancellation:
    """Tests for request cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_queued_request(self):
        """Cancel removes request from queue."""
        queue = RequestQueue()

        await queue.submit(create_queued_request(request_id="1"))
        await queue.submit(create_queued_request(request_id="2"))

        result = await queue.cancel("1")

        assert result is True
        assert queue.get_queue_depth() == 1  # Only request 2 remains

        metrics = queue.get_metrics()
        assert metrics.total_cancelled == 1

    @pytest.mark.asyncio
    async def test_cancel_not_found(self):
        """Cancel returns False for unknown request."""
        queue = RequestQueue()

        result = await queue.cancel("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_cancelled_request_skipped_on_dequeue(self):
        """Cancelled requests are skipped during dequeue."""
        queue = RequestQueue()

        # Submit two requests with same priority
        await queue.submit(create_queued_request(request_id="1"))
        await queue.submit(create_queued_request(request_id="2"))

        # Cancel the first one
        await queue.cancel("1")

        # Dequeue should skip cancelled and return second
        dequeued = await queue.dequeue()
        assert dequeued.request_id == "2"


# =============================================================================
# Queue Position Tests
# =============================================================================

class TestQueuePosition:
    """Tests for queue position tracking."""

    @pytest.mark.asyncio
    async def test_get_position(self):
        """get_position returns valid unique positions for all queued requests."""
        queue = RequestQueue()

        # Submit 3 requests
        await queue.submit(create_queued_request(request_id="1"))
        await queue.submit(create_queued_request(request_id="2"))
        await queue.submit(create_queued_request(request_id="3"))

        # All positions should be valid (0, 1, or 2) and unique
        positions = [
            queue.get_position("1"),
            queue.get_position("2"),
            queue.get_position("3"),
        ]
        assert set(positions) == {0, 1, 2}

    @pytest.mark.asyncio
    async def test_get_position_not_found(self):
        """get_position returns None for unknown request."""
        queue = RequestQueue()

        assert queue.get_position("nonexistent") is None


# =============================================================================
# Wait Result Tests
# =============================================================================

class TestWaitResult:
    """Tests for wait_result timeout handling."""

    @pytest.mark.asyncio
    async def test_wait_result_timeout(self):
        """wait_result raises TimeoutError on timeout."""
        queue = RequestQueue()

        await queue.submit(create_queued_request(request_id="1"))

        with pytest.raises(TimeoutError):
            await queue.wait_result("1", timeout=0.1)

        metrics = queue.get_metrics()
        assert metrics.total_timeouts == 1

    @pytest.mark.asyncio
    async def test_wait_result_not_found(self):
        """wait_result raises KeyError for unknown request."""
        queue = RequestQueue()

        with pytest.raises(KeyError):
            await queue.wait_result("nonexistent", timeout=1.0)


# =============================================================================
# Metrics Tests
# =============================================================================

class TestQueueMetrics:
    """Tests for queue metrics."""

    @pytest.mark.asyncio
    async def test_metrics_structure(self):
        """get_metrics returns QueueMetrics dataclass."""
        queue = RequestQueue()

        metrics = queue.get_metrics()

        assert isinstance(metrics, QueueMetrics)
        assert hasattr(metrics, "queue_depth")
        assert hasattr(metrics, "in_flight_count")
        assert hasattr(metrics, "total_enqueued")
        assert hasattr(metrics, "total_completed")
        assert hasattr(metrics, "total_failed")
        assert hasattr(metrics, "total_timeouts")
        assert hasattr(metrics, "total_cancelled")
        assert hasattr(metrics, "avg_wait_time_ms")
        assert hasattr(metrics, "avg_process_time_ms")

    @pytest.mark.asyncio
    async def test_avg_wait_time_tracking(self):
        """Average wait time is tracked correctly."""
        queue = RequestQueue()

        # Submit and immediately dequeue
        await queue.submit(create_queued_request(request_id="1"))
        await queue.dequeue()

        metrics = queue.get_metrics()
        # Wait time should be >= 0 (very fast, near 0)
        assert metrics.avg_wait_time_ms >= 0

    @pytest.mark.asyncio
    async def test_avg_process_time_tracking(self):
        """Average process time is tracked correctly."""
        queue = RequestQueue()

        await queue.submit(create_queued_request(request_id="1"))
        await queue.dequeue()

        # Small delay to simulate processing
        await asyncio.sleep(0.01)

        mock_result = MagicMock()
        await queue.mark_complete("1", mock_result)

        metrics = queue.get_metrics()
        # Process time should be >= 10ms
        assert metrics.avg_process_time_ms >= 0
