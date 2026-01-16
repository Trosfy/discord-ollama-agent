"""Circuit breaker implementation for resilience patterns.

Provides:
- CircuitBreakerConfig: Configuration dataclass
- CircuitBreaker: Standard implementation with state machine
"""
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque, Optional, Tuple

from .interfaces.circuit_breaker import (
    CircuitBreakerMetrics,
    CircuitState,
    ICircuitBreaker,
)

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 10
    """Consecutive failures before transitioning to OPEN."""

    success_threshold: int = 5
    """Successes in HALF_OPEN before transitioning to CLOSED."""

    open_timeout_seconds: float = 60.0
    """Time in OPEN state before transitioning to HALF_OPEN."""

    half_open_max_requests: int = 3
    """Max requests to test in HALF_OPEN before blocking."""

    failure_rate_threshold: float = 0.5
    """Rate-based trigger (0.5 = 50% failure rate triggers OPEN)."""

    sample_window_seconds: float = 60.0
    """Window for rate calculation."""


class CircuitBreaker(ICircuitBreaker):
    """Standard circuit breaker implementation.

    Implements the three-state circuit breaker pattern:
    - CLOSED: Normal operation, all requests allowed
    - OPEN: Failing fast, all requests rejected
    - HALF_OPEN: Testing recovery, limited requests allowed

    Thread-safe with internal locking.
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        on_state_change: Optional[Callable[[CircuitState, CircuitState], None]] = None,
    ):
        """Initialize circuit breaker.

        Args:
            name: Identifier for logging and metrics.
            config: Configuration, uses defaults if not provided.
            on_state_change: Callback invoked on state transitions.
        """
        self._name = name
        self._config = config or CircuitBreakerConfig()
        self._on_state_change = on_state_change

        # State
        self._state = CircuitState.CLOSED
        self._state_changed_at = time.time()

        # Counters
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._half_open_attempts = 0

        # Sliding window for rate calculation: (timestamp, success)
        self._recent_results: Deque[Tuple[float, bool]] = deque()

        # Totals
        self._total_failures = 0
        self._total_successes = 0
        self._open_count = 0
        self._last_failure_time: Optional[float] = None

        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._state

    @property
    def name(self) -> str:
        """Get circuit breaker name."""
        return self._name

    def is_allowed(self) -> bool:
        """Check if request should proceed.

        Returns:
            True if request can proceed.
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if timeout elapsed
                if time.time() - self._state_changed_at >= self._config.open_timeout_seconds:
                    self._transition_to(CircuitState.HALF_OPEN)
                    self._half_open_attempts = 0
                    return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                # Allow limited requests through
                if self._half_open_attempts < self._config.half_open_max_requests:
                    self._half_open_attempts += 1
                    return True
                return False

        return False

    def record_success(self) -> None:
        """Record successful execution."""
        with self._lock:
            now = time.time()
            self._recent_results.append((now, True))
            self._prune_old_results(now)

            self._consecutive_failures = 0
            self._consecutive_successes += 1
            self._total_successes += 1

            if self._state == CircuitState.HALF_OPEN:
                if self._consecutive_successes >= self._config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

    def record_failure(self, error: str) -> None:
        """Record failed execution.

        Args:
            error: Error description for logging.
        """
        with self._lock:
            now = time.time()
            self._recent_results.append((now, False))
            self._prune_old_results(now)

            self._consecutive_failures += 1
            self._consecutive_successes = 0
            self._total_failures += 1
            self._last_failure_time = now

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN → back to OPEN
                logger.warning(
                    f"Circuit breaker '{self._name}' failure in HALF_OPEN: {error}"
                )
                self._transition_to(CircuitState.OPEN)

            elif self._state == CircuitState.CLOSED:
                # Check thresholds
                should_open = (
                    self._consecutive_failures >= self._config.failure_threshold
                    or self._get_failure_rate() >= self._config.failure_rate_threshold
                )
                if should_open:
                    logger.warning(
                        f"Circuit breaker '{self._name}' opening: "
                        f"consecutive_failures={self._consecutive_failures}, "
                        f"failure_rate={self._get_failure_rate():.2f}, "
                        f"last_error={error}"
                    )
                    self._transition_to(CircuitState.OPEN)

    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get current metrics snapshot."""
        with self._lock:
            return CircuitBreakerMetrics(
                state=self._state,
                consecutive_failures=self._consecutive_failures,
                consecutive_successes=self._consecutive_successes,
                total_failures=self._total_failures,
                total_successes=self._total_successes,
                failure_rate=self._get_failure_rate(),
                last_failure_time=self._last_failure_time,
                last_state_change=self._state_changed_at,
                open_count=self._open_count,
                half_open_attempts=self._half_open_attempts,
            )

    def reset(self) -> None:
        """Force reset to CLOSED state."""
        with self._lock:
            old_state = self._state
            self._state = CircuitState.CLOSED
            self._state_changed_at = time.time()
            self._consecutive_failures = 0
            self._consecutive_successes = 0
            self._half_open_attempts = 0
            logger.info(
                f"Circuit breaker '{self._name}' reset: {old_state.value} → CLOSED"
            )

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to new state with callback.

        Must be called while holding the lock.

        Args:
            new_state: Target state.
        """
        old_state = self._state
        self._state = new_state
        self._state_changed_at = time.time()

        if new_state == CircuitState.OPEN:
            self._open_count += 1

        if new_state == CircuitState.CLOSED:
            # Reset counters on recovery
            self._consecutive_failures = 0

        logger.warning(
            f"Circuit breaker '{self._name}': {old_state.value} → {new_state.value}"
        )

        if self._on_state_change:
            # Call outside lock to prevent deadlocks
            # Note: This is still inside the lock - for true async safety,
            # consider using a queue for callbacks
            try:
                self._on_state_change(old_state, new_state)
            except Exception as e:
                logger.error(
                    f"Circuit breaker '{self._name}' state change callback failed: {e}"
                )

    def _prune_old_results(self, now: float) -> None:
        """Remove results outside sample window.

        Must be called while holding the lock.

        Args:
            now: Current timestamp.
        """
        cutoff = now - self._config.sample_window_seconds
        while self._recent_results and self._recent_results[0][0] < cutoff:
            self._recent_results.popleft()

    def _get_failure_rate(self) -> float:
        """Calculate failure rate in current window.

        Must be called while holding the lock.

        Returns:
            Failure rate between 0.0 and 1.0.
        """
        if not self._recent_results:
            return 0.0
        failures = sum(1 for _, success in self._recent_results if not success)
        return failures / len(self._recent_results)
