"""Pytest configuration and shared fixtures."""
import pytest
import asyncio
import sys
from unittest.mock import Mock


# Mock logging_client from shared module before any imports
mock_logging = Mock()
mock_logging.setup_logger = Mock(return_value=Mock())
sys.modules['logging_client'] = mock_logging


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def anyio_backend():
    """Use asyncio as the async backend."""
    return 'asyncio'
