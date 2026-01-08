"""Unit tests for PDFExtractor."""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile

from app.services.extractors.pdf_extractor import PDFExtractor


@pytest.fixture
def pdf_extractor():
    """Create PDFExtractor instance."""
    return PDFExtractor()


@pytest.fixture
def temp_pdf_file():
    """Create temporary test PDF file."""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        # Write minimal PDF structure (not a valid PDF, but sufficient for testing)
        f.write(b'%PDF-1.4\n')
        f.write(b'1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n')
        f.write(b'%%EOF\n')
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


class TestPDFExtractor:
    """Test cases for PDFExtractor."""

    def test_supported_extensions(self, pdf_extractor):
        """Test that PDFExtractor reports correct supported extensions."""
        extensions = pdf_extractor.supported_extensions()

        assert isinstance(extensions, set)
        assert '.pdf' in extensions
        assert len(extensions) == 1  # Only PDF

        # Should have leading dot
        for ext in extensions:
            assert ext.startswith('.')

    def test_supported_mime_types(self, pdf_extractor):
        """Test that PDFExtractor reports correct MIME types."""
        mime_types = pdf_extractor.supported_mime_types()

        assert isinstance(mime_types, set)
        assert 'application/pdf' in mime_types
        assert len(mime_types) == 1  # Only PDF MIME type

    @pytest.mark.asyncio
    async def test_extract_success(self, pdf_extractor, temp_pdf_file):
        """Test successful PDF text extraction."""
        # Mock file_read_wrapped
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = 'Annual Report 2024\n\nRevenue increased by 15%...'

            result = await pdf_extractor.extract(temp_pdf_file, 'report.pdf')

            # Verify file_read_wrapped was called with correct path
            mock_read.assert_called_once_with(temp_pdf_file)

            # Verify result structure
            assert isinstance(result, dict)
            assert 'text' in result
            assert 'extractor' in result
            assert 'status' in result

            # Verify result values
            assert result['text'] == 'Annual Report 2024\n\nRevenue increased by 15%...'
            assert result['extractor'] == 'strands_pdf'
            assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_extract_failure(self, pdf_extractor, temp_pdf_file):
        """Test PDF extraction failure handling."""
        # Mock file_read_wrapped to raise exception
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.side_effect = Exception("Corrupted PDF file")

            result = await pdf_extractor.extract(temp_pdf_file, 'broken.pdf')

            # Verify result structure for error case
            assert isinstance(result, dict)
            assert 'text' in result
            assert 'extractor' in result
            assert 'status' in result

            # Verify error handling
            assert '[PDF extraction failed:' in result['text']
            assert 'Corrupted PDF file' in result['text']
            assert result['extractor'] == 'strands_pdf'
            assert result['status'] == 'error'

    @pytest.mark.asyncio
    async def test_extract_empty_pdf(self, pdf_extractor, temp_pdf_file):
        """Test extraction from empty PDF."""
        # Mock file_read_wrapped returning empty string
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = ''

            result = await pdf_extractor.extract(temp_pdf_file, 'empty.pdf')

            # Verify empty text is handled correctly
            assert result['text'] == ''
            assert result['status'] == 'success'
            assert result['extractor'] == 'strands_pdf'

    @pytest.mark.asyncio
    async def test_extract_with_unicode(self, pdf_extractor, temp_pdf_file):
        """Test extraction with Unicode characters."""
        # Mock file_read_wrapped returning Unicode text
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = 'Résumé: José García\n日本語テキスト\n🎉 Emoji'

            result = await pdf_extractor.extract(temp_pdf_file, 'unicode.pdf')

            # Verify Unicode is preserved
            assert result['text'] == 'Résumé: José García\n日本語テキスト\n🎉 Emoji'
            assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_extract_large_pdf(self, pdf_extractor, temp_pdf_file):
        """Test extraction of large PDF content."""
        # Mock file_read_wrapped returning large text
        large_text = "Page content\n" * 10000  # 10000 lines
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = large_text

            result = await pdf_extractor.extract(temp_pdf_file, 'large.pdf')

            # Verify large text is handled
            assert len(result['text']) == len(large_text)
            assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_extract_multiline_content(self, pdf_extractor, temp_pdf_file):
        """Test extraction with multiline formatted content."""
        # Mock file_read_wrapped with formatted content
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = """
TABLE OF CONTENTS
=================

1. Introduction ............... 1
2. Methodology ................ 5
3. Results .................... 12
4. Conclusion ................. 25
"""

            result = await pdf_extractor.extract(temp_pdf_file, 'toc.pdf')

            # Verify multiline content is preserved
            assert 'TABLE OF CONTENTS' in result['text']
            assert '1. Introduction' in result['text']
            assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_extract_permission_error(self, pdf_extractor, temp_pdf_file):
        """Test handling of permission errors."""
        # Mock file_read_wrapped to raise PermissionError
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.side_effect = PermissionError("Access denied")

            result = await pdf_extractor.extract(temp_pdf_file, 'protected.pdf')

            # Verify error handling
            assert result['status'] == 'error'
            assert '[PDF extraction failed:' in result['text']
            assert 'Access denied' in result['text']

    def test_initialization_no_dependencies(self):
        """Test PDFExtractor initialization requires no dependencies."""
        # PDFExtractor should initialize without any parameters
        extractor = PDFExtractor()

        # Verify instance is created successfully
        assert extractor is not None

    def test_liskov_substitution_principle(self, pdf_extractor):
        """Test that PDFExtractor can be used as IContentExtractor."""
        from app.services.extractors.interface import IContentExtractor

        # Verify PDFExtractor implements IContentExtractor
        assert isinstance(pdf_extractor, IContentExtractor)

        # Verify all required methods exist
        assert hasattr(pdf_extractor, 'supported_extensions')
        assert hasattr(pdf_extractor, 'supported_mime_types')
        assert hasattr(pdf_extractor, 'extract')

        # Verify methods are callable
        assert callable(pdf_extractor.supported_extensions)
        assert callable(pdf_extractor.supported_mime_types)
        assert callable(pdf_extractor.extract)

    def test_single_responsibility_principle(self, pdf_extractor):
        """Test that PDFExtractor only handles PDF files."""
        extensions = pdf_extractor.supported_extensions()
        mime_types = pdf_extractor.supported_mime_types()

        # Should only handle PDF files (Single Responsibility)
        assert extensions == {'.pdf'}
        assert mime_types == {'application/pdf'}
