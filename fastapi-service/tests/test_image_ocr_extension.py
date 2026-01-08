"""
Unit tests for ImageOCRExtension.

Tests cover:
- OCR enhancement for image files
- Image file type detection
- Pre-extracted OCR lookup from file_refs
- Graceful OCR failure handling
- Pass-through for non-image files
"""
import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from typing import Dict

from app.extensions.image_ocr_extension import ImageOCRExtension
from strands.types.tools import ToolResult


# Fixtures
@pytest.fixture
def ocr_extension():
    """Create ImageOCRExtension instance."""
    return ImageOCRExtension()


@pytest.fixture
def sample_request_context() -> Dict:
    """Sample request context without file_refs."""
    return {
        'user_id': 'user123',
        'channel_id': 'channel456',
        'message_id': 'message789',
        'file_refs': []
    }


@pytest.fixture
def sample_request_context_with_ocr() -> Dict:
    """Sample request context with pre-extracted OCR in file_refs."""
    return {
        'user_id': 'user123',
        'channel_id': 'channel456',
        'file_refs': [
            {
                'file_id': 'img001',
                'filename': 'screenshot.png',
                'storage_path': '/tmp/discord-bot-uploads/screenshot.png',
                'extracted_content': 'Hello World\nThis is extracted text from image'
            }
        ]
    }


@pytest.fixture
def sample_request_context_no_ocr() -> Dict:
    """Sample request context with file_refs but no OCR content."""
    return {
        'user_id': 'user123',
        'file_refs': [
            {
                'file_id': 'img002',
                'filename': 'diagram.png',
                'storage_path': '/tmp/discord-bot-uploads/diagram.png',
                'extracted_content': '[No content extracted]'
            }
        ]
    }


@pytest.fixture
def image_file_read_result() -> ToolResult:
    """Sample file_read ToolResult for image file."""
    return {
        'status': 'success',
        'toolUseId': 'test-img-read',
        'content': [
            {
                'type': 'text',
                'text': 'File: /tmp/discord-bot-uploads/screenshot.png Type: PNG Size: 2.3MB'
            }
        ]
    }


@pytest.fixture
def text_file_read_result() -> ToolResult:
    """Sample file_read ToolResult for text file."""
    return {
        'status': 'success',
        'toolUseId': 'test-txt-read',
        'content': [
            {
                'type': 'text',
                'text': 'File: /tmp/notes.txt Type: text/plain Size: 1.2KB'
            }
        ]
    }


@pytest.fixture
def pdf_file_read_result() -> ToolResult:
    """Sample file_read ToolResult for PDF file."""
    return {
        'status': 'success',
        'toolUseId': 'test-pdf-read',
        'content': [
            {
                'type': 'text',
                'text': 'File: /tmp/document.pdf Type: PDF Content: Lorem ipsum...'
            }
        ]
    }


@pytest.fixture
def temp_image_file():
    """Create temporary image file for testing."""
    # Create a minimal PNG file (1x1 pixel)
    png_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00'
        b'\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx'
        b'\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    )

    with tempfile.NamedTemporaryFile(
        mode='wb',
        suffix='.png',
        delete=False,
        dir='/tmp'
    ) as f:
        f.write(png_data)
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


# ImageOCRExtension.on_file_read Tests
class TestImageOCRExtensionOnFileRead:
    """Tests for ImageOCRExtension.on_file_read()."""

    def test_on_file_read_adds_ocr_for_image(
        self,
        ocr_extension,
        sample_request_context_with_ocr,
        temp_image_file
    ):
        """Test on_file_read adds OCR text for image files."""
        # Update context and result to use temp file
        sample_request_context_with_ocr['file_refs'][0]['storage_path'] = temp_image_file

        image_file_read_result = {
            'status': 'success',
            'toolUseId': 'test-img-read',
            'content': [
                {
                    'type': 'text',
                    'text': f'File: {temp_image_file} Type: PNG Size: 1KB'
                }
            ]
        }

        # Save original length before mutation
        original_length = len(image_file_read_result['content'])

        result = ocr_extension.on_file_read(
            image_file_read_result,
            sample_request_context_with_ocr
        )

        # Should add OCR content block
        assert len(result['content']) > original_length
        assert len(result['content']) == 2  # Original + OCR

        # Check OCR text was appended
        ocr_block = result['content'][-1]
        assert 'OCR Extracted Text' in ocr_block['text']
        assert 'Hello World' in ocr_block['text']
        assert 'This is extracted text from image' in ocr_block['text']

    def test_on_file_read_skips_non_image_files(
        self,
        ocr_extension,
        text_file_read_result,
        sample_request_context
    ):
        """Test on_file_read skips OCR for non-image files."""
        original_content_length = len(text_file_read_result['content'])

        result = ocr_extension.on_file_read(
            text_file_read_result,
            sample_request_context
        )

        # Should not modify content (not an image)
        assert len(result['content']) == original_content_length
        assert result == text_file_read_result

    def test_on_file_read_skips_pdf_files(
        self,
        ocr_extension,
        pdf_file_read_result,
        sample_request_context
    ):
        """Test on_file_read skips OCR for PDF files."""
        original_content_length = len(pdf_file_read_result['content'])

        result = ocr_extension.on_file_read(
            pdf_file_read_result,
            sample_request_context
        )

        # Should not add OCR (PDF not an image)
        assert len(result['content']) == original_content_length

    def test_on_file_read_handles_missing_ocr_gracefully(
        self,
        ocr_extension,
        image_file_read_result,
        sample_request_context_no_ocr
    ):
        """Test on_file_read handles missing OCR content gracefully."""
        original_content_length = len(image_file_read_result['content'])

        result = ocr_extension.on_file_read(
            image_file_read_result,
            sample_request_context_no_ocr
        )

        # Should not crash, just log warning
        # Content should remain unchanged (no OCR to add)
        assert len(result['content']) == original_content_length

    def test_on_file_read_handles_empty_file_refs(
        self,
        ocr_extension,
        image_file_read_result,
        sample_request_context
    ):
        """Test on_file_read handles empty file_refs list."""
        result = ocr_extension.on_file_read(
            image_file_read_result,
            sample_request_context
        )

        # Should not crash
        # No OCR content to add (no file_refs)
        assert result['status'] == 'success'

    def test_on_file_read_preserves_original_content(
        self,
        ocr_extension,
        image_file_read_result,
        sample_request_context_with_ocr
    ):
        """Test on_file_read preserves original content blocks."""
        original_content = image_file_read_result['content'][0].copy()

        result = ocr_extension.on_file_read(
            image_file_read_result,
            sample_request_context_with_ocr
        )

        # Original content should be unchanged
        assert result['content'][0] == original_content

    def test_on_file_read_with_no_file_path(
        self,
        ocr_extension,
        sample_request_context
    ):
        """Test on_file_read handles ToolResult with no file path."""
        no_path_result: ToolResult = {
            'status': 'success',
            'toolUseId': 'test-no-path',
            'content': [
                {
                    'type': 'text',
                    'text': 'Some content without file path'
                }
            ]
        }

        result = ocr_extension.on_file_read(
            no_path_result,
            sample_request_context
        )

        # Should return unchanged (can't determine file type)
        assert result == no_path_result

    def test_on_file_read_with_error_result(
        self,
        ocr_extension,
        sample_request_context_with_ocr
    ):
        """Test on_file_read handles error ToolResult."""
        error_result: ToolResult = {
            'status': 'error',
            'toolUseId': 'test-error',
            'content': [
                {
                    'type': 'text',
                    'text': 'Error: File not found: /tmp/missing.png'
                }
            ]
        }

        result = ocr_extension.on_file_read(
            error_result,
            sample_request_context_with_ocr
        )

        # Should still process (extension can handle errors)
        assert result['status'] == 'error'


# ImageOCRExtension.on_file_write Tests
class TestImageOCRExtensionOnFileWrite:
    """Tests for ImageOCRExtension.on_file_write()."""

    def test_on_file_write_is_noop(
        self,
        ocr_extension,
        sample_request_context
    ):
        """Test on_file_write is a no-op (OCR only for reading)."""
        write_result: ToolResult = {
            'status': 'success',
            'toolUseId': 'test-write',
            'content': [
                {'type': 'text', 'text': 'File written'}
            ]
        }

        # Should not raise exception
        result = ocr_extension.on_file_write(
            write_result,
            sample_request_context
        )

        # Should return None (no-op)
        assert result is None

        # Context should be unchanged
        assert 'artifacts_created' not in sample_request_context


# Image File Detection Tests
class TestImageFileDetection:
    """Tests for _is_image_file() method."""

    @pytest.mark.parametrize("filename,expected", [
        ('/tmp/photo.png', True),
        ('/tmp/photo.PNG', True),
        ('/tmp/photo.jpg', True),
        ('/tmp/photo.JPG', True),
        ('/tmp/photo.jpeg', True),
        ('/tmp/photo.JPEG', True),
        ('/tmp/photo.gif', True),
        ('/tmp/photo.GIF', True),
        ('/tmp/photo.bmp', True),
        ('/tmp/photo.BMP', True),
        ('/tmp/photo.tiff', True),
        ('/tmp/photo.TIFF', True),
        ('/tmp/photo.webp', True),
        ('/tmp/photo.WEBP', True),
        ('/tmp/document.txt', False),
        ('/tmp/document.pdf', False),
        ('/tmp/script.py', False),
        ('/tmp/data.json', False),
        ('/tmp/archive.zip', False),
        ('/tmp/video.mp4', False),
        ('/tmp/audio.mp3', False),
        ('/tmp/no_extension', False),
    ])
    def test_is_image_file(
        self,
        ocr_extension,
        filename,
        expected
    ):
        """Test image file detection by extension."""
        result = ocr_extension._is_image_file(filename)
        assert result == expected


# Pre-extracted OCR Lookup Tests
class TestPreExtractedOCRLookup:
    """Tests for _get_preextracted_ocr() method."""

    def test_get_preextracted_ocr_finds_matching_file(
        self,
        ocr_extension,
        sample_request_context_with_ocr
    ):
        """Test OCR lookup finds matching file in file_refs."""
        file_path = '/tmp/discord-bot-uploads/screenshot.png'

        ocr_text = ocr_extension._get_preextracted_ocr(
            file_path,
            sample_request_context_with_ocr
        )

        assert ocr_text is not None
        assert 'Hello World' in ocr_text
        assert 'This is extracted text from image' in ocr_text

    def test_get_preextracted_ocr_returns_none_for_no_match(
        self,
        ocr_extension,
        sample_request_context_with_ocr
    ):
        """Test OCR lookup returns None when no matching file."""
        file_path = '/tmp/other-file.png'  # Not in file_refs

        ocr_text = ocr_extension._get_preextracted_ocr(
            file_path,
            sample_request_context_with_ocr
        )

        assert ocr_text is None

    def test_get_preextracted_ocr_returns_none_for_no_content(
        self,
        ocr_extension,
        sample_request_context_no_ocr
    ):
        """Test OCR lookup returns None when content is [No content extracted]."""
        file_path = '/tmp/discord-bot-uploads/diagram.png'

        ocr_text = ocr_extension._get_preextracted_ocr(
            file_path,
            sample_request_context_no_ocr
        )

        assert ocr_text is None

    def test_get_preextracted_ocr_returns_none_for_empty_file_refs(
        self,
        ocr_extension,
        sample_request_context
    ):
        """Test OCR lookup returns None when file_refs is empty."""
        file_path = '/tmp/some-file.png'

        ocr_text = ocr_extension._get_preextracted_ocr(
            file_path,
            sample_request_context
        )

        assert ocr_text is None

    def test_get_preextracted_ocr_handles_missing_file_refs_key(
        self,
        ocr_extension
    ):
        """Test OCR lookup handles missing file_refs key in context."""
        context_without_file_refs = {
            'user_id': 'user123',
            # No 'file_refs' key
        }
        file_path = '/tmp/some-file.png'

        ocr_text = ocr_extension._get_preextracted_ocr(
            file_path,
            context_without_file_refs
        )

        assert ocr_text is None


# File Path Extraction Tests
class TestFilePathExtraction:
    """Tests for _extract_file_path() method."""

    def test_extract_file_path_from_text_with_absolute_path(
        self,
        ocr_extension,
        temp_image_file
    ):
        """Test file path extraction from text content."""
        tool_result: ToolResult = {
            'status': 'success',
            'content': [
                {
                    'type': 'text',
                    'text': f'Reading file: {temp_image_file}'
                }
            ]
        }

        path = ocr_extension._extract_file_path(tool_result)
        assert path == temp_image_file

    def test_extract_file_path_from_path_key(
        self,
        ocr_extension,
        temp_image_file
    ):
        """Test file path extraction from 'path' key in content block."""
        tool_result: ToolResult = {
            'status': 'success',
            'content': [
                {
                    'type': 'text',
                    'text': 'File content',
                    'path': temp_image_file
                }
            ]
        }

        path = ocr_extension._extract_file_path(tool_result)
        assert path == temp_image_file

    def test_extract_file_path_strips_punctuation(
        self,
        ocr_extension,
        temp_image_file
    ):
        """Test file path extraction strips trailing punctuation."""
        tool_result: ToolResult = {
            'status': 'success',
            'content': [
                {
                    'type': 'text',
                    'text': f'Reading: {temp_image_file}.'  # Trailing period
                }
            ]
        }

        path = ocr_extension._extract_file_path(tool_result)
        assert path == temp_image_file
        assert not path.endswith('.')

    def test_extract_file_path_returns_none_for_no_path(
        self,
        ocr_extension
    ):
        """Test file path extraction returns None when no path found."""
        tool_result: ToolResult = {
            'status': 'success',
            'content': [
                {
                    'type': 'text',
                    'text': 'Some content without file path'
                }
            ]
        }

        path = ocr_extension._extract_file_path(tool_result)
        assert path is None

    def test_extract_file_path_returns_none_for_nonexistent_path(
        self,
        ocr_extension
    ):
        """Test file path extraction returns None for nonexistent paths."""
        tool_result: ToolResult = {
            'status': 'success',
            'content': [
                {
                    'type': 'text',
                    'text': 'Reading: /nonexistent/path/file.png'
                }
            ]
        }

        path = ocr_extension._extract_file_path(tool_result)
        # Should return None (os.path.exists check fails)
        assert path is None

    def test_extract_file_path_handles_empty_content(
        self,
        ocr_extension
    ):
        """Test file path extraction handles empty content list."""
        tool_result: ToolResult = {
            'status': 'success',
            'content': []
        }

        path = ocr_extension._extract_file_path(tool_result)
        assert path is None


# OCR Text Appending Tests
class TestOCRTextAppending:
    """Tests for _append_ocr_to_result() method."""

    def test_append_ocr_to_result_adds_content_block(
        self,
        ocr_extension
    ):
        """Test OCR text is appended as new content block."""
        tool_result: ToolResult = {
            'status': 'success',
            'content': [
                {'type': 'text', 'text': 'Original content'}
            ]
        }

        ocr_text = 'Hello from OCR'

        ocr_extension._append_ocr_to_result(tool_result, ocr_text)

        # Should have 2 content blocks now
        assert len(tool_result['content']) == 2

        # Check OCR block structure
        ocr_block = tool_result['content'][1]
        assert ocr_block['type'] == 'text'
        assert '--- OCR Extracted Text ---' in ocr_block['text']
        assert 'Hello from OCR' in ocr_block['text']

    def test_append_ocr_to_result_creates_content_if_missing(
        self,
        ocr_extension
    ):
        """Test OCR appending creates content list if missing."""
        tool_result: ToolResult = {
            'status': 'success',
            # No 'content' key
        }

        ocr_text = 'Hello from OCR'

        ocr_extension._append_ocr_to_result(tool_result, ocr_text)

        # Should create content list
        assert 'content' in tool_result
        assert len(tool_result['content']) == 1
        assert 'Hello from OCR' in tool_result['content'][0]['text']

    def test_append_ocr_to_result_preserves_existing_content(
        self,
        ocr_extension
    ):
        """Test OCR appending doesn't modify existing content."""
        original_block = {'type': 'text', 'text': 'Original content'}
        tool_result: ToolResult = {
            'status': 'success',
            'content': [original_block.copy()]
        }

        ocr_text = 'Hello from OCR'

        ocr_extension._append_ocr_to_result(tool_result, ocr_text)

        # Original block should be unchanged
        assert tool_result['content'][0] == original_block


# Integration Tests
class TestImageOCRExtensionIntegration:
    """Integration tests for ImageOCRExtension."""

    def test_full_image_ocr_workflow(
        self,
        ocr_extension,
        temp_image_file
    ):
        """Test complete workflow: image detection → OCR lookup → enhancement."""
        # Setup context with OCR
        context = {
            'file_refs': [
                {
                    'file_id': 'img001',
                    'filename': os.path.basename(temp_image_file),
                    'storage_path': temp_image_file,
                    'extracted_content': 'Test OCR text content'
                }
            ]
        }

        # Simulate Strands file_read result
        tool_result: ToolResult = {
            'status': 'success',
            'toolUseId': 'test-integration',
            'content': [
                {
                    'type': 'text',
                    'text': f'File: {temp_image_file} Type: PNG'
                }
            ]
        }

        # Process through extension
        result = ocr_extension.on_file_read(tool_result, context)

        # Should enhance with OCR
        assert len(result['content']) == 2
        assert '--- OCR Extracted Text ---' in result['content'][1]['text']
        assert 'Test OCR text content' in result['content'][1]['text']

    def test_non_image_file_passthrough(
        self,
        ocr_extension,
        sample_request_context
    ):
        """Test non-image files pass through unchanged."""
        tool_result: ToolResult = {
            'status': 'success',
            'content': [
                {
                    'type': 'text',
                    'text': 'File: /tmp/notes.txt Content: Hello World'
                }
            ]
        }

        result = ocr_extension.on_file_read(tool_result, sample_request_context)

        # Should be unchanged
        assert result == tool_result
        assert len(result['content']) == 1

    def test_image_without_ocr_logs_warning(
        self,
        ocr_extension,
        temp_image_file,
        sample_request_context
    ):
        """Test image without OCR logs warning but doesn't crash."""
        tool_result: ToolResult = {
            'status': 'success',
            'content': [
                {
                    'type': 'text',
                    'text': f'File: {temp_image_file} Type: PNG'
                }
            ]
        }

        # Should not crash (just log warning)
        result = ocr_extension.on_file_read(tool_result, sample_request_context)

        # Content unchanged (no OCR to add)
        assert len(result['content']) == 1
