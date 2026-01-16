"""Centralized request queue for TROISE AI.

Provides priority-based request queuing with:
- Hybrid priority scoring (user tier + task type + age)
- Async-safe operations with proper locking
- Result delivery via asyncio.Future
- Comprehensive metrics tracking
"""
import asyncio
import heapq
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .interfaces.queue import (
    IQueueInternal,
    IQueueMonitor,
    IPrioritizer,
    IRequestSubmitter,
    QueuedRequest,
    QueueMetrics,
    UserTier,
)

logger = logging.getLogger(__name__)


class HybridPrioritizer:
    """Default priority calculation using hybrid scoring.

    Score formula:
    - User tier: VIP=100, PREMIUM=50, NORMAL=0
    - Task type: Skills=50, Agents=0
    - Age bonus up to 30 (prevents starvation)

    Higher score = higher priority (processed first).
    """

    # User tier bonuses
    TIER_BONUSES = {
        UserTier.VIP: 100.0,
        UserTier.PREMIUM: 50.0,
        UserTier.NORMAL: 0.0,
    }

    def calculate_score(self, request: QueuedRequest) -> float:
        """Calculate priority score for a request."""
        score = 0.0

        # User tier bonus
        score += self.TIER_BONUSES.get(request.user_tier, 0.0)

        # Task type bonus (skills are faster, prioritize them)
        if request.routing_type == "skill":
            score += 50.0

        # Age bonus (prevents starvation)
        now = datetime.now(timezone.utc)
        queued_at = request.queued_at
        if queued_at.tzinfo is None:
            queued_at = queued_at.replace(tzinfo=timezone.utc)

        age_seconds = (now - queued_at).total_seconds()
        age_bonus = min(age_seconds / 60.0, 30.0)  # Max 30 points
        score += age_bonus

        return score


@dataclass
class QueueEntry:
    """Internal entry in the priority heap.

    Uses negative score for min-heap (Python heapq) to get max-priority first.
    Includes counter for stable sorting when scores are equal.
    """

    neg_score: float
    counter: int
    request: QueuedRequest

    def __lt__(self, other: "QueueEntry") -> bool:
        """Compare for heap ordering (lower neg_score = higher priority)."""
        if self.neg_score != other.neg_score:
            return self.neg_score < other.neg_score
        return self.counter < other.counter  # FIFO for same priority


@dataclass
class ResultHolder:
    """Holds execution result and completion future."""

    result: Optional["ExecutionResult"] = None
    error: Optional[str] = None
    future: asyncio.Future = field(default_factory=asyncio.Future)


class RequestQueue:
    """Centralized priority queue for all WebSocket requests.

    Implements IRequestSubmitter, IQueueInternal, and IQueueMonitor
    for Interface Segregation - different consumers see different methods.

    Thread-safe via asyncio.Lock and Condition for blocking dequeue.
    """

    def __init__(
        self,
        prioritizer: Optional[IPrioritizer] = None,
    ):
        """Initialize the request queue.

        Args:
            prioritizer: Priority calculation strategy. Defaults to HybridPrioritizer.
        """
        self._prioritizer = prioritizer or HybridPrioritizer()

        # Priority heap (min-heap with negated scores)
        self._heap: List[QueueEntry] = []
        self._counter = 0  # For stable sorting

        # Request tracking
        self._queued: Dict[str, QueueEntry] = {}  # request_id -> entry
        self._in_flight: Dict[str, QueuedRequest] = {}  # request_id -> request
        self._results: Dict[str, ResultHolder] = {}  # request_id -> result holder

        # Synchronization
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
        self._shutdown = False

        # Metrics
        self._total_enqueued = 0
        self._total_completed = 0
        self._total_failed = 0
        self._total_timeouts = 0
        self._total_cancelled = 0
        self._total_retries = 0
        self._wait_times: List[float] = []  # Last N wait times in ms
        self._process_times: List[float] = []  # Last N process times in ms
        self._max_metrics_samples = 100

    # =========================================================================
    # IRequestSubmitter interface
    # =========================================================================

    async def submit(self, request: QueuedRequest) -> str:
        """Submit a request to the queue.

        Args:
            request: The request to queue.

        Returns:
            The request_id for tracking.
        """
        async with self._lock:
            # Calculate priority score
            score = self._prioritizer.calculate_score(request)

            # Create heap entry (negate score for min-heap)
            entry = QueueEntry(
                neg_score=-score,
                counter=self._counter,
                request=request,
            )
            self._counter += 1

            # Add to heap and tracking dict
            heapq.heappush(self._heap, entry)
            self._queued[request.request_id] = entry

            # Create result holder with future
            self._results[request.request_id] = ResultHolder()

            # Update metrics
            self._total_enqueued += 1

            logger.debug(
                f"Queued request {request.request_id} "
                f"(score={score:.1f}, depth={len(self._heap)})"
            )

            # Signal waiting workers
            self._not_empty.notify()

        return request.request_id

    async def wait_result(
        self,
        request_id: str,
        timeout: float,
    ) -> "ExecutionResult":
        """Wait for a request to complete.

        Args:
            request_id: The request to wait for.
            timeout: Maximum seconds to wait.

        Returns:
            The execution result.

        Raises:
            TimeoutError: If the wait times out.
            KeyError: If request_id is not found.
            RuntimeError: If the request failed with an error.
        """
        # Get the result holder (created during submit)
        async with self._lock:
            if request_id not in self._results:
                raise KeyError(f"Request {request_id} not found")
            holder = self._results[request_id]

        # Wait for completion
        try:
            await asyncio.wait_for(holder.future, timeout=timeout)
        except asyncio.TimeoutError:
            self._total_timeouts += 1
            raise TimeoutError(f"Request {request_id} timed out after {timeout}s")

        # Return result or raise error
        if holder.error:
            raise RuntimeError(holder.error)

        return holder.result

    async def cancel(self, request_id: str) -> bool:
        """Cancel a queued or in-flight request.

        Args:
            request_id: The request to cancel.

        Returns:
            True if cancelled, False if not found or already complete.
        """
        async with self._lock:
            # Try to cancel from queue
            if request_id in self._queued:
                # Mark the entry as cancelled (will be skipped during dequeue)
                # We don't remove from heap (expensive), just from tracking
                del self._queued[request_id]

                # Complete the future with cancellation
                if request_id in self._results:
                    holder = self._results[request_id]
                    holder.error = "Cancelled"
                    if not holder.future.done():
                        holder.future.set_result(None)

                self._total_cancelled += 1
                logger.info(f"Cancelled queued request {request_id}")
                return True

            # Check if in-flight (cancellation handled by worker via token)
            if request_id in self._in_flight:
                # The worker will check the cancellation token
                logger.info(f"Request {request_id} is in-flight, worker will handle")
                return True

            return False

    def get_position(self, request_id: str) -> Optional[int]:
        """Get queue position for a request.

        Note: This is O(n) - use sparingly.
        """
        if request_id not in self._queued:
            return None

        # Count entries with higher priority (lower neg_score)
        target_entry = self._queued[request_id]
        position = 0
        for entry in self._heap:
            if entry.request.request_id in self._queued:  # Skip cancelled
                if entry.neg_score < target_entry.neg_score:
                    position += 1
                elif (
                    entry.neg_score == target_entry.neg_score
                    and entry.counter < target_entry.counter
                ):
                    position += 1

        return position

    # =========================================================================
    # IQueueInternal interface
    # =========================================================================

    async def dequeue(self) -> Optional[QueuedRequest]:
        """Get the highest priority request from the queue.

        Blocks if the queue is empty until a request is available.

        Returns:
            The next request to process, or None if shutdown.
        """
        async with self._not_empty:
            while True:
                if self._shutdown:
                    return None

                # Skip cancelled entries
                while self._heap:
                    entry = self._heap[0]
                    if entry.request.request_id in self._queued:
                        break  # Found valid entry
                    heapq.heappop(self._heap)  # Remove stale entry

                if self._heap:
                    # Pop the highest priority entry
                    entry = heapq.heappop(self._heap)
                    request = entry.request

                    # Move from queued to in-flight
                    del self._queued[request.request_id]
                    self._in_flight[request.request_id] = request
                    request.started_at = datetime.now(timezone.utc)

                    # Track wait time
                    wait_ms = (
                        request.started_at - request.queued_at
                    ).total_seconds() * 1000
                    self._wait_times.append(wait_ms)
                    if len(self._wait_times) > self._max_metrics_samples:
                        self._wait_times.pop(0)

                    logger.debug(
                        f"Dequeued request {request.request_id} "
                        f"(waited {wait_ms:.0f}ms)"
                    )
                    return request

                # Wait for new requests
                await self._not_empty.wait()

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
        async with self._lock:
            if request_id not in self._in_flight:
                logger.warning(f"mark_complete called for unknown request {request_id}")
                return

            request = self._in_flight.pop(request_id)

            # Track process time
            if request.started_at:
                process_ms = (
                    datetime.now(timezone.utc) - request.started_at
                ).total_seconds() * 1000
                self._process_times.append(process_ms)
                if len(self._process_times) > self._max_metrics_samples:
                    self._process_times.pop(0)

            # Set result and signal waiter
            if request_id in self._results:
                holder = self._results[request_id]
                holder.result = result
                if not holder.future.done():
                    holder.future.set_result(result)

            self._total_completed += 1
            logger.debug(f"Completed request {request_id}")

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
        async with self._lock:
            # Remove from in-flight if present
            if request_id in self._in_flight:
                del self._in_flight[request_id]

            # Set error and signal waiter
            if request_id in self._results:
                holder = self._results[request_id]
                holder.error = error
                if not holder.future.done():
                    holder.future.set_result(None)

            self._total_failed += 1
            logger.warning(f"Failed request {request_id}: {error}")

    async def requeue_for_retry(self, request_id: str) -> bool:
        """Move request from in_flight back to queue for retry.

        Args:
            request_id: The request to requeue.

        Returns:
            True if requeued, False if not found.
        """
        async with self._lock:
            if request_id not in self._in_flight:
                logger.warning(f"requeue_for_retry: request {request_id} not in flight")
                return False

            request = self._in_flight.pop(request_id)

            # Update retry tracking
            if request.first_attempt_at is None:
                request.first_attempt_at = request.queued_at
            request.retry_count += 1
            request.queued_at = datetime.now(timezone.utc)  # Reset for priority age bonus
            request.started_at = None

            # Re-add to queue with updated priority
            score = self._prioritizer.calculate_score(request)
            entry = QueueEntry(
                neg_score=-score,
                counter=self._counter,
                request=request,
            )
            self._counter += 1

            heapq.heappush(self._heap, entry)
            self._queued[request.request_id] = entry

            # Update metrics
            self._total_retries += 1

            logger.info(
                f"Requeued request {request_id} for retry #{request.retry_count}"
            )

            # Signal waiting workers
            self._not_empty.notify()

            return True

    def get_in_flight_snapshot(self) -> Dict[str, QueuedRequest]:
        """Get a snapshot of all in-flight requests.

        Returns:
            Copy of in-flight requests dict.
        """
        # Note: This is not async-locked, intended for monitoring only
        return dict(self._in_flight)

    # =========================================================================
    # IQueueMonitor interface
    # =========================================================================

    def get_metrics(self) -> QueueMetrics:
        """Get current queue metrics."""
        return QueueMetrics(
            queue_depth=self.get_queue_depth(),
            in_flight_count=self.get_in_flight_count(),
            total_enqueued=self._total_enqueued,
            total_completed=self._total_completed,
            total_failed=self._total_failed,
            total_timeouts=self._total_timeouts,
            total_cancelled=self._total_cancelled,
            total_retries=self._total_retries,
            avg_wait_time_ms=self._avg(self._wait_times),
            avg_process_time_ms=self._avg(self._process_times),
        )

    def get_queue_depth(self) -> int:
        """Get number of requests waiting in queue."""
        return len(self._queued)

    def get_in_flight_count(self) -> int:
        """Get number of requests currently being processed."""
        return len(self._in_flight)

    # =========================================================================
    # Internal methods
    # =========================================================================

    def _avg(self, values: List[float]) -> float:
        """Calculate average of a list."""
        if not values:
            return 0.0
        return sum(values) / len(values)

    async def shutdown(self) -> None:
        """Signal workers to stop and clean up."""
        async with self._lock:
            self._shutdown = True
            self._not_empty.notify_all()

        logger.info("Queue shutdown initiated")


# Import ExecutionResult for type hints (avoid circular import)
from .executor import ExecutionResult  # noqa: E402
