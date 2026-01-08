"""Integration tests for VRAM orchestration system.

These tests verify the full workflow of the VRAM orchestrator with all components.
"""
import pytest
from unittest.mock import patch, Mock, AsyncMock
from app.services.vram import create_orchestrator, get_orchestrator


@pytest.mark.asyncio
async def test_full_orchestrator_workflow():
    """Test complete workflow: load model -> check memory -> evict if needed -> load."""
    # Create orchestrator with real components
    orchestrator = create_orchestrator()

    # Mock system calls
    free_output = """              total        used        free      shared  buff/cache   available
Mem:    137438953472 83886080000 20971520000  1073741824 32505856000 50331648000
Swap:            0           0           0"""

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout=free_output)

        with patch('builtins.open'):
            with patch('app.services.vram.orchestrator.get_model_capabilities') as mock_caps:
                # Mock model capabilities
                mock_caps.return_value = Mock(
                    backend=Mock(type="ollama"),
                    vram_size_gb=40.0,
                    priority="NORMAL"
                )

                with patch('app.services.vram.backend_managers.force_unload_model', new_callable=AsyncMock):
                    # Load first model
                    await orchestrator.request_model_load("model-1")

                    status = await orchestrator.get_status()
                    assert len(status['loaded_models']) == 1
                    assert status['loaded_models'][0]['model_id'] == "model-1"

                    # Load second model
                    await orchestrator.request_model_load("model-2")

                    status = await orchestrator.get_status()
                    assert len(status['loaded_models']) == 2


@pytest.mark.asyncio
async def test_singleton_pattern():
    """Test that get_orchestrator returns the same instance."""
    orchestrator1 = get_orchestrator()
    orchestrator2 = get_orchestrator()

    assert orchestrator1 is orchestrator2


@pytest.mark.asyncio
async def test_model_registration_and_eviction():
    """Test that models are properly registered and evicted."""
    orchestrator = create_orchestrator()

    free_output = """              total        used        free      shared  buff/cache   available
Mem:    137438953472 83886080000 20971520000  1073741824 32505856000 50331648000
Swap:            0           0           0"""

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout=free_output)

        with patch('builtins.open'):
            with patch('app.services.vram.orchestrator.get_model_capabilities') as mock_caps:
                with patch('app.services.vram.backend_managers.force_unload_model', new_callable=AsyncMock):
                    # Load models until we approach the limit
                    mock_caps.return_value = Mock(
                        backend=Mock(type="ollama"),
                        vram_size_gb=30.0,
                        priority="NORMAL"
                    )

                    # Load 3 models (90GB total)
                    await orchestrator.request_model_load("model-1")
                    await orchestrator.request_model_load("model-2")
                    await orchestrator.request_model_load("model-3")

                    status = await orchestrator.get_status()
                    assert len(status['loaded_models']) == 3

                    # Try to load a 4th model that would exceed limit (120GB > 110GB limit)
                    # This should trigger eviction
                    await orchestrator.request_model_load("model-4")

                    status = await orchestrator.get_status()

                    # Should have evicted at least one model
                    model_ids = [m['model_id'] for m in status['loaded_models']]
                    assert "model-4" in model_ids


@pytest.mark.asyncio
async def test_priority_protection():
    """Test that high priority models are protected from eviction."""
    orchestrator = create_orchestrator()

    free_output = """              total        used        free      shared  buff/cache   available
Mem:    137438953472 83886080000 20971520000  1073741824 32505856000 50331648000
Swap:            0           0           0"""

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout=free_output)

        with patch('builtins.open'):
            with patch('app.services.vram.orchestrator.get_model_capabilities') as mock_caps:
                with patch('app.services.vram.backend_managers.force_unload_model', new_callable=AsyncMock):
                    # Load a CRITICAL priority model
                    mock_caps.return_value = Mock(
                        backend=Mock(type="ollama"),
                        vram_size_gb=50.0,
                        priority="CRITICAL"
                    )
                    await orchestrator.request_model_load("critical-model")

                    # Load LOW priority model
                    mock_caps.return_value = Mock(
                        backend=Mock(type="ollama"),
                        vram_size_gb=40.0,
                        priority="LOW"
                    )
                    await orchestrator.request_model_load("low-priority-model")

                    # Load NORMAL priority model that should trigger eviction
                    mock_caps.return_value = Mock(
                        backend=Mock(type="ollama"),
                        vram_size_gb=30.0,
                        priority="NORMAL"
                    )
                    await orchestrator.request_model_load("normal-model")

                    status = await orchestrator.get_status()
                    model_ids = [m['model_id'] for m in status['loaded_models']]

                    # CRITICAL model should still be loaded
                    assert "critical-model" in model_ids


@pytest.mark.asyncio
async def test_lru_ordering_maintained():
    """Test that LRU ordering is maintained across operations."""
    orchestrator = create_orchestrator()

    free_output = """              total        used        free      shared  buff/cache   available
Mem:    137438953472 83886080000 20971520000  1073741824 32505856000 50331648000
Swap:            0           0           0"""

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout=free_output)

        with patch('builtins.open'):
            with patch('app.services.vram.orchestrator.get_model_capabilities') as mock_caps:
                mock_caps.return_value = Mock(
                    backend=Mock(type="ollama"),
                    vram_size_gb=20.0,
                    priority="NORMAL"
                )

                # Load models
                await orchestrator.request_model_load("model-1")
                await orchestrator.request_model_load("model-2")
                await orchestrator.request_model_load("model-3")

                # Access model-1 to make it most recent
                await orchestrator.mark_model_accessed("model-1")

                status = await orchestrator.get_status()

                # model-1 should have newest last_accessed timestamp
                model_1 = next(m for m in status['loaded_models'] if m['model_id'] == "model-1")
                model_2 = next(m for m in status['loaded_models'] if m['model_id'] == "model-2")

                # model_1 should be accessed more recently than model_2
                assert model_1['last_accessed'] > model_2['last_accessed']


@pytest.mark.asyncio
async def test_manual_model_unload():
    """Test manually unloading a model via API."""
    orchestrator = create_orchestrator()

    free_output = """              total        used        free      shared  buff/cache   available
Mem:    137438953472 83886080000 20971520000  1073741824 32505856000 50331648000
Swap:            0           0           0"""

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout=free_output)

        with patch('builtins.open'):
            with patch('app.services.vram.orchestrator.get_model_capabilities') as mock_caps:
                mock_caps.return_value = Mock(
                    backend=Mock(type="ollama"),
                    vram_size_gb=20.0,
                    priority="NORMAL"
                )

                with patch('app.services.vram.backend_managers.force_unload_model', new_callable=AsyncMock):
                    # Load a model
                    await orchestrator.request_model_load("test-model")

                    status = await orchestrator.get_status()
                    assert len(status['loaded_models']) == 1

                    # Manually unload it
                    await orchestrator.mark_model_unloaded("test-model")

                    status = await orchestrator.get_status()
                    assert len(status['loaded_models']) == 0


@pytest.mark.asyncio
async def test_cache_flush_for_large_models():
    """Test that buffer cache is flushed for models >70GB."""
    orchestrator = create_orchestrator()

    free_output = """              total        used        free      shared  buff/cache   available
Mem:    137438953472 83886080000 20971520000  1073741824 32505856000 50331648000
Swap:            0           0           0"""

    flush_called = False

    def mock_run(*args, **kwargs):
        nonlocal flush_called
        # Check if this is the cache flush command
        if args and len(args[0]) > 0 and 'drop_caches' in str(args[0]):
            flush_called = True
        return Mock(returncode=0, stdout=free_output)

    with patch('subprocess.run', side_effect=mock_run):
        with patch('builtins.open'):
            with patch('app.services.vram.orchestrator.get_model_capabilities') as mock_caps:
                # Large model (>70GB)
                mock_caps.return_value = Mock(
                    backend=Mock(type="ollama"),
                    vram_size_gb=80.0,
                    priority="NORMAL"
                )

                await orchestrator.request_model_load("large-model")

                # Cache flush should have been triggered
                assert flush_called
