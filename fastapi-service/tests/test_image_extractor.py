"""Unit tests for ImageExtractor."""
import pytest
from unittest.mock import Mock, AsyncMock
from pathlib import Path
import tempfile

from app.services.extractors.image_extractor import ImageExtractor


@pytest.fixture
def mock_ocr_service():
    """Create mock OCR service."""
    service = Mock()
    service.extract_text_from_image = AsyncMock()
    return service


@pytest.fixture
def image_extractor(mock_ocr_service):
    """Create ImageExtractor instance with mock OCR service."""
    return ImageExtractor(ocr_service=mock_ocr_service)


@pytest.fixture
def temp_image_file():
    """Create temporary test image file."""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        # Write minimal valid PNG header
        f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


class TestImageExtractor:
    """Test cases for ImageExtractor."""

    def test_supported_extensions(self, image_extractor):
        """Test that ImageExtractor reports correct supported extensions."""
        extensions = image_extractor.supported_extensions()

        assert isinstance(extensions, set)
        assert '.png' in extensions
        assert '.jpg' in extensions
        assert '.jpeg' in extensions
        assert '.gif' in extensions
        assert '.bmp' in extensions
        assert '.tiff' in extensions
        assert '.webp' in extensions

        # Should have leading dots
        for ext in extensions:
            assert ext.startswith('.')

    def test_supported_mime_types(self, image_extractor):
        """Test that ImageExtractor reports correct MIME types."""
        mime_types = image_extractor.supported_mime_types()

        assert isinstance(mime_types, set)
        assert 'image/png' in mime_types
        assert 'image/jpeg' in mime_types
        assert 'image/gif' in mime_types
        assert 'image/bmp' in mime_types
        assert 'image/tiff' in mime_types
        assert 'image/webp' in mime_types

    @pytest.mark.asyncio
    async def test_extract_success(self, image_extractor, mock_ocr_service, temp_image_file):
        """Test successful image text extraction."""
        # Mock OCR service response
        mock_ocr_service.extract_text_from_image.return_value = {
            'text': 'Login screen\nUsername: _____\nPassword: _____',
            'status': 'success'
        }

        result = await image_extractor.extract(temp_image_file, 'screenshot.png')

        # Verify OCR service was called with correct path
        mock_ocr_service.extract_text_from_image.assert_called_once_with(temp_image_file)

        # Verify result structure
        assert isinstance(result, dict)
        assert 'text' in result
        assert 'extractor' in result
        assert 'status' in result

        # Verify result values
        assert result['text'] == 'Login screen\nUsername: _____\nPassword: _____'
        assert result['extractor'] == 'image_ocr'
        assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_extract_ocr_failure(self, image_extractor, mock_ocr_service, temp_image_file):
        """Test OCR failure handling."""
        # Mock OCR service to raise exception
        mock_ocr_service.extract_text_from_image.side_effect = Exception("Ollama connection failed")

        result = await image_extractor.extract(temp_image_file, 'broken.png')

        # Verify result structure for error case
        assert isinstance(result, dict)
        assert 'text' in result
        assert 'extractor' in result
        assert 'status' in result

        # Verify error handling
        assert '[OCR processing failed:' in result['text']
        assert 'Ollama connection failed' in result['text']
        assert result['extractor'] == 'image_ocr'
        assert result['status'] == 'error'

    @pytest.mark.asyncio
    async def test_extract_empty_ocr_result(self, image_extractor, mock_ocr_service, temp_image_file):
        """Test handling of empty OCR results."""
        # Mock OCR service returning empty text
        mock_ocr_service.extract_text_from_image.return_value = {
            'text': '',
            'status': 'success'
        }

        result = await image_extractor.extract(temp_image_file, 'blank.png')

        # Verify empty text is handled correctly
        assert result['text'] == ''
        assert result['status'] == 'success'
        assert result['extractor'] == 'image_ocr'

    @pytest.mark.asyncio
    async def test_extract_with_unicode(self, image_extractor, mock_ocr_service, temp_image_file):
        """Test extraction with Unicode characters."""
        # Mock OCR service returning Unicode text
        mock_ocr_service.extract_text_from_image.return_value = {
            'text': 'Hello 世界 🌍 Emoji test',
            'status': 'success'
        }

        result = await image_extractor.extract(temp_image_file, 'unicode.png')

        # Verify Unicode is preserved
        assert result['text'] == 'Hello 世界 🌍 Emoji test'
        assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_extract_large_text(self, image_extractor, mock_ocr_service, temp_image_file):
        """Test extraction of large text content."""
        # Mock OCR service returning large text
        large_text = "Line of text\n" * 1000  # 1000 lines
        mock_ocr_service.extract_text_from_image.return_value = {
            'text': large_text,
            'status': 'success'
        }

        result = await image_extractor.extract(temp_image_file, 'document.png')

        # Verify large text is handled
        assert len(result['text']) == len(large_text)
        assert result['status'] == 'success'

    def test_initialization_with_ocr_service(self, mock_ocr_service):
        """Test ImageExtractor initialization with OCR service."""
        extractor = ImageExtractor(ocr_service=mock_ocr_service)

        # Verify OCR service is stored
        assert extractor.ocr_service is mock_ocr_service

    def test_liskov_substitution_principle(self, image_extractor):
        """Test that ImageExtractor can be used as IContentExtractor."""
        from app.services.extractors.interface import IContentExtractor

        # Verify ImageExtractor implements IContentExtractor
        assert isinstance(image_extractor, IContentExtractor)

        # Verify all required methods exist
        assert hasattr(image_extractor, 'supported_extensions')
        assert hasattr(image_extractor, 'supported_mime_types')
        assert hasattr(image_extractor, 'extract')

        # Verify methods are callable
        assert callable(image_extractor.supported_extensions)
        assert callable(image_extractor.supported_mime_types)
        assert callable(image_extractor.extract)
