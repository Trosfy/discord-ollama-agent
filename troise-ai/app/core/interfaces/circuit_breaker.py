"""Circuit breaker interfaces for resilience patterns.

Provides:
- CircuitState enum for state machine
- CircuitBreakerMetrics for observability
- ICircuitBreaker protocol for pluggable implementations
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol


class CircuitState(Enum):
    """Circuit breaker states.

    State transitions:
        CLOSED → OPEN (on failure threshold exceeded)
        OPEN → HALF_OPEN (after timeout)
        HALF_OPEN → CLOSED (on success threshold reached)
        HALF_OPEN → OPEN (on any failure)
    """

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing fast, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker observability."""

    state: CircuitState
    consecutive_failures: int
    consecutive_successes: int
    total_failures: int
    total_successes: int
    failure_rate: float  # failures / (failures + successes) in window
    last_failure_time: Optional[float]
    last_state_change: float
    open_count: int  # Times breaker opened
    half_open_attempts: int  # Requests allowed through in HALF_OPEN


class ICircuitBreaker(Protocol):
    """Pluggable circuit breaker interface.

    Implementations track failures and control request flow
    to prevent cascade failures.
    """

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        ...

    def is_allowed(self) -> bool:
        """Check if request should be allowed through.

        Returns:
            True if request can proceed, False if circuit is open.
        """
        ...

    def record_success(self) -> None:
        """Record successful execution.

        May transition HALF_OPEN → CLOSED if success threshold reached.
        """
        ...

    def record_failure(self, error: str) -> None:
        """Record failed execution.

        May transition CLOSED → OPEN if failure threshold exceeded,
        or HALF_OPEN → OPEN on any failure.

        Args:
            error: Error description for logging.
        """
        ...

    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get current metrics snapshot.

        Returns:
            CircuitBreakerMetrics with current state and counters.
        """
        ...

    def reset(self) -> None:
        """Force reset to CLOSED state.

        Use for administrative override or testing.
        """
        ...
