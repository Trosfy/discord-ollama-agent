"""Unit tests for OCR Service."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import tempfile
import base64

from app.services.ocr_service import OCRService


@pytest.fixture
def ocr_service():
    """Create OCR service instance."""
    return OCRService(ollama_host="http://test-ollama:11434")


@pytest.fixture
def temp_image_file():
    """Create temporary test image file."""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        # Write some dummy image data
        f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_text_file():
    """Create temporary test text file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is test text content.\nLine 2.")
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


class TestOCRService:
    """Test cases for OCR Service."""

    @pytest.mark.asyncio
    async def test_extract_text_from_image_success(self, ocr_service, temp_image_file):
        """Test successful OCR text extraction."""
        # Mock Ollama API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'response': 'Extracted text from image'
        })

        # Create proper async context manager mock for post response
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__.return_value = mock_response
        mock_post_ctx.__aexit__.return_value = None

        # Create session mock with post method (NOT async, just returns context manager)
        mock_session_instance = Mock()
        mock_session_instance.post = Mock(return_value=mock_post_ctx)

        # Create ClientSession mock
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session_instance
        mock_session_ctx.__aexit__.return_value = None

        with patch('aiohttp.ClientSession', return_value=mock_session_ctx):
            result = await ocr_service.extract_text_from_image(temp_image_file)

            assert result['text'] == 'Extracted text from image'
            assert result['model'] == 'ministral-3:14b'
            assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_extract_text_from_image_ollama_error(self, ocr_service, temp_image_file):
        """Test OCR with Ollama API error."""
        # Mock Ollama API error response
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")

        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response

            result = await ocr_service.extract_text_from_image(temp_image_file)

            assert 'OCR processing failed' in result['text']
            assert result['status'] == 'error'

    @pytest.mark.asyncio
    async def test_extract_text_from_image_file_not_found(self, ocr_service):
        """Test OCR with non-existent file."""
        result = await ocr_service.extract_text_from_image('/nonexistent/image.png')

        assert 'OCR processing failed' in result['text']
        assert result['status'] == 'error'

    @pytest.mark.asyncio
    async def test_analyze_document_image(self, ocr_service, temp_image_file):
        """Test document analysis with image file."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'response': 'Image text content'
        })

        # Create proper async context manager mock for post response
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__.return_value = mock_response
        mock_post_ctx.__aexit__.return_value = None

        # Create session mock with post method (NOT async, just returns context manager)
        mock_session_instance = Mock()
        mock_session_instance.post = Mock(return_value=mock_post_ctx)

        # Create ClientSession mock
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session_instance
        mock_session_ctx.__aexit__.return_value = None

        with patch('aiohttp.ClientSession', return_value=mock_session_ctx):
            result = await ocr_service.analyze_document(temp_image_file, 'image/png')

            assert result['text'] == 'Image text content'
            assert result['model'] == 'ministral-3:14b'

    @pytest.mark.asyncio
    async def test_analyze_document_text_file(self, ocr_service, temp_text_file):
        """Test document analysis with text file (direct read)."""
        result = await ocr_service.analyze_document(temp_text_file, 'text/plain')

        assert 'This is test text content' in result['text']
        assert result['model'] == 'direct_read'
        assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_analyze_document_markdown_file(self, ocr_service):
        """Test document analysis with markdown file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test Markdown\n\nContent here.")
            temp_path = f.name

        try:
            result = await ocr_service.analyze_document(temp_path, 'text/markdown')

            assert '# Test Markdown' in result['text']
            assert result['model'] == 'direct_read'
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_analyze_document_unsupported_type(self, ocr_service):
        """Test document analysis with unsupported file type."""
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as f:
            f.write(b'\x00\x01\x02')
            temp_path = f.name

        try:
            result = await ocr_service.analyze_document(temp_path, 'application/octet-stream')

            assert 'Unsupported file type' in result['text']
            assert result['model'] == 'none'
            assert result['status'] == 'unsupported'
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_ocr_service_initialization(self):
        """Test OCR service initializes correctly."""
        service = OCRService(ollama_host="http://custom-host:1234")

        assert service.ollama_host == "http://custom-host:1234"
        assert service.ocr_model == "ministral-3:14b"

    @pytest.mark.asyncio
    async def test_extract_text_preserves_layout(self, ocr_service, temp_image_file):
        """Test that OCR prompt asks to preserve layout."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'response': 'Line 1\nLine 2\nLine 3'
        })

        # Create proper async context manager mock for post response
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__.return_value = mock_response
        mock_post_ctx.__aexit__.return_value = None

        # Create session mock with post method (NOT async, just returns context manager)
        mock_session_instance = Mock()
        mock_session_instance.post = Mock(return_value=mock_post_ctx)

        # Create ClientSession mock
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session_instance
        mock_session_ctx.__aexit__.return_value = None

        with patch('aiohttp.ClientSession', return_value=mock_session_ctx):
            result = await ocr_service.extract_text_from_image(temp_image_file)

            # Verify the prompt includes layout preservation
            call_args = mock_session_instance.post.call_args
            payload = call_args[1]['json']
            assert 'Preserve the layout and structure' in payload['prompt']
            assert payload['model'] == 'ministral-3:14b'
