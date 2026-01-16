"""Unit tests for Profile Manager."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.profile_manager import (
    ProfileManager,
    FallbackState,
    FallbackMetrics,
    ProfileManagerState,
    FALLBACK_THRESHOLD,
    RECOVERY_SUCCESS_THRESHOLD,
)


# =============================================================================
# Mock Profile
# =============================================================================

class MockProfile:
    """Mock profile for testing."""
    def __init__(self, name: str = "test"):
        self._name = name

    @property
    def profile_name(self) -> str:
        return self._name

    @property
    def available_models(self):
        return []

    @property
    def router_model(self) -> str:
        return f"{self._name}-router:7b"

    @property
    def general_model(self) -> str:
        return f"{self._name}-general:70b"

    @property
    def research_model(self) -> str:
        return f"{self._name}-research:24b"

    @property
    def code_model(self) -> str:
        return f"{self._name}-code:13b"

    @property
    def braindump_model(self) -> str:
        return f"{self._name}-braindump:24b"

    @property
    def vision_model(self) -> str:
        return f"{self._name}-vision:7b"

    @property
    def embedding_model(self) -> str:
        return f"{self._name}-embed:0.5b"

    def validate(self) -> None:
        pass


CONSERVATIVE_PROFILE = MockProfile("conservative")


# =============================================================================
# Initial State Tests
# =============================================================================

def test_initial_state_normal():
    """ProfileManager starts in NORMAL state."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    assert manager.state.fallback_state == FallbackState.NORMAL
    assert manager.state.current_profile_name == "balanced"
    assert manager.state.original_profile_name == "balanced"


def test_initial_metrics_zeroed():
    """ProfileManager starts with zeroed metrics."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    metrics = manager.state.metrics
    assert metrics.consecutive_failures == 0
    assert metrics.consecutive_successes == 0
    assert metrics.total_failures == 0
    assert metrics.total_successes == 0


# =============================================================================
# Record Failure Tests
# =============================================================================

@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_record_failure_increments_count(mock_get_profile):
    """record_load_failure increments failure counts."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    manager.record_load_failure("test:7b")

    assert manager.state.metrics.consecutive_failures == 1
    assert manager.state.metrics.total_failures == 1


@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_record_failure_resets_successes(mock_get_profile):
    """record_load_failure resets consecutive successes."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    # Record some successes first
    manager.record_load_success("test:7b")
    manager.record_load_success("test:7b")
    assert manager.state.metrics.consecutive_successes == 2

    # Failure resets it
    manager.record_load_failure("test:7b")
    assert manager.state.metrics.consecutive_successes == 0


@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_record_failure_triggers_fallback_at_threshold(mock_get_profile):
    """record_load_failure triggers fallback after FALLBACK_THRESHOLD failures."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    # Record failures up to threshold
    for i in range(FALLBACK_THRESHOLD):
        manager.record_load_failure(f"model-{i}")

    assert manager.state.fallback_state == FallbackState.DEGRADED
    assert manager.state.current_profile_name == "conservative"
    assert manager.state.metrics.fallback_count == 1


@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_no_fallback_before_threshold(mock_get_profile):
    """Fallback does not occur before reaching threshold."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    # Record failures just below threshold
    for i in range(FALLBACK_THRESHOLD - 1):
        manager.record_load_failure(f"model-{i}")

    assert manager.state.fallback_state == FallbackState.NORMAL


# =============================================================================
# Record Success Tests
# =============================================================================

def test_record_success_increments_count():
    """record_load_success increments success counts."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    manager.record_load_success("test:7b")

    assert manager.state.metrics.consecutive_successes == 1
    assert manager.state.metrics.total_successes == 1


def test_record_success_resets_failures():
    """record_load_success resets consecutive failures."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    # Record some failures first
    manager.record_load_failure("test:7b")
    manager.record_load_failure("test:7b")
    assert manager.state.metrics.consecutive_failures == 2

    # Success resets it
    manager.record_load_success("test:7b")
    assert manager.state.metrics.consecutive_failures == 0


# =============================================================================
# Recovery Probing Tests
# =============================================================================

@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_should_probe_recovery_false_when_normal(mock_get_profile):
    """should_probe_recovery returns False in NORMAL state."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    # Even with many successes, no probing in normal state
    for _ in range(RECOVERY_SUCCESS_THRESHOLD + 1):
        manager.record_load_success("test:7b")

    assert manager.should_probe_recovery() is False


@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_should_probe_recovery_true_after_threshold(mock_get_profile):
    """should_probe_recovery returns True after RECOVERY_SUCCESS_THRESHOLD."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    # Trigger fallback
    for _ in range(FALLBACK_THRESHOLD):
        manager.record_load_failure("test:7b")

    assert manager.state.fallback_state == FallbackState.DEGRADED

    # Accumulate successes
    for _ in range(RECOVERY_SUCCESS_THRESHOLD):
        manager.record_load_success("test:7b")

    assert manager.should_probe_recovery() is True


@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_should_probe_recovery_false_before_threshold(mock_get_profile):
    """should_probe_recovery returns False before success threshold."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    # Trigger fallback
    for _ in range(FALLBACK_THRESHOLD):
        manager.record_load_failure("test:7b")

    # Not enough successes
    for _ in range(RECOVERY_SUCCESS_THRESHOLD - 1):
        manager.record_load_success("test:7b")

    assert manager.should_probe_recovery() is False


# =============================================================================
# Probe Result Tests
# =============================================================================

@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_record_probe_result_success_recovers(mock_get_profile):
    """Successful probe recovers to original profile."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    # Trigger fallback
    for _ in range(FALLBACK_THRESHOLD):
        manager.record_load_failure("test:7b")

    # Record successful probe
    manager.record_probe_result(success=True, model_name="test:70b")

    assert manager.state.fallback_state == FallbackState.NORMAL
    assert manager.state.current_profile_name == "balanced"
    assert manager.state.metrics.recovery_count == 1


@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_record_probe_result_failure_stays_degraded(mock_get_profile):
    """Failed probe stays in DEGRADED state."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    # Trigger fallback
    for _ in range(FALLBACK_THRESHOLD):
        manager.record_load_failure("test:7b")

    # Accumulate successes
    for _ in range(RECOVERY_SUCCESS_THRESHOLD):
        manager.record_load_success("test:7b")

    # Failed probe
    manager.record_probe_result(success=False)

    assert manager.state.fallback_state == FallbackState.DEGRADED
    assert manager.state.metrics.consecutive_successes == 0  # Reset


# =============================================================================
# Force Fallback/Recovery Tests
# =============================================================================

@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_force_fallback(mock_get_profile):
    """force_fallback immediately triggers fallback."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    manager.force_fallback("Manual trigger")

    assert manager.state.fallback_state == FallbackState.DEGRADED
    assert manager.state.current_profile_name == "conservative"


@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_force_fallback_ignores_when_already_degraded(mock_get_profile):
    """force_fallback does nothing if already degraded."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    # First fallback
    manager.force_fallback("First trigger")
    assert manager.state.metrics.fallback_count == 1

    # Second call should be ignored
    manager.force_fallback("Second trigger")
    assert manager.state.metrics.fallback_count == 1  # Not incremented


@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_force_recovery(mock_get_profile):
    """force_recovery immediately recovers."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    # Trigger fallback first
    manager.force_fallback("Test")
    assert manager.state.fallback_state == FallbackState.DEGRADED

    # Force recovery
    result = manager.force_recovery()

    assert result is True
    assert manager.state.fallback_state == FallbackState.NORMAL
    assert manager.state.current_profile_name == "balanced"


def test_force_recovery_returns_false_when_normal():
    """force_recovery returns False if already normal."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    result = manager.force_recovery()

    assert result is False
    assert manager.state.fallback_state == FallbackState.NORMAL


# =============================================================================
# Callback Tests
# =============================================================================

@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_fallback_callback_called(mock_get_profile):
    """on_fallback callback is called when fallback triggers."""
    profile = MockProfile("balanced")
    callback = MagicMock()
    manager = ProfileManager(profile, on_fallback=callback)

    manager.force_fallback("Test reason")

    callback.assert_called_once()
    args = callback.call_args[0]
    assert args[0] == "balanced"  # original profile
    assert "Test reason" in args[1]


@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_recovery_callback_called(mock_get_profile):
    """on_recovery callback is called when recovery succeeds."""
    profile = MockProfile("balanced")
    callback = MagicMock()
    manager = ProfileManager(profile, on_recovery=callback)

    manager.force_fallback("Test")
    manager.force_recovery()

    callback.assert_called_once_with("balanced")


# =============================================================================
# Metrics Summary Tests
# =============================================================================

@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_get_metrics_summary(mock_get_profile):
    """get_metrics_summary returns complete summary."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    # Generate some metrics
    manager.record_load_success("test:7b")
    manager.record_load_failure("test:7b")

    summary = manager.get_metrics_summary()

    assert summary["state"] == "normal"
    assert summary["current_profile"] == "balanced"
    assert summary["original_profile"] == "balanced"
    assert summary["total_failures"] == 1
    assert summary["total_successes"] == 1


@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_get_metrics_summary_degraded(mock_get_profile):
    """get_metrics_summary shows degraded state correctly."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    manager.force_fallback("Test")

    summary = manager.get_metrics_summary()

    assert summary["state"] == "degraded"
    assert summary["current_profile"] == "conservative"
    assert summary["original_profile"] == "balanced"
    assert summary["fallback_count"] == 1


# =============================================================================
# Profile Getter Tests
# =============================================================================

def test_get_current_profile():
    """get_current_profile returns active profile."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    current = manager.get_current_profile()

    assert current.profile_name == "balanced"


def test_get_original_profile():
    """get_original_profile always returns original."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    original = manager.get_original_profile()

    assert original.profile_name == "balanced"


@patch("app.services.profile_manager.get_profile", return_value=CONSERVATIVE_PROFILE)
def test_get_original_profile_after_fallback(mock_get_profile):
    """get_original_profile returns original even after fallback."""
    profile = MockProfile("balanced")
    manager = ProfileManager(profile)

    manager.force_fallback("Test")

    assert manager.get_current_profile().profile_name == "conservative"
    assert manager.get_original_profile().profile_name == "balanced"
