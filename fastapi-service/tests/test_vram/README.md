# VRAM Orchestrator Tests

Comprehensive unit and integration tests for the VRAM orchestration system.

## Test Structure

```
tests/test_vram/
├── __init__.py                    # Package marker
├── conftest.py                    # Pytest fixtures and configuration
├── test_model_registry.py         # Tests for ModelRegistry
├── test_eviction_strategies.py    # Tests for LRU/Priority/Hybrid eviction
├── test_backend_managers.py       # Tests for Ollama/TensorRT/vLLM managers
├── test_memory_monitor.py         # Tests for UnifiedMemoryMonitor
├── test_orchestrator.py           # Tests for VRAMOrchestrator
├── test_integration.py            # End-to-end integration tests
└── README.md                      # This file
```

## Running Tests

### Run all VRAM tests:
```bash
cd fastapi-service
pytest tests/test_vram/ -v
```

### Run specific test file:
```bash
pytest tests/test_vram/test_model_registry.py -v
```

### Run specific test:
```bash
pytest tests/test_vram/test_orchestrator.py::test_orchestrator_successful_load -v
```

### Run with coverage:
```bash
pytest tests/test_vram/ --cov=app.services.vram --cov-report=html
```

### Run integration tests only:
```bash
pytest tests/test_vram/test_integration.py -v
```

## Test Coverage

### test_model_registry.py
- ✅ Model registration and unregistration
- ✅ LRU ordering maintenance
- ✅ Total memory usage calculation
- ✅ Backend filtering
- ✅ Access timestamp updates

### test_eviction_strategies.py
- ✅ LRU eviction (oldest first)
- ✅ Priority-based eviction (low priority first)
- ✅ Hybrid eviction (priority-weighted LRU)
- ✅ CRITICAL model protection
- ✅ Multi-model eviction
- ✅ No eviction when under limit

### test_backend_managers.py
- ✅ Backend type support detection
- ✅ Ollama model unloading
- ✅ TensorRT/vLLM stubs
- ✅ Composite manager delegation
- ✅ Shared memory cleanup

### test_memory_monitor.py
- ✅ Parsing `free -b` output
- ✅ PSI pressure parsing
- ✅ Buffer cache flushing
- ✅ Error handling and fallbacks
- ✅ High PSI warning logging
- ✅ Registry-based usage calculation

### test_orchestrator.py
- ✅ Model already loaded (no-op)
- ✅ Successful new model load
- ✅ Eviction triggering
- ✅ Cache flushing for large models
- ✅ Status reporting
- ✅ LRU access updates
- ✅ Manual model unload
- ✅ MemoryError on insufficient space

### test_integration.py
- ✅ Full workflow (load → check → evict → load)
- ✅ Singleton pattern verification
- ✅ Multi-model registration and eviction
- ✅ Priority-based protection
- ✅ LRU ordering maintenance
- ✅ Manual unload API
- ✅ Large model cache flushing

## Mocking Strategy

Tests use mocks for:
- **System calls**: `subprocess.run` for `free`, `ipcs`, `ipcrm`
- **File I/O**: PSI pressure files (`/proc/pressure/memory`)
- **Async operations**: `force_unload_model` utility
- **Config**: Model capabilities and settings

## Dependencies

Required packages (already in project):
```
pytest
pytest-asyncio
pytest-cov (optional, for coverage reports)
```

## CI/CD Integration

Add to your CI pipeline:
```yaml
- name: Run VRAM tests
  run: |
    cd fastapi-service
    pytest tests/test_vram/ -v --cov=app.services.vram
```

## Debugging Tests

Run with verbose output and print statements:
```bash
pytest tests/test_vram/ -v -s
```

Run with Python debugger on failure:
```bash
pytest tests/test_vram/ --pdb
```

## Performance Testing

For stress testing the orchestrator with many models:
```bash
pytest tests/test_vram/test_integration.py -v -k "test_model_registration_and_eviction"
```

## Success Criteria

All tests should pass with:
- ✅ No failures
- ✅ No warnings about unclosed resources
- ✅ Fast execution (<5 seconds for unit tests)
- ✅ Coverage >90% for orchestrator components
