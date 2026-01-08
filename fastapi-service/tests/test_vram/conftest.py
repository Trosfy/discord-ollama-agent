"""Pytest configuration for VRAM tests."""
import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton orchestrator between tests."""
    import app.services.vram
    app.services.vram._orchestrator = None
    yield
    app.services.vram._orchestrator = None


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    from unittest.mock import Mock
    settings = Mock()
    settings.VRAM_SOFT_LIMIT_GB = 100.0
    settings.VRAM_HARD_LIMIT_GB = 110.0
    settings.VRAM_ENABLE_ORCHESTRATOR = True
    settings.HEALTH_CHECK_INTERVAL = 30
    return settings
