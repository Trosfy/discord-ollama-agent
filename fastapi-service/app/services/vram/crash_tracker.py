"""Crash Tracker for circuit breaker pattern."""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Callable, Awaitable
import asyncio
import logging_client

logger = logging_client.setup_logger('crash_tracker')


class CrashTracker:
    """
    Tracks model crashes to detect patterns and prevent crash loops.

    Circuit Breaker Logic:
    - Records crashes with timestamps
    - Checks if model has crashed N+ times in time window
    - Recommends proactive eviction for unstable models

    Thread-safe for concurrent async access.
    """

    def __init__(self, crash_threshold: int = 2, time_window_seconds: int = 300):
        """
        Initialize crash tracker.

        Args:
            crash_threshold: Number of crashes to trigger circuit breaker (default: 2)
            time_window_seconds: Time window in seconds (default: 300 = 5 minutes)
        """
        self._crashes: Dict[str, List[Dict[str, Any]]] = {}
        self._crash_threshold = crash_threshold
        self._time_window_seconds = time_window_seconds
        self._observers: List[Callable[[str, int], Awaitable[None]]] = []
        logger.info(
            f"✅ CrashTracker initialized (threshold={crash_threshold}, "
            f"window={time_window_seconds}s)"
        )

    def add_observer(self, callback: Callable[[str, int], Awaitable[None]]) -> None:
        """
        Add observer for circuit breaker events (Observer Pattern).

        Args:
            callback: Async function(model_id, crash_count) to call on circuit breaker
        """
        self._observers.append(callback)
        logger.info(f"✅ Added observer to CrashTracker (total: {len(self._observers)})")

    def record_crash(self, model_id: str, reason: str = "unknown") -> None:
        """
        Record that a model crashed.

        Args:
            model_id: Model that crashed
            reason: Reason for crash (e.g., "generation_failure", "earlyoom_kill")
        """
        now = datetime.now()

        # Initialize list if first crash for this model
        if model_id not in self._crashes:
            self._crashes[model_id] = []

        # Add crash record
        self._crashes[model_id].append({
            'timestamp': now,
            'reason': reason
        })

        # Clean old crashes outside time window
        self._clean_old_crashes(model_id)

        # Log warning if threshold exceeded
        crash_count = len(self._crashes[model_id])
        if crash_count >= self._crash_threshold:
            logger.warning(
                f"⚠️  Circuit breaker: {model_id} has {crash_count} crashes "
                f"in last {self._time_window_seconds}s (threshold: {self._crash_threshold})"
            )

            # Notify all observers (Observer Pattern)
            for observer in self._observers:
                asyncio.create_task(observer(model_id, crash_count))
        else:
            logger.info(
                f"📝 Recorded crash for {model_id} "
                f"({crash_count}/{self._crash_threshold}, reason: {reason})"
            )

    def check_crash_history(self, model_id: str) -> Dict[str, Any]:
        """
        Check if model has crash history requiring circuit breaker action.

        Args:
            model_id: Model to check

        Returns:
            Dictionary with circuit breaker status:
            {
                'needs_protection': bool,  # True if >= threshold crashes in window
                'crash_count': int,
                'last_crash_seconds_ago': float or None,
                'recommendation': str  # Human-readable advice
            }
        """
        # Clean old crashes first
        self._clean_old_crashes(model_id)

        # Get recent crashes
        if model_id not in self._crashes or not self._crashes[model_id]:
            return {
                'needs_protection': False,
                'crash_count': 0,
                'last_crash_seconds_ago': None,
                'recommendation': 'No recent crashes - safe to load'
            }

        crash_count = len(self._crashes[model_id])
        last_crash = self._crashes[model_id][-1]['timestamp']
        seconds_ago = (datetime.now() - last_crash).total_seconds()

        needs_protection = crash_count >= self._crash_threshold

        if needs_protection:
            recommendation = (
                f"Circuit breaker triggered: {crash_count} crashes detected. "
                f"Recommend proactive eviction to create safety buffer."
            )
        else:
            recommendation = (
                f"Model has {crash_count} crash(es) but below threshold "
                f"({self._crash_threshold}). Safe to load normally."
            )

        return {
            'needs_protection': needs_protection,
            'crash_count': crash_count,
            'last_crash_seconds_ago': seconds_ago,
            'recommendation': recommendation
        }

    def get_crash_stats(self, model_id: str) -> Dict[str, Any]:
        """
        Get detailed crash statistics for monitoring.

        Args:
            model_id: Model to get stats for

        Returns:
            Dictionary with crash statistics
        """
        self._clean_old_crashes(model_id)

        if model_id not in self._crashes or not self._crashes[model_id]:
            return {
                'model_id': model_id,
                'crash_count': 0,
                'crashes': [],
                'last_crash_seconds_ago': None
            }

        crashes = self._crashes[model_id]
        last_crash = crashes[-1]['timestamp']
        seconds_ago = (datetime.now() - last_crash).total_seconds()

        return {
            'model_id': model_id,
            'crash_count': len(crashes),
            'crashes': [
                {
                    'timestamp': c['timestamp'].isoformat(),
                    'reason': c['reason'],
                    'seconds_ago': (datetime.now() - c['timestamp']).total_seconds()
                }
                for c in crashes
            ],
            'last_crash_seconds_ago': seconds_ago
        }

    def get_all_models_with_crashes(self) -> List[str]:
        """
        Get list of all models with recent crashes.

        Returns:
            List of model IDs with crashes in time window
        """
        # Clean all models first
        for model_id in list(self._crashes.keys()):
            self._clean_old_crashes(model_id)

        # Return models with crashes
        return [
            model_id for model_id, crashes in self._crashes.items()
            if crashes  # Non-empty list
        ]

    def clear_history(self, model_id: str) -> None:
        """
        Clear crash history for a model.

        Args:
            model_id: Model to clear history for

        Note:
            Can be used to reset state after successful generation,
            but optional - crashes naturally expire after time window.
        """
        if model_id in self._crashes:
            crash_count = len(self._crashes[model_id])
            del self._crashes[model_id]
            logger.info(f"🧹 Cleared {crash_count} crash(es) for {model_id}")

    def _clean_old_crashes(self, model_id: str) -> None:
        """
        Remove crashes outside the time window.

        Args:
            model_id: Model to clean crashes for
        """
        if model_id not in self._crashes:
            return

        cutoff_time = datetime.now() - timedelta(seconds=self._time_window_seconds)

        # Filter crashes within time window
        self._crashes[model_id] = [
            crash for crash in self._crashes[model_id]
            if crash['timestamp'] > cutoff_time
        ]

        # Remove model entry if no recent crashes
        if not self._crashes[model_id]:
            del self._crashes[model_id]
