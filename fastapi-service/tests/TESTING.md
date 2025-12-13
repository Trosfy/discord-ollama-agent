# Router Service Testing Guide

## Overview

Comprehensive test suite for the intelligent router service that classifies requests and routes them to specialized models.

## Test Files

### 1. `test_router_service.py` - Unit Tests (180 lines)

Tests the router service in isolation with mocked dependencies.

**Test Classes**:

- **`TestRouterClassification`** - Tests classification accuracy
  - `test_classify_self_handle_simple_question` - "What is Python?" → SELF_HANDLE
  - `test_classify_self_handle_explanation` - "Explain HTTP" → SELF_HANDLE
  - `test_classify_simple_code_basic_function` - "Write a function" → SIMPLE_CODE
  - `test_classify_simple_code_complex_task` - "Design a distributed caching system" → SIMPLE_CODE
  - `test_classify_simple_code_bug_fix` - "Fix this syntax error" → SIMPLE_CODE
  - `test_classify_reasoning_comparison` - "Compare React vs Vue" → REASONING
  - `test_classify_reasoning_analysis` - "Analyze microservices" → REASONING
  - `test_classify_reasoning_research` - "Research auth best practices" → REASONING

- **`TestRouterFallback`** - Tests fallback behavior
  - `test_fallback_invalid_route_name` - Invalid route → REASONING
  - `test_fallback_classification_exception` - Exception → REASONING
  - `test_fallback_partial_match` - Extracts route from verbose response

- **`TestRouterConfiguration`** - Tests model configuration
  - `test_get_model_for_self_handle` - Verifies gpt-oss:20b config
  - `test_get_model_for_simple_code` - Verifies qwen2.5-coder:7b config
  - `test_get_model_for_reasoning` - Verifies deepseek-r1:8b config

- **`TestEdgeCases`** - Tests boundary conditions
  - `test_ambiguous_explanation_vs_code` - Ambiguous queries
  - `test_decision_question_routes_to_reasoning` - "Should I" questions
  - `test_empty_message` - Empty string handling
  - `test_very_long_message` - Long message handling

- **`TestClassificationPrompt`** - Tests prompt structure
  - `test_classification_prompt_contains_routes` - All routes present
  - `test_classification_prompt_has_examples` - Examples included
  - `test_classification_prompt_single_output` - Requests single output

### 2. `test_router_integration.py` - Integration Tests (370 lines)

Tests the full routing pipeline from orchestrator to LLM generation.

**Test Classes**:

- **`TestRouterIntegration`** - End-to-end routing flow
  - `test_self_handle_route_flow` - Full SELF_HANDLE pipeline
  - `test_simple_code_route_flow` - Full SIMPLE_CODE pipeline
  - `test_reasoning_route_flow` - Full REASONING pipeline with references
  - `test_router_fallback_in_orchestrator` - Fallback handling in orchestrator

- **`TestRouteSystemPrompts`** - Route-specific prompts
  - `test_self_handle_uses_conversational_prompt` - Conversational, 500 word limit
  - `test_simple_code_uses_coding_prompt` - Coding principles, 1000 word limit
  - `test_reasoning_uses_analytical_prompt` - Analytical, 1500 word limit
  - `test_custom_user_prompt_appended` - User custom prompts appended
  - `test_invalid_route_type_falls_back` - Invalid route → general prompt

- **`TestModelLifecycleManagement`** - Model loading/unloading
  - `test_ollama_keep_alive_configured` - OLLAMA_KEEP_ALIVE=0
  - `test_router_model_unloads_before_execution` - Sequential model loading
  - `test_route_models_configured_correctly` - Existing models used

- **`TestReferenceCapture`** - Reference tracking
  - `test_references_captured_in_reasoning_route` - Web references appended

## Running Tests

### Best Practice: Using Test Script (Recommended)

```bash
# From repository root
./scripts/run-tests.sh
```

This script:
- Uses a separate test service that doesn't pollute production containers
- Installs dev dependencies (pytest, pytest-asyncio) only in test container
- Runs all tests with proper environment setup

### Using Docker Compose Test Configuration

```bash
# From repository root
docker-compose -f docker-compose.yml -f docker-compose.test.yml run --rm fastapi-service-test
```

### Run All Router Tests Directly (If pytest installed)

```bash
# From fastapi-service directory (only if pytest already installed)
pytest tests/test_router_service.py tests/test_router_integration.py -v
```

### Run Specific Test Class

```bash
# Run only classification tests
pytest tests/test_router_service.py::TestRouterClassification -v

# Run only integration tests
pytest tests/test_router_integration.py::TestRouterIntegration -v
```

### Run Specific Test

```bash
# Run single test
pytest tests/test_router_service.py::TestRouterClassification::test_classify_self_handle_simple_question -v
```

### Run with Coverage

```bash
# Install coverage if not already installed
pip install pytest-cov

# Run with coverage report
pytest tests/test_router_service.py tests/test_router_integration.py --cov=app.services.router_service --cov-report=term-missing
```

### Run All Tests (Including Existing Tests)

```bash
# Run entire test suite
pytest tests/ -v
```

## Test Coverage

### Router Service (`router_service.py`)
- ✅ Classification logic (`classify_request`)
- ✅ Route configuration (`get_model_for_route`)
- ✅ Fallback behavior (invalid routes, exceptions)
- ✅ Edge cases (empty messages, long messages, ambiguous queries)
- ✅ Classification prompt structure

### Orchestrator Integration
- ✅ Router service injection
- ✅ Request classification flow
- ✅ Route-based LLM generation
- ✅ Reference appending
- ✅ Fallback handling

### StrandsLLM Integration
- ✅ Route-specific system prompts
- ✅ `generate_with_route()` method
- ✅ Custom user prompt appending
- ✅ Invalid route fallback

### Configuration
- ✅ OLLAMA_KEEP_ALIVE setting
- ✅ Route model configurations
- ✅ Existing models used (no new downloads)

## Expected Test Results

All tests should pass with the following outcomes:

### Classification Tests (8 tests)
- Simple questions → SELF_HANDLE
- Coding tasks → SIMPLE_CODE
- Analysis/comparisons → REASONING

### Fallback Tests (3 tests)
- Invalid route → REASONING
- Exceptions → REASONING
- Partial matches extracted correctly

### Integration Tests (9 tests)
- Full pipeline for each route
- Correct models used
- References appended
- Prompts optimized

### Total: 37 tests

## Continuous Integration

To integrate into CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
- name: Run Router Tests
  run: |
    cd fastapi-service
    pip install -r requirements.txt
    pytest tests/test_router_service.py tests/test_router_integration.py --cov=app.services.router_service
```

## Troubleshooting

### Import Errors

If you encounter import errors, ensure `PYTHONPATH` includes the shared directory:

```bash
export PYTHONPATH=/shared:$PYTHONPATH
pytest tests/
```

### AsyncIO Warnings

If you see asyncio warnings, verify `pytest.ini` has:

```ini
[pytest]
asyncio_mode = auto
```

### Missing Dependencies

Install test dependencies:

```bash
pip install pytest pytest-asyncio pytest-cov
```

## Manual Testing Checklist

For end-to-end validation with actual models:

### SELF_HANDLE Route
- [ ] Query: "What is HTTP?"
- [ ] Expected: General explanation, < 10s response time
- [ ] Model: gpt-oss:20b

### SIMPLE_CODE Route
- [ ] Query: "Write a Python function to reverse a string"
- [ ] Expected: Valid Python code, < 15s response time
- [ ] Model: qwen2.5-coder:7b

### REASONING Route
- [ ] Query: "Compare SQL vs NoSQL databases"
- [ ] Expected: Structured analysis, < 30s response time, references appended
- [ ] Model: deepseek-r1:8b

### Fallback Behavior
- [ ] Query: Ambiguous or unclear request
- [ ] Expected: Routes to REASONING (most capable default)
- [ ] Model: deepseek-r1:8b

### Model Lifecycle
- [ ] Verify only 1 model loaded at a time using `ollama ps`
- [ ] Check logs for model load/unload events

## Future Test Additions

Potential tests to add as system evolves:

1. **Performance Tests**: Measure classification latency
2. **Load Tests**: Concurrent request handling
3. **Model Accuracy Tests**: Classification accuracy against labeled dataset
4. **A/B Testing**: Compare old vs new routing system
5. **Chaos Tests**: Model unavailability, timeout handling
6. **Memory Tests**: Verify model unloading frees GPU memory

## Contributing

When adding new routes or modifying router logic:

1. Add unit tests to `test_router_service.py`
2. Add integration tests to `test_router_integration.py`
3. Update this documentation
4. Run full test suite before committing
5. Ensure all tests pass
