"""Tests for UnifiedMemoryMonitor."""
import pytest
from unittest.mock import Mock, patch, mock_open
from app.services.vram.unified_memory_monitor import UnifiedMemoryMonitor
from app.services.vram.model_registry import ModelRegistry
from app.services.vram.interfaces import BackendType, ModelPriority


@pytest.mark.asyncio
async def test_get_status_parses_free_output():
    """Test that get_status correctly parses `free -b` output."""
    registry = ModelRegistry()
    registry.register("test-model", BackendType.OLLAMA, 25.0)

    monitor = UnifiedMemoryMonitor(registry)

    # Mock free command output
    free_output = """              total        used        free      shared  buff/cache   available
Mem:    137438953472 83886080000 20971520000  1073741824 32505856000 50331648000
Swap:            0           0           0"""

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout=free_output
        )

        with patch('builtins.open', mock_open(read_data="some avg10=0.00\nfull avg10=0.00")):
            status = await monitor.get_status()

            # Check that values are parsed correctly
            assert status.total_gb > 0
            assert status.used_gb > 0
            assert status.available_gb > 0
            assert status.model_usage_gb == 25.0  # From registry


@pytest.mark.asyncio
async def test_check_pressure_parses_psi():
    """Test that check_pressure parses PSI correctly."""
    registry = ModelRegistry()
    monitor = UnifiedMemoryMonitor(registry)

    psi_content = """some avg10=15.50 avg60=10.25 avg300=5.75 total=123456
full avg10=2.30 avg60=1.50 avg300=0.80 total=78901"""

    with patch('builtins.open', mock_open(read_data=psi_content)):
        psi = await monitor.check_pressure()

        assert psi['some_avg10'] == 15.50
        assert psi['full_avg10'] == 2.30


@pytest.mark.asyncio
async def test_check_pressure_handles_missing_file():
    """Test that check_pressure handles missing PSI file gracefully."""
    registry = ModelRegistry()
    monitor = UnifiedMemoryMonitor(registry)

    with patch('builtins.open', side_effect=FileNotFoundError):
        psi = await monitor.check_pressure()

        # Should return zeros instead of crashing
        assert psi['some_avg10'] == 0.0
        assert psi['full_avg10'] == 0.0


@pytest.mark.asyncio
async def test_flush_cache_calls_sudo():
    """Test that flush_cache calls sudo command."""
    registry = ModelRegistry()
    monitor = UnifiedMemoryMonitor(registry)

    with patch('subprocess.run') as mock_run:
        await monitor.flush_cache()

        # Should have called sudo to flush cache
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert 'sudo' in call_args
        assert 'drop_caches' in ' '.join(call_args)


@pytest.mark.asyncio
async def test_get_status_fallback_on_error():
    """Test that get_status returns fallback values on error."""
    registry = ModelRegistry()
    registry.register("test-model", BackendType.OLLAMA, 15.0)

    monitor = UnifiedMemoryMonitor(registry)

    with patch('subprocess.run', side_effect=Exception("Command failed")):
        with patch('builtins.open', mock_open(read_data="some avg10=0.00\nfull avg10=0.00")):
            status = await monitor.get_status()

            # Should return fallback values
            assert status.total_gb == 128.0  # Fallback
            assert status.model_usage_gb == 15.0  # Still from registry


@pytest.mark.asyncio
async def test_high_psi_triggers_warning():
    """Test that high PSI values trigger warnings in logs."""
    registry = ModelRegistry()
    monitor = UnifiedMemoryMonitor(registry)

    free_output = """              total        used        free      shared  buff/cache   available
Mem:    137438953472 83886080000 20971520000  1073741824 32505856000 50331648000
Swap:            0           0           0"""

    # High PSI values
    psi_content = """some avg10=25.50 avg60=20.25 avg300=15.75 total=123456
full avg10=8.30 avg60=5.50 avg300=2.80 total=78901"""

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout=free_output)

        with patch('builtins.open', mock_open(read_data=psi_content)):
            with patch('app.services.vram.unified_memory_monitor.logger') as mock_logger:
                status = await monitor.get_status()

                # Should have logged a warning about high PSI
                assert mock_logger.warning.called
                warning_msg = mock_logger.warning.call_args[0][0]
                assert "Memory pressure" in warning_msg


@pytest.mark.asyncio
async def test_model_usage_from_registry():
    """Test that model usage is calculated from registry."""
    registry = ModelRegistry()
    registry.register("model-1", BackendType.OLLAMA, 20.0)
    registry.register("model-2", BackendType.OLLAMA, 30.0)
    registry.register("model-3", BackendType.OLLAMA, 15.0)

    monitor = UnifiedMemoryMonitor(registry)

    free_output = """              total        used        free      shared  buff/cache   available
Mem:    137438953472 83886080000 20971520000  1073741824 32505856000 50331648000
Swap:            0           0           0"""

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout=free_output)

        with patch('builtins.open', mock_open(read_data="some avg10=0.00\nfull avg10=0.00")):
            status = await monitor.get_status()

            # Should sum all models: 20 + 30 + 15 = 65
            assert status.model_usage_gb == 65.0
