"""Queue management service for TROISE AI.

Provides WorkerPool and QueueManager for processing queued requests.
Follows Single Responsibility Principle:
- QueueWorker: Processes individual requests
- WorkerPool: Manages worker lifecycle
- QueueManager: Orchestrates queue and pool
"""
import asyncio
import logging
from typing import List, Optional, TYPE_CHECKING

from ..core.config import Config, QueueConfig
from ..core.interfaces.queue import (
    IQueueInternal,
    IQueueMonitor,
    IRequestSubmitter,
    QueuedRequest,
    QueueMetrics,
)
from ..core.interfaces.services import IExecutor

if TYPE_CHECKING:
    from ..core.queue import RequestQueue
    from .circuit_breaker_registry import CircuitBreakerRegistry

logger = logging.getLogger(__name__)


class QueueWorker:
    """Worker that processes requests from the queue.

    Each worker runs in an asyncio task, polling the queue for work.
    Includes timeout watchdog to prevent stuck requests.
    Integrates with circuit breaker for failure tracking.
    """

    def __init__(
        self,
        worker_id: int,
        queue: IQueueInternal,
        executor: IExecutor,
        config: QueueConfig,
        circuit_registry: Optional["CircuitBreakerRegistry"] = None,
    ):
        """Initialize the worker.

        Args:
            worker_id: Unique identifier for this worker.
            queue: Queue interface for dequeuing and completing requests.
            executor: Executor for running skills/agents.
            config: Queue configuration with timeouts.
            circuit_registry: Optional circuit breaker registry for failure tracking.
        """
        self._id = worker_id
        self._queue = queue
        self._executor = executor
        self._config = config
        self._circuit_registry = circuit_registry
        self._running = False
        self._current_request: Optional[str] = None

    @property
    def worker_id(self) -> int:
        """Get worker ID."""
        return self._id

    @property
    def is_busy(self) -> bool:
        """Check if worker is processing a request."""
        return self._current_request is not None

    @property
    def current_request_id(self) -> Optional[str]:
        """Get current request ID if processing."""
        return self._current_request

    async def run(self) -> None:
        """Run the worker loop.

        Continuously dequeues and processes requests until stopped.
        """
        self._running = True
        logger.info(f"Worker {self._id} started")

        while self._running:
            try:
                # Dequeue blocks until a request is available or shutdown
                request = await self._queue.dequeue()

                if request is None:
                    # Shutdown signal
                    break

                await self._process(request)

            except Exception as e:
                logger.error(f"Worker {self._id} error: {e}", exc_info=True)
                # Continue processing - don't let one error stop the worker
                await asyncio.sleep(0.1)

        logger.info(f"Worker {self._id} stopped")

    async def _process(self, request: QueuedRequest) -> None:
        """Process a single request with timeout watchdog.

        Integrates with circuit breaker:
        - Checks if requests are allowed before execution
        - Records success/failure for circuit breaker state tracking

        Args:
            request: The request to process.
        """
        self._current_request = request.request_id

        try:
            # ========== CIRCUIT BREAKER CHECK ==========
            if self._circuit_registry:
                allowed, rejection_reason = self._circuit_registry.is_allowed()
                if not allowed:
                    logger.warning(
                        f"Worker {self._id} request {request.request_id} "
                        f"rejected: {rejection_reason}"
                    )
                    await self._queue.mark_failed(request.request_id, rejection_reason)
                    return

            # ========== CANCELLATION CHECK ==========
            if hasattr(request.context, 'cancellation_token'):
                if request.context.cancellation_token.is_set():
                    await self._queue.mark_failed(
                        request.request_id,
                        "Cancelled before execution"
                    )
                    return

            # Get timeout for this request type (classification-aware)
            classification = getattr(request.routing_result, 'classification', None) \
                if request.routing_result else None
            timeout = self._config.get_timeout_for_type(request.routing_type, classification)
            # Add buffer for cleanup
            timeout_with_buffer = timeout + self._config.timeout_buffer_seconds

            logger.debug(
                f"Worker {self._id} processing {request.request_id} "
                f"(type={request.routing_type}, classification={classification}, timeout={timeout}s)"
            )

            # ========== EXECUTION ==========
            result = await asyncio.wait_for(
                self._executor.execute(
                    request.routing_result,
                    request.user_input,
                    request.context,
                ),
                timeout=timeout_with_buffer,
            )

            # ========== SUCCESS ==========
            await self._queue.mark_complete(request.request_id, result)
            if self._circuit_registry:
                self._circuit_registry.record_success()

        except asyncio.TimeoutError:
            error_msg = f"Execution timeout after {timeout_with_buffer}s"
            logger.error(f"Worker {self._id} timeout for {request.request_id}")
            await self._queue.mark_failed(request.request_id, error_msg)
            if self._circuit_registry:
                self._circuit_registry.record_failure(error_msg)

        except asyncio.CancelledError:
            logger.info(f"Worker {self._id} cancelled for {request.request_id}")
            await self._queue.mark_failed(request.request_id, "Cancelled")
            # Don't record cancellation as circuit breaker failure
            raise  # Re-raise to stop worker if shutdown

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"Worker {self._id} error for {request.request_id}: {e}",
                exc_info=True,
            )
            await self._queue.mark_failed(request.request_id, error_msg)
            if self._circuit_registry:
                self._circuit_registry.record_failure(error_msg)

        finally:
            self._current_request = None

    async def stop(self) -> None:
        """Signal the worker to stop."""
        self._running = False
        logger.debug(f"Worker {self._id} stop requested")


class WorkerPool:
    """Manages a pool of queue workers.

    Handles worker lifecycle: creation, startup, and graceful shutdown.
    Single Responsibility: only manages workers, not queue logic.
    """

    def __init__(
        self,
        worker_count: int,
        queue: IQueueInternal,
        executor: IExecutor,
        config: QueueConfig,
        circuit_registry: Optional["CircuitBreakerRegistry"] = None,
    ):
        """Initialize the worker pool.

        Args:
            worker_count: Number of workers to create.
            queue: Queue interface for workers.
            executor: Executor for workers.
            config: Queue configuration.
            circuit_registry: Optional circuit breaker registry for workers.
        """
        self._count = worker_count
        self._queue = queue
        self._executor = executor
        self._config = config
        self._circuit_registry = circuit_registry
        self._workers: List[QueueWorker] = []
        self._worker_tasks: List[asyncio.Task] = []

    @property
    def total_workers(self) -> int:
        """Get total worker count."""
        return len(self._workers)

    @property
    def busy_workers(self) -> int:
        """Get count of workers currently processing."""
        return sum(1 for w in self._workers if w.is_busy)

    @property
    def idle_workers(self) -> int:
        """Get count of idle workers."""
        return self.total_workers - self.busy_workers

    def get_worker_status(self) -> List[dict]:
        """Get status of all workers."""
        return [
            {
                "id": w.worker_id,
                "busy": w.is_busy,
                "current_request": w.current_request_id,
            }
            for w in self._workers
        ]

    async def start(self) -> None:
        """Start all workers."""
        for i in range(self._count):
            worker = QueueWorker(
                worker_id=i,
                queue=self._queue,
                executor=self._executor,
                config=self._config,
                circuit_registry=self._circuit_registry,
            )
            self._workers.append(worker)

            task = asyncio.create_task(
                worker.run(),
                name=f"queue-worker-{i}",
            )
            self._worker_tasks.append(task)

        logger.info(f"Started {self._count} queue workers")

    async def stop(self, timeout: float = 30.0) -> None:
        """Gracefully shutdown all workers.

        Args:
            timeout: Maximum seconds to wait for workers to finish.
        """
        logger.info("Stopping worker pool...")

        # Signal all workers to stop
        for worker in self._workers:
            await worker.stop()

        # Wait for tasks with timeout
        if self._worker_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._worker_tasks, return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"Worker shutdown timed out after {timeout}s, "
                    "cancelling remaining tasks"
                )
                for task in self._worker_tasks:
                    if not task.done():
                        task.cancel()

        self._workers.clear()
        self._worker_tasks.clear()
        logger.info("Worker pool stopped")


class QueueManager:
    """Orchestrates the request queue and worker pool.

    Thin facade providing a clean API for:
    - Submitting requests
    - Waiting for results
    - Getting metrics

    Single Responsibility: Orchestration only, delegates to components.
    """

    def __init__(
        self,
        queue: "RequestQueue",
        executor: IExecutor,
        config: Config,
        circuit_registry: Optional["CircuitBreakerRegistry"] = None,
    ):
        """Initialize the queue manager.

        Args:
            queue: The request queue.
            executor: The executor for skills/agents.
            config: Application configuration.
            circuit_registry: Optional circuit breaker registry for failure tracking.
        """
        self._queue = queue
        self._executor = executor
        self._config = config
        self._circuit_registry = circuit_registry
        self._pool: Optional[WorkerPool] = None

    @property
    def queue(self) -> IRequestSubmitter:
        """Get the queue as IRequestSubmitter interface."""
        return self._queue

    @property
    def is_running(self) -> bool:
        """Check if the queue manager is running."""
        return self._pool is not None

    async def start(self) -> None:
        """Start the queue manager and worker pool."""
        if self._pool is not None:
            logger.warning("QueueManager already started")
            return

        # Create and start worker pool
        self._pool = WorkerPool(
            worker_count=self._config.queue.worker_count,
            queue=self._queue,  # As IQueueInternal
            executor=self._executor,
            config=self._config.queue,
            circuit_registry=self._circuit_registry,
        )
        await self._pool.start()

        logger.info(
            f"QueueManager started with {self._config.queue.worker_count} workers"
        )

    async def stop(self) -> None:
        """Stop the queue manager and workers."""
        if self._pool is None:
            return

        # Stop workers
        await self._pool.stop()

        # Signal queue shutdown
        await self._queue.shutdown()

        self._pool = None
        logger.info("QueueManager stopped")

    async def submit(self, request: QueuedRequest) -> str:
        """Submit a request to the queue.

        Args:
            request: The request to queue.

        Returns:
            The request_id for tracking.
        """
        return await self._queue.submit(request)

    async def wait_for_result(self, request_id: str, timeout: float = None):
        """Wait for a request to complete.

        Args:
            request_id: The request to wait for.
            timeout: Maximum seconds to wait. Uses config default if None.

        Returns:
            The execution result.

        Raises:
            TimeoutError: If the wait times out.
            RuntimeError: If the request failed.
        """
        if timeout is None:
            timeout = self._config.execution_timeout

        return await self._queue.wait_result(request_id, timeout)

    async def cancel(self, request_id: str) -> bool:
        """Cancel a request.

        Args:
            request_id: The request to cancel.

        Returns:
            True if cancelled.
        """
        return await self._queue.cancel(request_id)

    def get_position(self, request_id: str) -> Optional[int]:
        """Get queue position for a request."""
        return self._queue.get_position(request_id)

    def get_metrics(self) -> QueueMetrics:
        """Get queue metrics."""
        return self._queue.get_metrics()

    def get_queue_depth(self) -> int:
        """Get number of queued requests."""
        return self._queue.get_queue_depth()

    def get_in_flight_count(self) -> int:
        """Get number of in-flight requests."""
        return self._queue.get_in_flight_count()

    def get_worker_status(self) -> dict:
        """Get worker pool status."""
        if self._pool is None:
            return {"total": 0, "busy": 0, "idle": 0, "workers": []}

        return {
            "total": self._pool.total_workers,
            "busy": self._pool.busy_workers,
            "idle": self._pool.idle_workers,
            "workers": self._pool.get_worker_status(),
        }

    def get_status(self) -> dict:
        """Get full queue manager status."""
        metrics = self.get_metrics()
        workers = self.get_worker_status()

        return {
            "queue_depth": metrics.queue_depth,
            "in_flight": metrics.in_flight_count,
            "workers": workers,
            "metrics": {
                "total_enqueued": metrics.total_enqueued,
                "total_completed": metrics.total_completed,
                "total_failed": metrics.total_failed,
                "total_timeouts": metrics.total_timeouts,
                "total_cancelled": metrics.total_cancelled,
                "total_retries": metrics.total_retries,
                "avg_wait_time_ms": round(metrics.avg_wait_time_ms, 1),
                "avg_process_time_ms": round(metrics.avg_process_time_ms, 1),
            },
        }
