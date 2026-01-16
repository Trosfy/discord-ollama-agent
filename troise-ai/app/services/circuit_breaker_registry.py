"""Circuit breaker registry for managing system-wide circuit breakers.

Provides centralized circuit breaker management with ProfileManager integration
for automatic profile degradation on sustained failures.
"""
import logging
from typing import Dict, Optional, Tuple

from ..core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from ..core.config import Config, CircuitBreakerYAMLConfig
from ..core.interfaces.circuit_breaker import CircuitBreakerMetrics, CircuitState

logger = logging.getLogger(__name__)


class CircuitBreakerRegistry:
    """Central registry for circuit breakers.

    Manages a single queue-level circuit breaker (no per-type breakers since
    agents can invoke skills during execution, making type-based isolation
    unreliable).

    Integrates with ProfileManager:
    - On circuit OPEN: signals failure to ProfileManager for degradation
    - On successes: signals success to ProfileManager for recovery tracking
    """

    def __init__(
        self,
        config: Config,
        profile_manager: Optional["ProfileManager"] = None,
    ):
        """Initialize the circuit breaker registry.

        Args:
            config: Application configuration.
            profile_manager: Optional ProfileManager for integration.
                            If None, profile degradation is disabled.
        """
        self._config = config
        self._profile_manager = profile_manager
        self._breakers: Dict[str, CircuitBreaker] = {}

        self._create_queue_breaker()

    def _create_queue_breaker(self) -> None:
        """Create the queue-level circuit breaker."""
        yaml_config = self._config.circuit_breaker

        cb_config = CircuitBreakerConfig(
            failure_threshold=yaml_config.failure_threshold,
            success_threshold=yaml_config.success_threshold,
            open_timeout_seconds=yaml_config.open_timeout_seconds,
            half_open_max_requests=yaml_config.half_open_max_requests,
            failure_rate_threshold=yaml_config.failure_rate_threshold,
            sample_window_seconds=yaml_config.sample_window_seconds,
        )

        self._breakers["queue"] = CircuitBreaker(
            name="queue",
            config=cb_config,
            on_state_change=self._on_queue_state_change,
        )

        logger.info(
            f"Created queue circuit breaker: "
            f"failure_threshold={cb_config.failure_threshold}, "
            f"open_timeout={cb_config.open_timeout_seconds}s"
        )

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name.

        Args:
            name: Circuit breaker name (e.g., "queue").

        Returns:
            The circuit breaker, or None if not found.
        """
        return self._breakers.get(name)

    def is_allowed(self) -> Tuple[bool, Optional[str]]:
        """Check if requests are allowed through.

        Returns:
            Tuple of (allowed, rejection_reason).
            If allowed is False, rejection_reason explains why.
        """
        queue_breaker = self._breakers.get("queue")
        if queue_breaker and not queue_breaker.is_allowed():
            return False, "Circuit breaker OPEN - service degraded"
        return True, None

    def record_success(self) -> None:
        """Record a successful execution.

        Updates circuit breaker metrics and signals ProfileManager
        for recovery tracking.
        """
        if breaker := self._breakers.get("queue"):
            breaker.record_success()

        # Signal ProfileManager for recovery tracking
        # This allows ProfileManager to accumulate consecutive_successes
        # which enables should_probe_recovery() to return True
        if self._profile_manager:
            self._profile_manager.record_load_success("queue_execution")

    def record_failure(self, error: str) -> None:
        """Record a failed execution.

        Updates circuit breaker metrics. May trigger circuit open
        if thresholds are exceeded.

        Args:
            error: Error description for logging.
        """
        if breaker := self._breakers.get("queue"):
            breaker.record_failure(error)

    def _on_queue_state_change(
        self, old_state: CircuitState, new_state: CircuitState
    ) -> None:
        """Handle queue circuit breaker state changes.

        Integrates with ProfileManager for profile degradation and recovery.

        Args:
            old_state: Previous circuit state.
            new_state: New circuit state.
        """
        if new_state == CircuitState.OPEN:
            # Trigger profile fallback
            logger.warning(
                "Queue circuit breaker OPEN - triggering profile degradation"
            )
            if self._profile_manager:
                self._profile_manager.record_load_failure(
                    "queue_circuit_breaker",
                    "Queue circuit breaker opened due to high failure rate",
                )

        elif old_state == CircuitState.HALF_OPEN and new_state == CircuitState.CLOSED:
            # Circuit breaker recovered
            # ProfileManager will probe recovery via VRAMOrchestrator.health_check_loop()
            # after accumulating RECOVERY_SUCCESS_THRESHOLD consecutive successes
            logger.info(
                "Queue circuit breaker recovered - profile recovery probing enabled"
            )

    def get_all_metrics(self) -> Dict[str, CircuitBreakerMetrics]:
        """Get metrics for all circuit breakers.

        Returns:
            Dict mapping breaker names to their metrics.
        """
        return {name: cb.get_metrics() for name, cb in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset all circuit breakers to CLOSED state.

        Use for administrative override or testing.
        """
        for name, breaker in self._breakers.items():
            breaker.reset()
            logger.info(f"Reset circuit breaker: {name}")
