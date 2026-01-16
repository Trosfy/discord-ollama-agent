"""Profile manager for tracking fallback state and recovery.

This module provides the ProfileManager class which tracks model loading
failures and manages automatic fallback to conservative profiles when
the system encounters persistent issues.
"""
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable

from ..core.interfaces import IConfigProfile
from ..core.profiles import get_profile

logger = logging.getLogger(__name__)


# Thresholds for fallback and recovery behavior
FALLBACK_THRESHOLD = 3  # Consecutive failures before triggering fallback
RECOVERY_SUCCESS_THRESHOLD = 5  # Consecutive successes before attempting recovery


class FallbackState(Enum):
    """Current state of the fallback system."""
    NORMAL = "normal"           # Operating with original profile
    DEGRADED = "degraded"       # Operating with fallback profile
    PROBING = "probing"         # Testing if original profile can be restored


@dataclass
class FallbackMetrics:
    """Metrics tracking for fallback decisions."""
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    fallback_count: int = 0
    recovery_count: int = 0


@dataclass
class ProfileManagerState:
    """Internal state of the profile manager."""
    original_profile_name: str
    current_profile_name: str
    fallback_state: FallbackState = FallbackState.NORMAL
    metrics: FallbackMetrics = field(default_factory=FallbackMetrics)


class ProfileManager:
    """
    Manages profile state and fallback behavior.

    This class tracks model loading failures and manages automatic
    fallback to conservative profiles when persistent issues occur.
    It does NOT interact with backends directly - that responsibility
    belongs to VRAMOrchestrator.

    Fallback Flow:
    1. System operates normally with configured profile
    2. If FALLBACK_THRESHOLD consecutive failures occur, switch to conservative
    3. After RECOVERY_SUCCESS_THRESHOLD successes in degraded mode, probe recovery
    4. If probe succeeds, restore original profile; otherwise stay degraded

    Example:
        manager = ProfileManager(initial_profile)

        # On model load failure
        manager.record_load_failure("gpt-oss:120b")
        if manager.state.fallback_state == FallbackState.DEGRADED:
            # Use conservative profile
            profile = manager.get_current_profile()

        # On model load success
        manager.record_load_success("gpt-oss:20b")
        if manager.should_probe_recovery():
            # Attempt to load a model from original profile
            success = try_load_original_model()
            manager.record_probe_result(success)
    """

    def __init__(
        self,
        initial_profile: IConfigProfile,
        on_fallback: Optional[Callable[[str, str], None]] = None,
        on_recovery: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the profile manager.

        Args:
            initial_profile: The initial configuration profile to use.
            on_fallback: Optional callback when fallback is triggered.
                         Called with (original_profile_name, reason).
            on_recovery: Optional callback when recovery succeeds.
                         Called with (restored_profile_name).
        """
        self._state = ProfileManagerState(
            original_profile_name=initial_profile.profile_name,
            current_profile_name=initial_profile.profile_name,
        )
        self._current_profile = initial_profile
        self._original_profile = initial_profile
        self._on_fallback = on_fallback
        self._on_recovery = on_recovery

    @property
    def state(self) -> ProfileManagerState:
        """Get the current state of the profile manager."""
        return self._state

    def get_current_profile(self) -> IConfigProfile:
        """
        Get the currently active profile.

        Returns:
            The current profile (may be fallback or original).
        """
        return self._current_profile

    def get_original_profile(self) -> IConfigProfile:
        """
        Get the original profile (before any fallback).

        Returns:
            The original configured profile.
        """
        return self._original_profile

    def record_load_failure(self, model_name: str, reason: Optional[str] = None) -> None:
        """
        Record a model load failure.

        Updates failure metrics and potentially triggers fallback
        if the failure threshold is reached.

        Args:
            model_name: Name of the model that failed to load.
            reason: Optional reason for the failure.
        """
        metrics = self._state.metrics
        metrics.consecutive_failures += 1
        metrics.consecutive_successes = 0
        metrics.total_failures += 1
        metrics.last_failure_time = time.time()

        logger.warning(
            f"Model load failure: {model_name} "
            f"(consecutive: {metrics.consecutive_failures}, total: {metrics.total_failures})"
            + (f" - {reason}" if reason else "")
        )

        # Check if we should trigger fallback
        if (
            self._state.fallback_state == FallbackState.NORMAL
            and metrics.consecutive_failures >= FALLBACK_THRESHOLD
        ):
            self._trigger_fallback(
                f"Consecutive failures ({metrics.consecutive_failures}) "
                f"exceeded threshold ({FALLBACK_THRESHOLD})"
            )

    def record_load_success(self, model_name: str) -> None:
        """
        Record a successful model load.

        Updates success metrics. In degraded state, accumulating
        successes may lead to recovery probing.

        Args:
            model_name: Name of the model that loaded successfully.
        """
        metrics = self._state.metrics
        metrics.consecutive_successes += 1
        metrics.consecutive_failures = 0
        metrics.total_successes += 1
        metrics.last_success_time = time.time()

        logger.debug(
            f"Model load success: {model_name} "
            f"(consecutive: {metrics.consecutive_successes})"
        )

    def should_probe_recovery(self) -> bool:
        """
        Check if we should attempt to probe recovery to the original profile.

        Recovery probing should occur when:
        1. We are in degraded state
        2. We have accumulated enough consecutive successes

        Returns:
            True if recovery probing should be attempted.
        """
        if self._state.fallback_state != FallbackState.DEGRADED:
            return False

        return self._state.metrics.consecutive_successes >= RECOVERY_SUCCESS_THRESHOLD

    def record_probe_result(self, success: bool, model_name: Optional[str] = None) -> None:
        """
        Record the result of a recovery probe.

        If the probe succeeded, attempt to recover to the original profile.
        If it failed, remain in degraded state and reset the success counter.

        Args:
            success: Whether the probe load succeeded.
            model_name: Optional name of the model that was probed.
        """
        if success:
            logger.info(
                f"Recovery probe succeeded"
                + (f" for {model_name}" if model_name else "")
            )
            self._attempt_recovery()
        else:
            logger.warning(
                f"Recovery probe failed"
                + (f" for {model_name}" if model_name else "")
                + ", remaining in degraded state"
            )
            # Reset success counter but stay in degraded state
            self._state.metrics.consecutive_successes = 0
            self._state.fallback_state = FallbackState.DEGRADED

    def _trigger_fallback(self, reason: str) -> None:
        """
        Switch to the conservative fallback profile.

        Args:
            reason: The reason for triggering fallback.
        """
        logger.warning(
            f"Triggering fallback to conservative profile: {reason}"
        )

        self._state.fallback_state = FallbackState.DEGRADED
        self._state.metrics.fallback_count += 1

        # Switch to conservative profile
        self._current_profile = get_profile("conservative")
        self._state.current_profile_name = "conservative"

        # Reset failure counter (we're starting fresh with new profile)
        self._state.metrics.consecutive_failures = 0

        # Notify callback if registered
        if self._on_fallback:
            try:
                self._on_fallback(self._state.original_profile_name, reason)
            except Exception as e:
                logger.error(f"Fallback callback failed: {e}")

    def _attempt_recovery(self) -> None:
        """
        Attempt to recover to the original profile.

        Called after a successful recovery probe.
        """
        logger.info(
            f"Recovering to original profile: {self._state.original_profile_name}"
        )

        self._state.fallback_state = FallbackState.NORMAL
        self._state.metrics.recovery_count += 1

        # Restore original profile
        self._current_profile = self._original_profile
        self._state.current_profile_name = self._state.original_profile_name

        # Reset counters
        self._state.metrics.consecutive_successes = 0
        self._state.metrics.consecutive_failures = 0

        # Notify callback if registered
        if self._on_recovery:
            try:
                self._on_recovery(self._state.original_profile_name)
            except Exception as e:
                logger.error(f"Recovery callback failed: {e}")

    def force_fallback(self, reason: str = "Manual fallback requested") -> None:
        """
        Force an immediate fallback to conservative profile.

        This bypasses the normal failure counting mechanism.

        Args:
            reason: The reason for forcing fallback.
        """
        if self._state.fallback_state == FallbackState.DEGRADED:
            logger.warning("Already in degraded state, ignoring force_fallback")
            return

        self._trigger_fallback(reason)

    def force_recovery(self) -> bool:
        """
        Force an immediate recovery attempt to the original profile.

        This bypasses the normal success counting mechanism.
        Should only be used for administrative/debugging purposes.

        Returns:
            True if recovery was performed, False if already in normal state.
        """
        if self._state.fallback_state == FallbackState.NORMAL:
            logger.warning("Already in normal state, ignoring force_recovery")
            return False

        self._attempt_recovery()
        return True

    def get_metrics_summary(self) -> dict:
        """
        Get a summary of the fallback metrics.

        Returns:
            Dictionary containing key metrics for monitoring.
        """
        metrics = self._state.metrics
        return {
            "state": self._state.fallback_state.value,
            "current_profile": self._state.current_profile_name,
            "original_profile": self._state.original_profile_name,
            "consecutive_failures": metrics.consecutive_failures,
            "consecutive_successes": metrics.consecutive_successes,
            "total_failures": metrics.total_failures,
            "total_successes": metrics.total_successes,
            "fallback_count": metrics.fallback_count,
            "recovery_count": metrics.recovery_count,
        }
