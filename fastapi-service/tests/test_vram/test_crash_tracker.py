"""Tests for CrashTracker."""
import pytest
import asyncio
from datetime import datetime, timedelta
from app.services.vram.crash_tracker import CrashTracker


@pytest.fixture
def tracker():
    """Create a CrashTracker with 2 crash threshold and 300s window."""
    return CrashTracker(crash_threshold=2, time_window_seconds=300)


def test_crash_tracker_single_crash(tracker):
    """Test that single crash doesn't trigger circuit breaker."""
    tracker.record_crash("model-1")
    status = tracker.check_crash_history("model-1")

    assert status['needs_protection'] is False
    assert status['crash_count'] == 1
    assert status['last_crash_seconds_ago'] is not None
    assert 'below threshold' in status['recommendation']


def test_crash_tracker_threshold_reached(tracker):
    """Test that 2 crashes trigger circuit breaker."""
    tracker.record_crash("model-1")
    tracker.record_crash("model-1")

    status = tracker.check_crash_history("model-1")
    assert status['needs_protection'] is True
    assert status['crash_count'] == 2
    assert 'Circuit breaker triggered' in status['recommendation']


def test_crash_tracker_multiple_crashes(tracker):
    """Test tracking multiple crashes."""
    tracker.record_crash("model-1")
    tracker.record_crash("model-1")
    tracker.record_crash("model-1")

    status = tracker.check_crash_history("model-1")
    assert status['needs_protection'] is True
    assert status['crash_count'] == 3


def test_crash_tracker_old_crashes_ignored(tracker):
    """Test that crashes outside time window are ignored."""
    # Simulate old crash (> 5 minutes ago)
    old_time = datetime.now() - timedelta(seconds=400)
    tracker._crashes["model-1"] = [
        {'timestamp': old_time, 'reason': 'test'}
    ]

    status = tracker.check_crash_history("model-1")
    assert status['needs_protection'] is False
    assert status['crash_count'] == 0  # Old crash cleaned up
    assert status['last_crash_seconds_ago'] is None


def test_crash_tracker_mixed_old_and_new_crashes(tracker):
    """Test that only recent crashes are counted."""
    # Add old crash
    old_time = datetime.now() - timedelta(seconds=400)
    tracker._crashes["model-1"] = [
        {'timestamp': old_time, 'reason': 'old'}
    ]

    # Add new crash
    tracker.record_crash("model-1")

    status = tracker.check_crash_history("model-1")
    assert status['needs_protection'] is False  # Only 1 recent crash
    assert status['crash_count'] == 1


def test_crash_tracker_per_model_isolation(tracker):
    """Test that crashes are tracked per model."""
    tracker.record_crash("model-1")
    tracker.record_crash("model-1")
    tracker.record_crash("model-2")

    status1 = tracker.check_crash_history("model-1")
    status2 = tracker.check_crash_history("model-2")

    assert status1['needs_protection'] is True  # 2 crashes
    assert status1['crash_count'] == 2

    assert status2['needs_protection'] is False  # 1 crash
    assert status2['crash_count'] == 1


def test_crash_tracker_no_crashes(tracker):
    """Test model with no crash history."""
    status = tracker.check_crash_history("never-crashed-model")

    assert status['needs_protection'] is False
    assert status['crash_count'] == 0
    assert status['last_crash_seconds_ago'] is None
    assert 'No recent crashes' in status['recommendation']


def test_crash_tracker_get_crash_stats(tracker):
    """Test detailed crash statistics."""
    tracker.record_crash("model-1", reason="earlyoom_kill")
    tracker.record_crash("model-1", reason="generation_failure")

    stats = tracker.get_crash_stats("model-1")

    assert stats['model_id'] == "model-1"
    assert stats['crash_count'] == 2
    assert len(stats['crashes']) == 2
    assert stats['crashes'][0]['reason'] == "earlyoom_kill"
    assert stats['crashes'][1]['reason'] == "generation_failure"
    assert stats['last_crash_seconds_ago'] is not None


def test_crash_tracker_get_all_models_with_crashes(tracker):
    """Test getting all models with recent crashes."""
    tracker.record_crash("model-1")
    tracker.record_crash("model-2")
    tracker.record_crash("model-3")

    # Add old crash that should be cleaned
    old_time = datetime.now() - timedelta(seconds=400)
    tracker._crashes["model-4"] = [
        {'timestamp': old_time, 'reason': 'old'}
    ]

    models = tracker.get_all_models_with_crashes()

    assert len(models) == 3
    assert "model-1" in models
    assert "model-2" in models
    assert "model-3" in models
    assert "model-4" not in models  # Old crash cleaned


def test_crash_tracker_clear_history(tracker):
    """Test clearing crash history for a model."""
    tracker.record_crash("model-1")
    tracker.record_crash("model-1")

    assert tracker.check_crash_history("model-1")['crash_count'] == 2

    tracker.clear_history("model-1")

    assert tracker.check_crash_history("model-1")['crash_count'] == 0


def test_crash_tracker_clear_nonexistent_model(tracker):
    """Test clearing history for model with no crashes (no error)."""
    tracker.clear_history("nonexistent-model")  # Should not raise

    status = tracker.check_crash_history("nonexistent-model")
    assert status['crash_count'] == 0


def test_crash_tracker_crash_reasons(tracker):
    """Test that crash reasons are tracked."""
    tracker.record_crash("model-1", reason="earlyoom_kill")
    tracker.record_crash("model-1", reason="generation_failure")

    stats = tracker.get_crash_stats("model-1")

    reasons = [c['reason'] for c in stats['crashes']]
    assert "earlyoom_kill" in reasons
    assert "generation_failure" in reasons


def test_crash_tracker_custom_threshold(tracker):
    """Test CrashTracker with custom threshold."""
    custom_tracker = CrashTracker(crash_threshold=3, time_window_seconds=300)

    custom_tracker.record_crash("model-1")
    custom_tracker.record_crash("model-1")

    # 2 crashes shouldn't trigger with threshold of 3
    status = custom_tracker.check_crash_history("model-1")
    assert status['needs_protection'] is False
    assert status['crash_count'] == 2

    # 3 crashes should trigger
    custom_tracker.record_crash("model-1")
    status = custom_tracker.check_crash_history("model-1")
    assert status['needs_protection'] is True
    assert status['crash_count'] == 3


def test_crash_tracker_timestamps_within_window(tracker):
    """Test that all tracked crashes are within the time window."""
    tracker.record_crash("model-1")
    import time
    time.sleep(0.1)  # Small delay
    tracker.record_crash("model-1")

    stats = tracker.get_crash_stats("model-1")

    for crash in stats['crashes']:
        assert crash['seconds_ago'] <= 300  # Within 5 minute window


def test_crash_tracker_automatic_cleanup(tracker):
    """Test that old crashes are automatically cleaned on check."""
    # Add a crash
    tracker.record_crash("model-1")

    # Artificially age it
    old_time = datetime.now() - timedelta(seconds=400)
    tracker._crashes["model-1"][0]['timestamp'] = old_time

    # Check should clean it up
    status = tracker.check_crash_history("model-1")

    assert status['crash_count'] == 0
    assert "model-1" not in tracker._crashes  # Entry removed
