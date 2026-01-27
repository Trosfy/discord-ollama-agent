"""Visibility monitor for stuck request detection.

Monitors in-flight requests and handles:
- Stuck request detection via visibility timeout
- Automatic retry for retriable requests
- Circuit breaker failure signaling
"""
import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..core.config import Config
    from ..core.interfaces.queue import IQueueInternal
    from .circuit_breaker_registry import CircuitBreakerRegistry

logger = logging.getLogger(__name__)


class VisibilityMonitor:
    """Monitors in-flight requests for stuck/timeout conditions.

    Periodically checks all in-flight requests and:
    - Detects requests exceeding visibility timeout
    - Requeues retriable requests for retry
    - Marks exhausted requests as failed
    - Signals circuit breaker on timeout failures
    """

    def __init__(
        self,
        queue: "IQueueInternal",
        config: "Config",
        circuit_registry: Optional["CircuitBreakerRegistry"] = None,
    ):
        """Initialize visibility monitor.

        Args:
            queue: Queue to monitor (IQueueInternal interface).
            config: Configuration with timeout settings.
            circuit_registry: Optional circuit breaker registry for failure signaling.
        """
        self._queue = queue
        self._config = config
        self._circuit_registry = circuit_registry
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the monitoring loop."""
        if self._running:
            logger.warning("Visibility monitor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(
            f"Visibility monitor started "
            f"(check_interval={self._config.queue.visibility_check_interval_seconds}s, "
            f"timeout={self._config.queue.visibility_timeout_seconds}s)"
        )

    async def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("Visibility monitor stopped")

    async def _monitor_loop(self) -> None:
        """Periodic check for stuck requests."""
        check_interval = self._config.queue.visibility_check_interval_seconds
        visibility_timeout = self._config.queue.visibility_timeout_seconds

        while self._running:
            try:
                await asyncio.sleep(check_interval)
                await self._check_stuck_requests(visibility_timeout)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Visibility monitor error: {e}", exc_info=True)

    async def _check_stuck_requests(self, default_timeout: float) -> None:
        """Find and handle requests exceeding visibility timeout.

        Uses classification-aware timeouts: IMAGE requests get longer timeouts
        to avoid premature requeuing during diffusion model inference.

        Args:
            default_timeout: Default visibility timeout in seconds.
        """
        now = datetime.now(timezone.utc)

        # Get snapshot of in-flight requests
        in_flight = self._queue.get_in_flight_snapshot()

        if not in_flight:
            return

        stuck_count = 0
        for request_id, request in in_flight.items():
            if request.started_at is None:
                continue

            # Handle timezone-naive datetime
            started_at = request.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)

            elapsed = (now - started_at).total_seconds()

            # Get classification-aware timeout
            classification = getattr(request.routing_result, 'classification', None) \
                if request.routing_result else None
            timeout = self._config.queue.get_visibility_timeout_for_classification(classification)

            if elapsed > timeout:
                stuck_count += 1
                logger.warning(
                    f"Request {request_id} stuck for {elapsed:.0f}s "
                    f"(visibility timeout: {timeout}s, "
                    f"retry_count: {request.retry_count})"
                )

                # Check retry eligibility
                max_retries = self._config.queue.max_retries
                if request.retry_count < max_retries:
                    requeued = await self._queue.requeue_for_retry(request_id)
                    if requeued:
                        logger.info(
                            f"Request {request_id} requeued "
                            f"(retry {request.retry_count + 1}/{max_retries})"
                        )
                    else:
                        # Request was completed/failed between snapshot and requeue
                        logger.debug(
                            f"Request {request_id} no longer in flight, skip requeue"
                        )
                else:
                    # Max retries exceeded
                    error_msg = (
                        f"Exceeded visibility timeout ({timeout}s) "
                        f"after {request.retry_count} retries"
                    )
                    await self._queue.mark_failed(request_id, error_msg)

                    # Signal circuit breaker
                    if self._circuit_registry:
                        self._circuit_registry.record_failure(
                            f"Visibility timeout: {request_id}"
                        )

                    logger.error(
                        f"Request {request_id} failed permanently: {error_msg}"
                    )

        if stuck_count > 0:
            logger.warning(f"Visibility check found {stuck_count} stuck request(s)")
