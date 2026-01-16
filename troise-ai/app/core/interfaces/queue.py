"""Queue interfaces for request processing.

Follows Interface Segregation Principle - different consumers
use different focused interfaces:
- IRequestSubmitter: For WebSocket handlers submitting requests
- IQueueInternal: For workers consuming and completing requests
- IQueueMonitor: For metrics/monitoring endpoints
- IPrioritizer: For pluggable priority calculation
"""
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Protocol

if TYPE_CHECKING:
    from ..context import ExecutionContext
    from ..executor import ExecutionResult
    from ..router import RoutingResult


@dataclass
class QueueMetrics:
    """Queue health and performance metrics."""

    queue_depth: int
    in_flight_count: int
    total_enqueued: int
    total_completed: int
    total_failed: int
    total_timeouts: int
    total_cancelled: int
    total_retries: int  # Requests requeued for retry
    avg_wait_time_ms: float
    avg_process_time_ms: float


class UserTier:
    """User tier levels for priority calculation.

    Priority order (highest to lowest): VIP > PREMIUM > NORMAL
    """

    VIP = "vip"
    PREMIUM = "premium"
    NORMAL = "normal"


@dataclass
class QueuedRequest:
    """Request waiting in queue for processing.

    Contains all information needed for execution and priority calculation.
    """

    request_id: str
    user_id: str
    session_id: str
    user_tier: str  # UserTier.VIP or UserTier.NORMAL
    routing_result: "RoutingResult"
    user_input: str
    context: "ExecutionContext"
    queued_at: datetime
    started_at: Optional[datetime] = None
    timeout_seconds: int = 300

    # Retry tracking
    retry_count: int = 0
    last_error: Optional[str] = None
    first_attempt_at: Optional[datetime] = None  # Original queued_at before retries

    @property
    def routing_type(self) -> str:
        """Get the routing type (skill or agent)."""
        return self.routing_result.type


class IPrioritizer(Protocol):
    """Pluggable priority calculation strategy.

    Allows customizing how requests are prioritized without
    modifying the queue implementation (Open/Closed Principle).
    """

    def calculate_score(self, request: "QueuedRequest") -> float:
        """Calculate priority score for a request.

        Higher scores = higher priority (processed first).

        Args:
            request: The queued request to score.

        Returns:
            Priority score as float.
        """
        ...


class IRequestSubmitter(Protocol):
    """Interface for submitting requests to the queue.

    Minimal interface for WebSocket handlers - they only need
    to submit requests and wait for results.
    """

    async def submit(self, request: "QueuedRequest") -> str:
        """Submit a request to the queue.

        Args:
            request: The request to queue.

        Returns:
            The request_id for tracking.
        """
        ...

    async def wait_result(
        self,
        request_id: str,
        timeout: float,
    ) -> "ExecutionResult":
        """Wait for a request to complete.

        Blocks until the request completes or times out.

        Args:
            request_id: The request to wait for.
            timeout: Maximum seconds to wait.

        Returns:
            The execution result.

        Raises:
            TimeoutError: If the wait times out.
            KeyError: If request_id is not found.
        """
        ...

    async def cancel(self, request_id: str) -> bool:
        """Cancel a queued or in-flight request.

        Args:
            request_id: The request to cancel.

        Returns:
            True if cancelled, False if not found or already complete.
        """
        ...

    def get_position(self, request_id: str) -> Optional[int]:
        """Get queue position for a request.

        Args:
            request_id: The request to find.

        Returns:
            Position in queue (0 = next), None if not queued.
        """
        ...


class IQueueInternal(Protocol):
    """Internal interface for queue workers.

    Used by workers to dequeue requests and report results.
    Separated from IRequestSubmitter to avoid exposing internal
    methods to WebSocket handlers.
    """

    async def dequeue(self) -> Optional["QueuedRequest"]:
        """Get the highest priority request from the queue.

        Blocks if the queue is empty until a request is available.

        Returns:
            The next request to process, or None if shutdown.
        """
        ...

    async def mark_complete(
        self,
        request_id: str,
        result: "ExecutionResult",
    ) -> None:
        """Mark a request as successfully completed.

        Args:
            request_id: The completed request.
            result: The execution result.
        """
        ...

    async def mark_failed(
        self,
        request_id: str,
        error: str,
    ) -> None:
        """Mark a request as failed.

        Args:
            request_id: The failed request.
            error: Error description.
        """
        ...

    async def requeue_for_retry(self, request_id: str) -> bool:
        """Move request from in_flight back to queue for retry.

        Used by VisibilityMonitor to requeue stuck requests.

        Args:
            request_id: The request to requeue.

        Returns:
            True if requeued, False if not found.
        """
        ...

    def get_in_flight_snapshot(self) -> dict[str, "QueuedRequest"]:
        """Get a snapshot of currently in-flight requests.

        Used by VisibilityMonitor to check for stuck requests.

        Returns:
            Dict mapping request_id to QueuedRequest.
        """
        ...


class IQueueMonitor(Protocol):
    """Interface for queue monitoring and metrics.

    Used by the /queue/status endpoint and alerting systems.
    """

    def get_metrics(self) -> QueueMetrics:
        """Get current queue metrics.

        Returns:
            QueueMetrics with current state and counters.
        """
        ...

    def get_queue_depth(self) -> int:
        """Get number of requests waiting in queue.

        Returns:
            Count of queued requests.
        """
        ...

    def get_in_flight_count(self) -> int:
        """Get number of requests currently being processed.

        Returns:
            Count of in-flight requests.
        """
        ...
