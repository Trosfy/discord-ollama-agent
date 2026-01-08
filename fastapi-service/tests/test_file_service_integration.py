"""Integration tests for FileService with FileExtractionRouter."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import tempfile

from app.services.file_service import FileService
from app.services.file_extraction_router import FileExtractionRouter
from app.services.extractors.image_extractor import ImageExtractor
from app.services.extractors.pdf_extractor import PDFExtractor
from app.services.extractors.text_extractor import TextExtractor


@pytest.fixture
def mock_ocr_service():
    """Create mock OCR service."""
    service = Mock()
    service.extract_text_from_image = AsyncMock(return_value={
        'text': 'Login screen\nUsername: _____',
        'status': 'success'
    })
    return service


@pytest.fixture
def extraction_router_with_all_extractors(mock_ocr_service):
    """Create FileExtractionRouter with all extractors registered."""
    router = FileExtractionRouter()
    router.register_extractor(ImageExtractor(mock_ocr_service))
    router.register_extractor(PDFExtractor())
    router.register_extractor(TextExtractor())
    return router


@pytest.fixture
def file_service(extraction_router_with_all_extractors):
    """Create FileService with router."""
    with patch('app.config.settings') as mock_settings:
        # Create temporary directories
        temp_upload_dir = tempfile.mkdtemp()
        temp_artifact_dir = tempfile.mkdtemp()

        mock_settings.TEMP_UPLOAD_DIR = temp_upload_dir
        mock_settings.TEMP_ARTIFACT_DIR = temp_artifact_dir

        service = FileService(extraction_router=extraction_router_with_all_extractors)

        yield service

        # Cleanup
        import shutil
        shutil.rmtree(temp_upload_dir, ignore_errors=True)
        shutil.rmtree(temp_artifact_dir, ignore_errors=True)


class TestFileServiceIntegration:
    """Integration tests for FileService with extraction router."""

    @pytest.mark.asyncio
    async def test_save_image_file_with_ocr(self, file_service, mock_ocr_service):
        """Test saving image file triggers OCR extraction."""
        # Create minimal PNG image
        image_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100

        result = await file_service.save_temp_file(
            file_data=image_data,
            filename='screenshot.png',
            content_type='image/png',
            user_id='user123'
        )

        # Verify file was saved
        assert 'file_id' in result
        assert result['filename'] == 'screenshot.png'
        assert result['content_type'] == 'image/png'
        assert result['size'] == len(image_data)
        assert result['user_id'] == 'user123'

        # Verify OCR was performed
        assert 'extracted_content' in result
        assert result['extracted_content'] == 'Login screen\nUsername: _____'

        # Verify OCR service was called
        mock_ocr_service.extract_text_from_image.assert_called_once()

        # Verify file exists on disk
        storage_path = Path(result['storage_path'])
        assert storage_path.exists()

        # Cleanup
        storage_path.unlink()

    @pytest.mark.asyncio
    async def test_save_pdf_file_with_extraction(self, file_service):
        """Test saving PDF file triggers text extraction."""
        # Create minimal PDF
        pdf_data = b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n'

        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_pdf_read:
            mock_pdf_read.return_value = 'Annual Report 2024\nRevenue increased by 15%'

            result = await file_service.save_temp_file(
                file_data=pdf_data,
                filename='report.pdf',
                content_type='application/pdf',
                user_id='user123'
            )

            # Verify file was saved
            assert result['filename'] == 'report.pdf'
            assert result['content_type'] == 'application/pdf'

            # Verify PDF extraction was performed
            assert result['extracted_content'] == 'Annual Report 2024\nRevenue increased by 15%'

            # Verify file_read_wrapped was called
            mock_pdf_read.assert_called_once()

            # Cleanup
            Path(result['storage_path']).unlink()

    @pytest.mark.asyncio
    async def test_save_text_file_with_extraction(self, file_service):
        """Test saving text file triggers content extraction."""
        # Create text file content
        text_data = b'This is a test file.\nLine 2.\nLine 3.'

        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = 'This is a test file.\nLine 2.\nLine 3.'

            result = await file_service.save_temp_file(
                file_data=text_data,
                filename='notes.txt',
                content_type='text/plain',
                user_id='user456'
            )

            # Verify file was saved
            assert result['filename'] == 'notes.txt'
            assert result['content_type'] == 'text/plain'

            # Verify text extraction was performed
            assert result['extracted_content'] == 'This is a test file.\nLine 2.\nLine 3.'

            # Cleanup
            Path(result['storage_path']).unlink()

    @pytest.mark.asyncio
    async def test_save_python_file_with_extraction(self, file_service):
        """Test saving Python file triggers content extraction."""
        # Create Python file content
        python_code = b'def hello():\n    print("Hello, world!")\n'

        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = 'def hello():\n    print("Hello, world!")\n'

            result = await file_service.save_temp_file(
                file_data=python_code,
                filename='script.py',
                content_type='text/x-python',
                user_id='dev001'
            )

            # Verify Python code extraction
            assert result['filename'] == 'script.py'
            assert 'def hello()' in result['extracted_content']

            # Cleanup
            Path(result['storage_path']).unlink()

    @pytest.mark.asyncio
    async def test_save_json_file_with_extraction(self, file_service):
        """Test saving JSON file triggers content extraction."""
        # Create JSON content
        json_data = b'{"name": "test", "value": 123}'

        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = '{"name": "test", "value": 123}'

            result = await file_service.save_temp_file(
                file_data=json_data,
                filename='config.json',
                content_type='application/json',
                user_id='admin'
            )

            # Verify JSON extraction
            assert result['filename'] == 'config.json'
            assert result['extracted_content'] == '{"name": "test", "value": 123}'

            # Cleanup
            Path(result['storage_path']).unlink()

    @pytest.mark.asyncio
    async def test_save_unsupported_file_type(self, file_service):
        """Test saving unsupported file type returns appropriate message."""
        # Create binary file (not supported)
        binary_data = b'\x00\x01\x02\x03\x04\x05'

        result = await file_service.save_temp_file(
            file_data=binary_data,
            filename='data.bin',
            content_type='application/octet-stream',
            user_id='user789'
        )

        # Verify file was saved but extraction shows unsupported
        assert result['filename'] == 'data.bin'
        assert 'Unsupported file type' in result['extracted_content']

        # Cleanup
        Path(result['storage_path']).unlink()

    @pytest.mark.asyncio
    async def test_extraction_failure_graceful_handling(self, file_service, mock_ocr_service):
        """Test that extraction failures are handled gracefully."""
        # Configure OCR to fail
        mock_ocr_service.extract_text_from_image.side_effect = Exception("OCR service down")

        image_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100

        result = await file_service.save_temp_file(
            file_data=image_data,
            filename='broken.png',
            content_type='image/png',
            user_id='user123'
        )

        # Verify file was still saved despite extraction failure
        assert result['filename'] == 'broken.png'
        assert result['size'] == len(image_data)

        # Verify extraction failure is indicated
        assert 'OCR processing failed' in result['extracted_content'] or '[Extraction failed]' in result['extracted_content']

        # Cleanup
        Path(result['storage_path']).unlink()

    @pytest.mark.asyncio
    async def test_multiple_files_different_types(self, file_service, mock_ocr_service):
        """Test processing multiple files of different types."""
        # Save image
        image_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        image_result = await file_service.save_temp_file(
            image_data, 'screenshot.png', 'image/png', 'user1'
        )

        # Save PDF
        pdf_data = b'%PDF-1.4\n%%EOF\n'
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_pdf_read:
            mock_pdf_read.return_value = 'PDF content'
            pdf_result = await file_service.save_temp_file(
                pdf_data, 'doc.pdf', 'application/pdf', 'user1'
            )

        # Save text
        text_data = b'Text content'
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_text_read:
            mock_text_read.return_value = 'Text content'
            text_result = await file_service.save_temp_file(
                text_data, 'notes.txt', 'text/plain', 'user1'
            )

        # Verify all files were processed with appropriate extractors
        assert 'Login screen' in image_result['extracted_content']
        assert pdf_result['extracted_content'] == 'PDF content'
        assert text_result['extracted_content'] == 'Text content'

        # Verify different extractors were used
        assert mock_ocr_service.extract_text_from_image.called
        assert mock_pdf_read.called
        assert mock_text_read.called

        # Cleanup
        Path(image_result['storage_path']).unlink()
        Path(pdf_result['storage_path']).unlink()
        Path(text_result['storage_path']).unlink()

    @pytest.mark.asyncio
    async def test_file_service_without_router(self):
        """Test FileService behavior when no extraction router is provided."""
        with patch('app.config.settings') as mock_settings:
            temp_upload_dir = tempfile.mkdtemp()
            temp_artifact_dir = tempfile.mkdtemp()

            mock_settings.TEMP_UPLOAD_DIR = temp_upload_dir
            mock_settings.TEMP_ARTIFACT_DIR = temp_artifact_dir

            # Create FileService without router
            service = FileService(extraction_router=None)

            # Try to save file
            text_data = b'Test content'
            result = await service.save_temp_file(
                text_data, 'test.txt', 'text/plain', 'user1'
            )

            # Verify file was saved but extraction shows unavailable
            assert result['filename'] == 'test.txt'
            assert result['extracted_content'] == '[Extraction router not available]'

            # Cleanup
            Path(result['storage_path']).unlink()
            import shutil
            shutil.rmtree(temp_upload_dir, ignore_errors=True)
            shutil.rmtree(temp_artifact_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_unicode_filename_handling(self, file_service):
        """Test handling of Unicode filenames."""
        text_data = b'Content with unicode'

        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = 'Content with unicode'

            result = await file_service.save_temp_file(
                file_data=text_data,
                filename='文档.txt',  # Unicode filename
                content_type='text/plain',
                user_id='user123'
            )

            # Verify Unicode filename is preserved
            assert result['filename'] == '文档.txt'
            assert result['extracted_content'] == 'Content with unicode'

            # Cleanup
            Path(result['storage_path']).unlink()

    @pytest.mark.asyncio
    async def test_large_file_handling(self, file_service):
        """Test handling of large files."""
        # Create large text content (1MB)
        large_text = b'Line of text\n' * 100000

        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = 'Line of text\n' * 100000

            result = await file_service.save_temp_file(
                file_data=large_text,
                filename='large.txt',
                content_type='text/plain',
                user_id='user123'
            )

            # Verify large file was saved and extracted
            assert result['size'] == len(large_text)
            assert len(result['extracted_content']) > 1000000

            # Cleanup
            Path(result['storage_path']).unlink()

    @pytest.mark.asyncio
    async def test_end_to_end_preprocessing_flow(self, file_service, mock_ocr_service):
        """Test complete preprocessing flow: save → route → extract → store."""
        # Simulate user uploading image via Discord
        image_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100

        # STAGE 1: PREPROCESSING (FileService + Router + Extractor)
        file_info = await file_service.save_temp_file(
            file_data=image_data,
            filename='user_screenshot.png',
            content_type='image/png',
            user_id='discord_user_123'
        )

        # Verify preprocessing completed successfully
        assert 'file_id' in file_info
        assert 'storage_path' in file_info
        assert 'extracted_content' in file_info

        # Verify extracted content is ready for agent
        assert file_info['extracted_content'] == 'Login screen\nUsername: _____'

        # This extracted content would be stored in file_refs for agent to access
        # via list_attachments tool during STAGE 2 (Main Workflow)

        # Verify file is on disk for potential Discord upload later
        assert Path(file_info['storage_path']).exists()

        # Cleanup
        Path(file_info['storage_path']).unlink()

    @pytest.mark.asyncio
    async def test_solid_principles_integration(self, file_service, extraction_router_with_all_extractors):
        """Test that SOLID principles are maintained in integration."""
        # Single Responsibility: FileService manages storage, Router routes, Extractors extract
        assert hasattr(file_service, 'extraction_router')
        assert isinstance(file_service.extraction_router, FileExtractionRouter)
        assert len(file_service.extraction_router.extractors) == 3

        # Open/Closed: Can add new extractor without modifying FileService or Router
        from app.services.extractors.interface import IContentExtractor
        new_extractor = Mock(spec=IContentExtractor)
        new_extractor.supported_extensions.return_value = {'.custom'}
        new_extractor.supported_mime_types.return_value = {'application/custom'}

        file_service.extraction_router.register_extractor(new_extractor)
        assert len(file_service.extraction_router.extractors) == 4

        # Dependency Inversion: FileService depends on Router abstraction
        # Router depends on IContentExtractor abstraction
        for extractor in file_service.extraction_router.extractors[:3]:
            assert isinstance(extractor, IContentExtractor)

    @pytest.mark.asyncio
    async def test_artifact_save_and_retrieval(self, file_service):
        """Test saving artifacts after agent creates files."""
        # Simulate agent calling file_write and creating artifact
        artifact_content = "def fibonacci(n):\n    if n <= 1:\n        return n\n"

        storage_path = await file_service.save_artifact(
            artifact_id='art_123',
            content=artifact_content,
            filename='fibonacci.py'
        )

        # Verify artifact was saved
        assert Path(storage_path).exists()

        # Verify artifact content
        with open(storage_path, 'r') as f:
            saved_content = f.read()
        assert saved_content == artifact_content

        # Cleanup
        Path(storage_path).unlink()

    @pytest.mark.asyncio
    async def test_delete_file(self, file_service):
        """Test file deletion."""
        # Save file first
        text_data = b'Temporary content'

        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = 'Temporary content'

            result = await file_service.save_temp_file(
                text_data, 'temp.txt', 'text/plain', 'user1'
            )

            storage_path = result['storage_path']
            assert Path(storage_path).exists()

            # Delete file
            await file_service.delete_file(storage_path)

            # Verify file was deleted
            assert not Path(storage_path).exists()
