# RAG Implementation Test Suite

This directory contains comprehensive tests for the RAG (Retrieval-Augmented Generation) implementation, including LangChain chunking, Ollama embeddings, DynamoDB vector storage, and RAG-enhanced web scraping.

## Test Files

### 1. `test_chunking_service.py`
Tests for LangChain-based text chunking service.

**Coverage:**
- Basic text chunking with tiktoken token counting
- Chunk overlap verification
- Token count accuracy
- Empty text validation
- Custom chunk size and overlap parameters
- Long document handling
- Special character and unicode support
- Unique chunk ID generation
- Structure preservation during chunking

**Key Tests:**
- `test_chunk_text_basic` - Verifies basic chunking functionality
- `test_chunk_text_overlap` - Ensures proper overlap between chunks
- `test_chunk_text_token_count_accuracy` - Validates token counting
- `test_chunk_text_empty_raises_error` - Error handling for empty input
- `test_chunk_text_long_document` - Performance with large documents
- `test_chunk_text_special_characters` - Unicode and special char handling

### 2. `test_embedding_service.py`
Tests for Ollama embedding service with mocked API calls.

**Coverage:**
- Single text embedding generation
- Batch embedding processing
- HTTP error handling (500, timeout, connection errors)
- Empty text validation
- Partial batch failure handling
- Long text support
- Special character embedding
- API call verification

**Key Tests:**
- `test_embed_text_success` - Successful embedding generation
- `test_embed_batch_success` - Batch processing functionality
- `test_embed_text_http_error` - HTTP error recovery
- `test_embed_batch_partial_failure` - Handling batch failures
- `test_embed_text_timeout` - Timeout handling
- `test_embed_batch_large_batch` - Scalability testing (50 texts)

### 3. `test_vector_storage.py`
Tests for DynamoDB vector storage with TTL support.

**Coverage:**
- URL hashing (SHA256)
- Cosine similarity calculation
- Table initialization with TTL
- Chunk storage with batch writes
- Cache hit/miss retrieval
- TTL expiration filtering
- Similar chunk search with client-side similarity
- Empty/invalid input validation

**Key Tests:**
- `test_hash_url` - URL hashing consistency
- `test_cosine_similarity` - Vector similarity computation
- `test_store_chunks_success` - Chunk storage with TTL
- `test_get_chunks_by_url_success` - Cache retrieval
- `test_get_chunks_by_url_expired_chunks` - TTL expiration handling
- `test_search_similar_success` - Similarity search ranking

### 4. `test_web_tools_rag.py`
Integration tests for RAG-enhanced web scraping.

**Coverage:**
- Complete RAG pipeline (fetch → chunk → embed → store)
- Cache hit/miss scenarios
- Cache disable option
- HTTP error handling (404, 500)
- Timeout handling with retry
- Insufficient content detection
- WAF bypass headers generation
- Retry mechanism with exponential backoff
- User-Agent pool validation

**Key Tests:**
- `test_fetch_webpage_cache_miss_full_pipeline` - Full RAG workflow
- `test_fetch_webpage_cache_hit` - Cached response retrieval
- `test_fetch_webpage_cache_disabled` - Bypass cache functionality
- `test_fetch_webpage_http_error` - Error recovery
- `test_fetch_with_retry_rate_limit_retry` - 429 rate limit handling
- `test_fetch_with_retry_exhausted` - Retry exhaustion

## Running Tests

### Run All RAG Tests
```bash
cd fastapi-service
pytest tests/test_chunking_service.py tests/test_embedding_service.py tests/test_vector_storage.py tests/test_web_tools_rag.py -v
```

### Run Specific Test File
```bash
pytest tests/test_chunking_service.py -v
```

### Run Specific Test
```bash
pytest tests/test_chunking_service.py::test_chunk_text_basic -v
```

### Run with Coverage
```bash
pytest tests/test_*rag*.py --cov=app.services --cov=app.implementations --cov=app.tools --cov-report=html
```

### Run Only Fast Tests (Skip Slow Integration Tests)
```bash
pytest tests/test_chunking_service.py tests/test_embedding_service.py tests/test_vector_storage.py -v
```

## Test Statistics

| Test File | Test Count | Lines of Code | Coverage |
|-----------|------------|---------------|----------|
| `test_chunking_service.py` | 14 tests | ~350 lines | Chunking service |
| `test_embedding_service.py` | 15 tests | ~400 lines | Embedding service |
| `test_vector_storage.py` | 15 tests | ~450 lines | Vector storage |
| `test_web_tools_rag.py` | 13 tests | ~500 lines | Web tools integration |
| **Total** | **57 tests** | **~1,700 lines** | **All RAG components** |

## Test Fixtures

### Common Fixtures

**`chunking_service`** - LangChainChunkingService instance with test parameters
```python
@pytest.fixture
def chunking_service():
    return LangChainChunkingService(chunk_size=100, chunk_overlap=20)
```

**`embedding_service`** - OllamaEmbeddingService instance
```python
@pytest.fixture
def embedding_service():
    return OllamaEmbeddingService(
        model="qwen3-embedding:4b",
        base_url="http://localhost:11434"
    )
```

**`vector_storage`** - DynamoDBVectorStorage instance
```python
@pytest.fixture
def vector_storage():
    return DynamoDBVectorStorage()
```

**`sample_chunks`** - Sample chunk data for testing
```python
@pytest.fixture
def sample_chunks():
    return [
        {
            "chunk_id": "chunk-1",
            "chunk_text": "First chunk",
            "embedding_vector": [0.1] * 1024,
            "chunk_index": 0,
            "token_count": 5
        },
        # ...
    ]
```

## Mocking Strategy

### HTTP Requests (httpx)
```python
with patch('httpx.AsyncClient') as mock_client:
    mock_instance = AsyncMock()
    mock_instance.post.return_value = mock_response
    mock_client.return_value = mock_instance
```

### DynamoDB (aioboto3)
```python
with patch('aioboto3.Session') as mock_session:
    mock_dynamodb = AsyncMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_session_instance.resource.return_value = mock_dynamodb
```

### Async Sleep (for retry tests)
```python
with patch('asyncio.sleep') as mock_sleep:
    mock_sleep.return_value = None
```

## Test Patterns

### Testing Async Functions
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None
```

### Testing Error Handling
```python
with pytest.raises(ValueError, match="expected error message"):
    await function_that_raises()
```

### Testing with Mocks
```python
with patch('module.dependency') as mock_dep:
    mock_dep.return_value = expected_value
    result = function_under_test()
    mock_dep.assert_called_once()
```

## Debugging Failed Tests

### View Detailed Output
```bash
pytest tests/test_chunking_service.py -v -s
```

### Run Single Test with Debug
```bash
pytest tests/test_chunking_service.py::test_chunk_text_basic -v -s --pdb
```

### Check Coverage for Specific Module
```bash
pytest tests/test_chunking_service.py --cov=app.services.chunking_service --cov-report=term-missing
```

## Dependencies Required

### Test Dependencies
- `pytest>=7.4.3` - Test framework
- `pytest-asyncio>=0.21.1` - Async test support
- `httpx>=0.25.2` - HTTP client for mocking
- `moto[dynamodb]>=4.2.0` - AWS mocking (for future integration tests)

### Production Dependencies (tested)
- `langchain>=0.1.0` - Text splitting
- `langchain-text-splitters>=0.0.1` - RecursiveCharacterTextSplitter
- `tiktoken>=0.5.1` - Token counting
- `httpx>=0.27.0` - HTTP/2 client
- `beautifulsoup4>=4.12.0` - HTML parsing
- `aioboto3>=15.5.0` - DynamoDB async client

## Integration Test Requirements

For full integration testing (not mocked):

1. **Ollama Running**: `ollama serve`
2. **Embedding Model**: `ollama pull qwen3-embedding:4b`
3. **DynamoDB Local**: Docker container running
4. **Environment Variables**: Properly configured in `.env`

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run RAG Tests
  run: |
    cd fastapi-service
    pytest tests/test_chunking_service.py \
           tests/test_embedding_service.py \
           tests/test_vector_storage.py \
           tests/test_web_tools_rag.py \
           --cov --cov-report=xml
```

### Test Matrix
- Python 3.11, 3.12
- Multiple OS: Ubuntu, macOS
- Fast tests only (mocked dependencies)

## Known Limitations

1. **Client-Side Similarity**: DynamoDB vector search uses client-side cosine similarity (full table scan). For production scale, migrate to Pinecone/Weaviate/pgvector.

2. **Mock Testing**: Most tests use mocks to avoid external dependencies. Integration tests with real Ollama/DynamoDB should be run separately.

3. **Async Context**: Tests use `asyncio.run()` for compatibility. In production, services run in FastAPI's async context.

## Future Test Additions

- [ ] Load testing (1000+ chunks)
- [ ] Concurrent request handling
- [ ] Memory leak detection
- [ ] Real Ollama integration tests
- [ ] DynamoDB Local integration tests
- [ ] End-to-end user flow tests
- [ ] Performance benchmarks
- [ ] Error recovery scenarios

## Troubleshooting

### Import Errors
```bash
# Ensure you're in the correct directory
cd fastapi-service
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Async Test Failures
```bash
# Install pytest-asyncio
pip install pytest-asyncio
# Or with uv
uv pip install pytest-asyncio
```

### Mock Not Found
```bash
# Verify unittest.mock is available (Python 3.3+)
python -c "from unittest.mock import MagicMock; print('OK')"
```

## Contact & Support

For issues or questions about the RAG test suite:
- Check test logs: `pytest tests/test_*rag*.py -v -s`
- Review implementation: See docstrings in test files
- Check plan: `/home/trosfy/.claude/plans/cached-kindling-nest.md`
