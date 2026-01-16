"""Tests for circuit breaker implementation."""
import time
import pytest

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.core.interfaces.circuit_breaker import CircuitState


class TestCircuitBreakerConfig:
    """Test CircuitBreakerConfig defaults."""

    def test_default_values(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()

        assert config.failure_threshold == 10
        assert config.success_threshold == 5
        assert config.open_timeout_seconds == 60.0
        assert config.half_open_max_requests == 3
        assert config.failure_rate_threshold == 0.5
        assert config.sample_window_seconds == 60.0

    def test_custom_values(self):
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=3,
            open_timeout_seconds=30.0,
            half_open_max_requests=2,
        )

        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.open_timeout_seconds == 30.0
        assert config.half_open_max_requests == 2


class TestCircuitBreakerState:
    """Test circuit breaker state transitions."""

    def test_initial_state_is_closed(self):
        """Test that circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_closed_allows_requests(self):
        """Test that CLOSED state allows requests."""
        cb = CircuitBreaker("test")
        assert cb.is_allowed() is True

    def test_success_in_closed_stays_closed(self):
        """Test that success in CLOSED state stays CLOSED."""
        cb = CircuitBreaker("test")
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_consecutive_failures_open_circuit(self):
        """Test that consecutive failures open the circuit."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config)

        # Record failures up to threshold
        for i in range(3):
            cb.record_failure(f"error {i}")

        assert cb.state == CircuitState.OPEN

    def test_open_rejects_requests(self):
        """Test that OPEN state rejects requests."""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", config)

        cb.record_failure("error")
        assert cb.state == CircuitState.OPEN
        assert cb.is_allowed() is False

    def test_open_transitions_to_half_open_after_timeout(self):
        """Test that OPEN transitions to HALF_OPEN after timeout."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            open_timeout_seconds=0.01,  # Very short timeout for testing
        )
        cb = CircuitBreaker("test", config)

        # Open the circuit
        cb.record_failure("error")
        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(0.02)

        # Request should trigger transition
        assert cb.is_allowed() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_allows_limited_requests(self):
        """Test that HALF_OPEN allows limited requests."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            open_timeout_seconds=0.01,
            half_open_max_requests=2,
        )
        cb = CircuitBreaker("test", config)

        # Open and transition to HALF_OPEN
        cb.record_failure("error")
        time.sleep(0.02)
        # First is_allowed() triggers transition to HALF_OPEN and counts as first probe
        assert cb.is_allowed() is True  # Transition + first probe
        assert cb.is_allowed() is True  # Second probe (half_open_attempts=1)
        assert cb.is_allowed() is True  # Third probe (half_open_attempts=2)
        assert cb.is_allowed() is False  # Fourth blocked (half_open_attempts >= max)

    def test_success_in_half_open_closes_circuit(self):
        """Test that successes in HALF_OPEN close the circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=2,
            open_timeout_seconds=0.01,
        )
        cb = CircuitBreaker("test", config)

        # Open and transition to HALF_OPEN
        cb.record_failure("error")
        time.sleep(0.02)
        cb.is_allowed()  # Trigger transition

        # Record successes
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_failure_in_half_open_reopens_circuit(self):
        """Test that failure in HALF_OPEN reopens the circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            open_timeout_seconds=0.01,
        )
        cb = CircuitBreaker("test", config)

        # Open and transition to HALF_OPEN
        cb.record_failure("error")
        time.sleep(0.02)
        cb.is_allowed()  # Trigger transition
        assert cb.state == CircuitState.HALF_OPEN

        # Failure should reopen
        cb.record_failure("another error")
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics tracking."""

    def test_metrics_initial_state(self):
        """Test initial metrics state."""
        cb = CircuitBreaker("test")
        metrics = cb.get_metrics()

        assert metrics.state == CircuitState.CLOSED
        assert metrics.consecutive_failures == 0
        assert metrics.consecutive_successes == 0
        assert metrics.total_failures == 0
        assert metrics.total_successes == 0
        assert metrics.failure_rate == 0.0
        assert metrics.open_count == 0

    def test_metrics_track_successes(self):
        """Test metrics track successes."""
        cb = CircuitBreaker("test")

        cb.record_success()
        cb.record_success()
        cb.record_success()

        metrics = cb.get_metrics()
        assert metrics.consecutive_successes == 3
        assert metrics.total_successes == 3
        assert metrics.consecutive_failures == 0

    def test_metrics_track_failures(self):
        """Test metrics track failures."""
        config = CircuitBreakerConfig(failure_threshold=10)  # High threshold
        cb = CircuitBreaker("test", config)

        cb.record_failure("error 1")
        cb.record_failure("error 2")

        metrics = cb.get_metrics()
        assert metrics.consecutive_failures == 2
        assert metrics.total_failures == 2
        assert metrics.consecutive_successes == 0

    def test_metrics_track_open_count(self):
        """Test metrics track open count."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            open_timeout_seconds=0.01,
        )
        cb = CircuitBreaker("test", config)

        # Open once
        cb.record_failure("error")
        metrics = cb.get_metrics()
        assert metrics.open_count == 1

        # Transition to HALF_OPEN, then OPEN again
        time.sleep(0.02)
        cb.is_allowed()  # Transition to HALF_OPEN
        cb.record_failure("another error")

        metrics = cb.get_metrics()
        assert metrics.open_count == 2

    def test_failure_resets_consecutive_successes(self):
        """Test that failure resets consecutive successes."""
        config = CircuitBreakerConfig(failure_threshold=10)
        cb = CircuitBreaker("test", config)

        cb.record_success()
        cb.record_success()
        cb.record_failure("error")

        metrics = cb.get_metrics()
        assert metrics.consecutive_successes == 0
        assert metrics.consecutive_failures == 1

    def test_success_resets_consecutive_failures(self):
        """Test that success resets consecutive failures."""
        config = CircuitBreakerConfig(failure_threshold=10)
        cb = CircuitBreaker("test", config)

        cb.record_failure("error 1")
        cb.record_failure("error 2")
        cb.record_success()

        metrics = cb.get_metrics()
        assert metrics.consecutive_failures == 0
        assert metrics.consecutive_successes == 1


class TestCircuitBreakerRateBasedTriggering:
    """Test rate-based circuit opening."""

    def test_high_failure_rate_opens_circuit(self):
        """Test that high failure rate opens the circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=100,  # High consecutive threshold
            failure_rate_threshold=0.5,  # 50% rate threshold
            sample_window_seconds=60.0,
        )
        cb = CircuitBreaker("test", config)

        # Record 3 failures and 2 successes (60% failure rate)
        cb.record_failure("error 1")
        cb.record_success()
        cb.record_failure("error 2")
        cb.record_success()
        cb.record_failure("error 3")

        # Should open due to rate (60% > 50%)
        assert cb.state == CircuitState.OPEN

    def test_low_failure_rate_keeps_closed(self):
        """Test that low failure rate keeps circuit closed."""
        config = CircuitBreakerConfig(
            failure_threshold=100,
            failure_rate_threshold=0.5,
            sample_window_seconds=60.0,
        )
        cb = CircuitBreaker("test", config)

        # Record 4 successes first to establish baseline, then 1 failure (20% failure rate)
        # Order matters because rate is checked on each failure
        cb.record_success()
        cb.record_success()
        cb.record_success()
        cb.record_success()
        cb.record_failure("error")  # 1/5 = 20% < 50%

        # Should stay closed (20% < 50%)
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerReset:
    """Test circuit breaker reset functionality."""

    def test_reset_closes_circuit(self):
        """Test that reset closes the circuit."""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", config)

        # Open the circuit
        cb.record_failure("error")
        assert cb.state == CircuitState.OPEN

        # Reset
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_reset_clears_counters(self):
        """Test that reset clears counters."""
        config = CircuitBreakerConfig(failure_threshold=10)
        cb = CircuitBreaker("test", config)

        cb.record_failure("error 1")
        cb.record_failure("error 2")
        cb.record_failure("error 3")

        cb.reset()

        metrics = cb.get_metrics()
        assert metrics.consecutive_failures == 0
        assert metrics.consecutive_successes == 0


class TestCircuitBreakerCallback:
    """Test state change callback."""

    def test_callback_on_state_change(self):
        """Test callback is called on state changes."""
        state_changes = []

        def on_change(old_state, new_state):
            state_changes.append((old_state, new_state))

        config = CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=1,
            open_timeout_seconds=0.01,
        )
        cb = CircuitBreaker("test", config, on_state_change=on_change)

        # Open circuit
        cb.record_failure("error")
        assert state_changes[-1] == (CircuitState.CLOSED, CircuitState.OPEN)

        # Transition to HALF_OPEN
        time.sleep(0.02)
        cb.is_allowed()
        assert state_changes[-1] == (CircuitState.OPEN, CircuitState.HALF_OPEN)

        # Close circuit
        cb.record_success()
        assert state_changes[-1] == (CircuitState.HALF_OPEN, CircuitState.CLOSED)

        assert len(state_changes) == 3


class TestCircuitBreakerName:
    """Test circuit breaker name property."""

    def test_name_property(self):
        """Test name property returns correct value."""
        cb = CircuitBreaker("my-circuit")
        assert cb.name == "my-circuit"
