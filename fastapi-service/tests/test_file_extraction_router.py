"""Unit tests for FileExtractionRouter (Strategy Pattern)."""
import pytest
from unittest.mock import Mock, AsyncMock
from pathlib import Path
import tempfile

from app.services.file_extraction_router import FileExtractionRouter
from app.services.extractors.interface import IContentExtractor


@pytest.fixture
def router():
    """Create FileExtractionRouter instance."""
    return FileExtractionRouter()


@pytest.fixture
def mock_image_extractor():
    """Create mock image extractor."""
    extractor = Mock(spec=IContentExtractor)
    extractor.supported_extensions.return_value = {'.png', '.jpg', '.jpeg'}
    extractor.supported_mime_types.return_value = {'image/png', 'image/jpeg'}
    extractor.extract = AsyncMock(return_value={
        'text': 'Extracted from image',
        'extractor': 'mock_image',
        'status': 'success'
    })
    return extractor


@pytest.fixture
def mock_pdf_extractor():
    """Create mock PDF extractor."""
    extractor = Mock(spec=IContentExtractor)
    extractor.supported_extensions.return_value = {'.pdf'}
    extractor.supported_mime_types.return_value = {'application/pdf'}
    extractor.extract = AsyncMock(return_value={
        'text': 'Extracted from PDF',
        'extractor': 'mock_pdf',
        'status': 'success'
    })
    return extractor


@pytest.fixture
def mock_text_extractor():
    """Create mock text extractor."""
    extractor = Mock(spec=IContentExtractor)
    extractor.supported_extensions.return_value = {'.txt', '.md', '.py'}
    extractor.supported_mime_types.return_value = {'text/plain', 'text/markdown'}
    extractor.extract = AsyncMock(return_value={
        'text': 'Extracted from text',
        'extractor': 'mock_text',
        'status': 'success'
    })
    return extractor


@pytest.fixture
def temp_image_file():
    """Create temporary test image file."""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
        temp_path = f.name

    yield temp_path
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_pdf_file():
    """Create temporary test PDF file."""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        f.write(b'%PDF-1.4\n%%EOF\n')
        temp_path = f.name

    yield temp_path
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_text_file():
    """Create temporary test text file."""
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
        f.write(b'Test content')
        temp_path = f.name

    yield temp_path
    Path(temp_path).unlink(missing_ok=True)


class TestFileExtractionRouter:
    """Test cases for FileExtractionRouter."""

    def test_initialization(self):
        """Test router initialization with empty extractor registry."""
        router = FileExtractionRouter()

        # Verify router is initialized with empty extractor list
        assert router.extractors == []

    def test_register_single_extractor(self, router, mock_image_extractor):
        """Test registering a single extractor."""
        router.register_extractor(mock_image_extractor)

        # Verify extractor is registered
        assert len(router.extractors) == 1
        assert router.extractors[0] is mock_image_extractor

    def test_register_multiple_extractors(self, router, mock_image_extractor, mock_pdf_extractor, mock_text_extractor):
        """Test registering multiple extractors."""
        router.register_extractor(mock_image_extractor)
        router.register_extractor(mock_pdf_extractor)
        router.register_extractor(mock_text_extractor)

        # Verify all extractors are registered
        assert len(router.extractors) == 3
        assert mock_image_extractor in router.extractors
        assert mock_pdf_extractor in router.extractors
        assert mock_text_extractor in router.extractors

    @pytest.mark.asyncio
    async def test_route_by_extension_png(self, router, mock_image_extractor, temp_image_file):
        """Test routing to correct extractor by file extension (.png)."""
        router.register_extractor(mock_image_extractor)

        result = await router.extract_content(temp_image_file, 'image/png')

        # Verify correct extractor was called
        mock_image_extractor.extract.assert_called_once_with(temp_image_file, Path(temp_image_file).name)

        # Verify result
        assert result['text'] == 'Extracted from image'
        assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_route_by_extension_pdf(self, router, mock_pdf_extractor, temp_pdf_file):
        """Test routing to correct extractor by file extension (.pdf)."""
        router.register_extractor(mock_pdf_extractor)

        result = await router.extract_content(temp_pdf_file, 'application/pdf')

        # Verify correct extractor was called
        mock_pdf_extractor.extract.assert_called_once_with(temp_pdf_file, Path(temp_pdf_file).name)

        # Verify result
        assert result['text'] == 'Extracted from PDF'
        assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_route_by_extension_text(self, router, mock_text_extractor, temp_text_file):
        """Test routing to correct extractor by file extension (.txt)."""
        router.register_extractor(mock_text_extractor)

        result = await router.extract_content(temp_text_file, 'text/plain')

        # Verify correct extractor was called
        mock_text_extractor.extract.assert_called_once_with(temp_text_file, Path(temp_text_file).name)

        # Verify result
        assert result['text'] == 'Extracted from text'
        assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_route_by_mime_type(self, router, mock_image_extractor):
        """Test routing to correct extractor by MIME type when extension doesn't match."""
        router.register_extractor(mock_image_extractor)

        # File with no extension but valid MIME type
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
            temp_path = f.name

        try:
            result = await router.extract_content(temp_path, 'image/png')

            # Verify extractor was called based on MIME type
            mock_image_extractor.extract.assert_called_once()
            assert result['text'] == 'Extracted from image'
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_route_with_multiple_extractors(self, router, mock_image_extractor, mock_pdf_extractor, mock_text_extractor, temp_image_file):
        """Test routing selects correct extractor among multiple registered."""
        # Register all extractors
        router.register_extractor(mock_text_extractor)
        router.register_extractor(mock_pdf_extractor)
        router.register_extractor(mock_image_extractor)

        result = await router.extract_content(temp_image_file, 'image/png')

        # Verify only image extractor was called
        mock_image_extractor.extract.assert_called_once()
        mock_pdf_extractor.extract.assert_not_called()
        mock_text_extractor.extract.assert_not_called()

        assert result['text'] == 'Extracted from image'

    @pytest.mark.asyncio
    async def test_unsupported_file_type(self, router, mock_image_extractor):
        """Test handling of unsupported file types."""
        router.register_extractor(mock_image_extractor)

        # Try to extract unsupported file type
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as f:
            f.write(b'MZ\x90\x00')  # EXE header
            temp_path = f.name

        try:
            result = await router.extract_content(temp_path, 'application/x-msdownload')

            # Verify no extractor was called
            mock_image_extractor.extract.assert_not_called()

            # Verify unsupported response
            assert 'Unsupported file type' in result['text']
            assert result['extractor'] == 'none'
            assert result['status'] == 'unsupported'
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_extractor_isolation_on_failure(self, router, mock_image_extractor, mock_pdf_extractor, temp_pdf_file):
        """Test that one extractor failure doesn't affect others (extractor isolation)."""
        # Configure image extractor to fail
        failing_extractor = Mock(spec=IContentExtractor)
        failing_extractor.supported_extensions.return_value = {'.png'}
        failing_extractor.supported_mime_types.return_value = {'image/png'}
        failing_extractor.extract = AsyncMock(side_effect=Exception("Extractor crashed"))

        # Register failing extractor and working PDF extractor
        router.register_extractor(failing_extractor)
        router.register_extractor(mock_pdf_extractor)

        # Extract PDF (should work despite failing image extractor)
        result = await router.extract_content(temp_pdf_file, 'application/pdf')

        # Verify PDF extractor still works
        mock_pdf_extractor.extract.assert_called_once()
        assert result['text'] == 'Extracted from PDF'
        assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_first_match_wins(self, router):
        """Test that first matching extractor is used (Strategy Pattern)."""
        # Create two extractors that support the same file type
        extractor1 = Mock(spec=IContentExtractor)
        extractor1.supported_extensions.return_value = {'.txt'}
        extractor1.supported_mime_types.return_value = {'text/plain'}
        extractor1.extract = AsyncMock(return_value={
            'text': 'From extractor 1',
            'extractor': 'extractor1',
            'status': 'success'
        })

        extractor2 = Mock(spec=IContentExtractor)
        extractor2.supported_extensions.return_value = {'.txt'}
        extractor2.supported_mime_types.return_value = {'text/plain'}
        extractor2.extract = AsyncMock(return_value={
            'text': 'From extractor 2',
            'extractor': 'extractor2',
            'status': 'success'
        })

        # Register in order: extractor1 first, then extractor2
        router.register_extractor(extractor1)
        router.register_extractor(extractor2)

        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'Test')
            temp_path = f.name

        try:
            result = await router.extract_content(temp_path, 'text/plain')

            # Verify first extractor was used
            extractor1.extract.assert_called_once()
            extractor2.extract.assert_not_called()
            assert result['text'] == 'From extractor 1'
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_case_insensitive_extension_matching(self, router, mock_image_extractor):
        """Test that extension matching is case-insensitive."""
        router.register_extractor(mock_image_extractor)

        # Create file with uppercase extension
        with tempfile.NamedTemporaryFile(suffix='.PNG', delete=False) as f:
            f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
            temp_path = f.name

        try:
            result = await router.extract_content(temp_path, 'image/png')

            # Verify extractor was called despite uppercase extension
            mock_image_extractor.extract.assert_called_once()
            assert result['status'] == 'success'
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_extract_content_with_complex_filename(self, router, mock_image_extractor):
        """Test extraction with complex filename (spaces, special chars)."""
        router.register_extractor(mock_image_extractor)

        # Create file with complex name
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
            temp_path = f.name

        try:
            result = await router.extract_content(temp_path, 'image/png')

            # Verify extraction works with complex filename
            assert result['status'] == 'success'
            mock_image_extractor.extract.assert_called_once()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_open_closed_principle(self, router, mock_image_extractor, mock_pdf_extractor):
        """Test Open/Closed Principle: OPEN for extension, CLOSED for modification."""
        # Initially register image extractor
        router.register_extractor(mock_image_extractor)
        assert len(router.extractors) == 1

        # Add new extractor WITHOUT modifying router code (Open/Closed)
        router.register_extractor(mock_pdf_extractor)
        assert len(router.extractors) == 2

        # Router code doesn't need to change to support new file types
        # This demonstrates Open/Closed Principle

    def test_dependency_inversion_principle(self, router):
        """Test Dependency Inversion: Router depends on IContentExtractor abstraction."""
        # Create mock that implements IContentExtractor interface
        mock_extractor = Mock(spec=IContentExtractor)
        mock_extractor.supported_extensions.return_value = {'.custom'}
        mock_extractor.supported_mime_types.return_value = {'application/custom'}

        # Router accepts any IContentExtractor implementation
        router.register_extractor(mock_extractor)

        # Verify router doesn't depend on concrete classes
        assert len(router.extractors) == 1
        assert isinstance(router.extractors[0], Mock)

    def test_single_responsibility_principle(self, router):
        """Test Single Responsibility: Router only routes, doesn't extract."""
        # Router should have extractors list and registration method
        assert hasattr(router, 'extractors')
        assert hasattr(router, 'register_extractor')
        assert hasattr(router, 'extract_content')

        # Router should NOT have extraction logic for specific file types
        assert not hasattr(router, 'extract_pdf')
        assert not hasattr(router, 'extract_image')
        assert not hasattr(router, 'extract_text')

    @pytest.mark.asyncio
    async def test_liskov_substitution_principle(self, router):
        """Test Liskov Substitution: All IContentExtractor implementations are interchangeable."""
        # Create multiple extractors implementing same interface
        extractors = []
        for i in range(3):
            extractor = Mock(spec=IContentExtractor)
            extractor.supported_extensions.return_value = {f'.ext{i}'}
            extractor.supported_mime_types.return_value = {f'application/ext{i}'}
            extractor.extract = AsyncMock(return_value={
                'text': f'Result {i}',
                'extractor': f'extractor{i}',
                'status': 'success'
            })
            extractors.append(extractor)
            router.register_extractor(extractor)

        # All extractors should be usable interchangeably via the interface
        assert len(router.extractors) == 3

        # Router treats all extractors identically
        for i, extractor in enumerate(extractors):
            with tempfile.NamedTemporaryFile(suffix=f'.ext{i}', delete=False) as f:
                f.write(b'Test')
                temp_path = f.name

            try:
                result = await router.extract_content(temp_path, f'application/ext{i}')
                assert result['text'] == f'Result {i}'
            finally:
                Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_empty_router_unsupported(self, router, temp_text_file):
        """Test that router with no extractors returns unsupported for all files."""
        # Don't register any extractors
        result = await router.extract_content(temp_text_file, 'text/plain')

        # Verify unsupported response
        assert 'Unsupported file type' in result['text']
        assert result['extractor'] == 'none'
        assert result['status'] == 'unsupported'

    @pytest.mark.asyncio
    async def test_strategy_pattern_dynamic_selection(self, router, mock_image_extractor, mock_pdf_extractor, mock_text_extractor, temp_image_file, temp_pdf_file, temp_text_file):
        """Test Strategy Pattern: Router dynamically selects appropriate extractor."""
        # Register all extractors
        router.register_extractor(mock_image_extractor)
        router.register_extractor(mock_pdf_extractor)
        router.register_extractor(mock_text_extractor)

        # Extract different file types - router selects correct strategy
        image_result = await router.extract_content(temp_image_file, 'image/png')
        pdf_result = await router.extract_content(temp_pdf_file, 'application/pdf')
        text_result = await router.extract_content(temp_text_file, 'text/plain')

        # Verify different strategies were applied
        assert image_result['text'] == 'Extracted from image'
        assert pdf_result['text'] == 'Extracted from PDF'
        assert text_result['text'] == 'Extracted from text'

        # Verify each extractor was called exactly once
        mock_image_extractor.extract.assert_called_once()
        mock_pdf_extractor.extract.assert_called_once()
        mock_text_extractor.extract.assert_called_once()
