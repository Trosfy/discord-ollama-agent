# Admin Service Tests

Comprehensive unit and integration tests for the admin-service.

## Test Structure

- **test_auth_middleware.py**: Tests for JWT and Discord token authentication (10 tests)
- **test_vram_client.py**: Tests for VRAMClient with mocked HTTP responses (8 tests)
- **test_model_service.py**: Tests for ModelService business logic (10 tests)
- **test_user_service.py**: Tests for UserService business logic (10 tests)
- **test_api_endpoints.py**: Integration tests for all API endpoints (16 tests)

## Running Tests

### Install dependencies

```bash
cd admin-service
uv pip install -e ".[dev]"  # or: pip install -e ".[dev]"
```

### Run all tests

```bash
pytest
```

### Run specific test file

```bash
pytest tests/test_auth_middleware.py
pytest tests/test_vram_client.py
pytest tests/test_model_service.py
pytest tests/test_user_service.py
pytest tests/test_api_endpoints.py
```

### Run with coverage

```bash
pytest --cov=app --cov-report=html
```

### Run specific test class

```bash
pytest tests/test_auth_middleware.py::TestJWTVerification
```

### Run specific test method

```bash
pytest tests/test_auth_middleware.py::TestJWTVerification::test_valid_jwt_token_admin_role
```

## Test Coverage

- ✅ **Auth middleware** (JWT + Discord tokens) - 10 tests
- ✅ **VRAMClient** HTTP methods - 8 tests
- ✅ **ModelService** business logic with audit logging - 10 tests
- ✅ **UserService** business logic (grant/ban/unban/stats) - 10 tests
- ✅ **API endpoints** (models/vram/users) - 16 integration tests
- ✅ **Authorization** checks (401 for missing auth)
- ✅ **Error handling** (HTTP errors, validation, not found)
- ✅ **Audit logging** verification in all service tests

**Total: 54 test cases**

## Environment Variables for Testing

The tests use default test values. To customize:

```bash
export JWT_SECRET="test-jwt-secret"
export BOT_SECRET="test-bot-secret"
export INTERNAL_API_KEY="test-internal-key"
```

## Mock Strategy

- **HTTP calls**: Mocked using `unittest.mock.patch`
- **DynamoDB**: Services mocked at service layer
- **Authentication**: Real JWT generation/verification with test secrets

## CI/CD Integration

These tests are designed to run in CI pipelines:

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    cd admin-service
    pytest --cov=app --cov-report=xml
```
