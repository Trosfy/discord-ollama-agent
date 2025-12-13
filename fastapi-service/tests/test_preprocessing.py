"""Unit tests for preprocessing module."""
import pytest
from app.preprocessing import FileContextBuilder


class TestFileContextBuilder:
    """Test FileContextBuilder class."""

    def test_no_files(self):
        """Test with no file references."""
        builder = FileContextBuilder()
        result = builder.append_to_message("hello", [])
        assert result == "hello"

    def test_single_image_with_content(self):
        """Test with single image file containing extracted content."""
        builder = FileContextBuilder()
        file_refs = [{
            'filename': 'code.png',
            'content_type': 'image/png',
            'extracted_content': 'function test() { return 42; }'
        }]

        result = builder.append_to_message("what is this", file_refs)

        assert "what is this" in result
        assert "[Attached file: code.png (image/png)]" in result
        assert "function test() { return 42; }" in result

    def test_failed_extraction(self):
        """Test with failed content extraction."""
        builder = FileContextBuilder()
        file_refs = [{
            'filename': 'broken.png',
            'content_type': 'image/png',
            'extracted_content': '[Processing failed]'
        }]

        result = builder.append_to_message("question", file_refs)

        assert "[Content extraction failed or unavailable]" in result
        assert "[Processing failed]" not in result  # Should be replaced

    def test_empty_content(self):
        """Test with empty extracted content."""
        builder = FileContextBuilder()
        file_refs = [{
            'filename': 'empty.txt',
            'content_type': 'text/plain',
            'extracted_content': ''
        }]

        result = builder.append_to_message("test", file_refs)

        assert "[Content extraction failed or unavailable]" in result

    def test_none_content(self):
        """Test with None extracted content."""
        builder = FileContextBuilder()
        file_refs = [{
            'filename': 'none.txt',
            'content_type': 'text/plain',
            'extracted_content': None
        }]

        result = builder.append_to_message("test", file_refs)

        assert "[Content extraction failed or unavailable]" in result

    def test_multiple_files(self):
        """Test with multiple file references."""
        builder = FileContextBuilder()
        file_refs = [
            {
                'filename': 'code.png',
                'content_type': 'image/png',
                'extracted_content': 'function a() {}'
            },
            {
                'filename': 'data.txt',
                'content_type': 'text/plain',
                'extracted_content': 'Sample data'
            }
        ]

        result = builder.append_to_message("analyze", file_refs)

        assert "code.png" in result
        assert "data.txt" in result
        assert "function a() {}" in result
        assert "Sample data" in result

    def test_file_summary_no_files(self):
        """Test file summary with no files."""
        builder = FileContextBuilder()
        summary = builder.get_file_summary([])
        assert summary == "No files"

    def test_file_summary_single_image(self):
        """Test file summary with single image."""
        builder = FileContextBuilder()
        file_refs = [
            {'content_type': 'image/png'}
        ]

        summary = builder.get_file_summary(file_refs)
        assert "1 image" in summary

    def test_file_summary_multiple_types(self):
        """Test file summary with multiple file types."""
        builder = FileContextBuilder()
        file_refs = [
            {'content_type': 'image/png'},
            {'content_type': 'image/jpeg'},
            {'content_type': 'application/pdf'}
        ]

        summary = builder.get_file_summary(file_refs)
        assert "2 image" in summary
        assert "1 PDF" in summary

    def test_file_summary_audio(self):
        """Test file summary with audio file."""
        builder = FileContextBuilder()
        file_refs = [
            {'content_type': 'audio/mp3'}
        ]

        summary = builder.get_file_summary(file_refs)
        assert "1 audio" in summary

    def test_file_summary_video(self):
        """Test file summary with video file."""
        builder = FileContextBuilder()
        file_refs = [
            {'content_type': 'video/mp4'}
        ]

        summary = builder.get_file_summary(file_refs)
        assert "1 video" in summary

    def test_file_summary_text(self):
        """Test file summary with text file."""
        builder = FileContextBuilder()
        file_refs = [
            {'content_type': 'text/plain'}
        ]

        summary = builder.get_file_summary(file_refs)
        assert "1 text file" in summary

    def test_file_summary_unknown(self):
        """Test file summary with unknown file type."""
        builder = FileContextBuilder()
        file_refs = [
            {'content_type': 'application/octet-stream'}
        ]

        summary = builder.get_file_summary(file_refs)
        assert "1 file" in summary

    def test_ocr_service_unavailable_message(self):
        """Test with OCR service unavailable error message."""
        builder = FileContextBuilder()
        file_refs = [{
            'filename': 'image.png',
            'content_type': 'image/png',
            'extracted_content': '[OCR service not available]'
        }]

        result = builder.append_to_message("test", file_refs)

        assert "[Content extraction failed or unavailable]" in result
        assert "[OCR service not available]" not in result

    def test_message_enrichment_structure(self):
        """Test the structure of enriched message."""
        builder = FileContextBuilder()
        file_refs = [{
            'filename': 'test.txt',
            'content_type': 'text/plain',
            'extracted_content': 'Hello world'
        }]

        result = builder.append_to_message("original message", file_refs)

        # Check structure: original message + file info + content
        assert result.startswith("original message")
        assert "[Attached file: test.txt (text/plain)]" in result
        assert "Content:\nHello world" in result
