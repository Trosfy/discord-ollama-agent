"""Unit tests for File Service."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import tempfile
import time

from app.services.file_service import FileService


@pytest.fixture
def mock_ocr_service():
    """Create mock OCR service."""
    ocr = AsyncMock()
    ocr.analyze_document = AsyncMock(return_value={
        'text': 'Extracted text from test file',
        'model': 'ministral-3:14b',
        'status': 'success'
    })
    return ocr


@pytest.fixture
def file_service(mock_ocr_service):
    """Create file service instance with temp directories."""
    with tempfile.TemporaryDirectory() as temp_upload_dir, \
         tempfile.TemporaryDirectory() as temp_artifact_dir:

        service = FileService(mock_ocr_service)
        service.temp_upload_dir = Path(temp_upload_dir)
        service.temp_artifact_dir = Path(temp_artifact_dir)

        yield service


class TestFileService:
    """Test cases for File Service."""

    @pytest.mark.asyncio
    async def test_save_temp_file_success(self, file_service, mock_ocr_service):
        """Test successful temp file save and processing."""
        file_data = b'Test file content'
        filename = 'test_image.png'
        content_type = 'image/png'
        user_id = 'user123'

        result = await file_service.save_temp_file(
            file_data=file_data,
            filename=filename,
            content_type=content_type,
            user_id=user_id
        )

        # Verify result structure
        assert 'file_id' in result
        assert result['filename'] == filename
        assert result['content_type'] == content_type
        assert result['size'] == len(file_data)
        assert result['extracted_content'] == 'Extracted text from test file'
        assert result['user_id'] == user_id

        # Verify file was saved
        storage_path = Path(result['storage_path'])
        assert storage_path.exists()
        assert storage_path.read_bytes() == file_data

        # Verify OCR was called
        mock_ocr_service.analyze_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_temp_file_with_extension(self, file_service):
        """Test file saved with correct extension."""
        file_data = b'JSON content'
        filename = 'data.json'

        result = await file_service.save_temp_file(
            file_data=file_data,
            filename=filename,
            content_type='application/json',
            user_id='user123'
        )

        storage_path = Path(result['storage_path'])
        assert storage_path.suffix == '.json'

    @pytest.mark.asyncio
    async def test_save_temp_file_no_extension(self, file_service):
        """Test file saved when no extension provided."""
        file_data = b'Some content'
        filename = 'noextension'

        result = await file_service.save_temp_file(
            file_data=file_data,
            filename=filename,
            content_type='application/octet-stream',
            user_id='user123'
        )

        storage_path = Path(result['storage_path'])
        assert storage_path.suffix == '.bin'

    @pytest.mark.asyncio
    async def test_save_temp_file_ocr_failure(self, file_service, mock_ocr_service):
        """Test file save when OCR fails."""
        mock_ocr_service.analyze_document.side_effect = Exception("OCR failed")

        file_data = b'Test file'
        result = await file_service.save_temp_file(
            file_data=file_data,
            filename='test.png',
            content_type='image/png',
            user_id='user123'
        )

        # File should still be saved
        assert result['extracted_content'] == '[Processing failed]'
        assert Path(result['storage_path']).exists()

    @pytest.mark.asyncio
    async def test_delete_file_success(self, file_service):
        """Test successful file deletion."""
        # Create a temp file first
        file_data = b'To be deleted'
        result = await file_service.save_temp_file(
            file_data=file_data,
            filename='delete_me.txt',
            content_type='text/plain',
            user_id='user123'
        )

        storage_path = result['storage_path']
        assert Path(storage_path).exists()

        # Delete the file
        await file_service.delete_file(storage_path)

        # Verify deletion
        assert not Path(storage_path).exists()

    @pytest.mark.asyncio
    async def test_delete_file_not_exists(self, file_service):
        """Test deleting non-existent file (should not raise error)."""
        # Should not raise an exception
        await file_service.delete_file('/nonexistent/file.txt')

    @pytest.mark.asyncio
    async def test_save_artifact_success(self, file_service):
        """Test successful artifact save."""
        artifact_id = 'artifact-123'
        content = 'print("Hello, World!")'
        filename = 'script.py'

        storage_path = await file_service.save_artifact(
            artifact_id=artifact_id,
            content=content,
            filename=filename
        )

        # Verify file was saved
        path = Path(storage_path)
        assert path.exists()
        assert path.read_text(encoding='utf-8') == content
        assert filename in path.name
        assert artifact_id in path.name

    @pytest.mark.asyncio
    async def test_save_artifact_sanitizes_filename(self, file_service):
        """Test artifact filename is sanitized (no path traversal)."""
        artifact_id = 'artifact-456'
        content = 'test content'
        filename = '../../../etc/passwd'  # Malicious filename

        storage_path = await file_service.save_artifact(
            artifact_id=artifact_id,
            content=content,
            filename=filename
        )

        # Verify file is saved in artifact dir, not traversed path
        path = Path(storage_path)
        assert path.parent == file_service.temp_artifact_dir
        assert 'passwd' in path.name  # Filename preserved but path removed

    @pytest.mark.asyncio
    async def test_cleanup_old_artifacts(self, file_service):
        """Test cleanup of old artifacts."""
        # Create an old artifact (modified time in the past)
        old_artifact_path = file_service.temp_artifact_dir / 'old_artifact.txt'
        old_artifact_path.write_text('Old content')

        # Set modification time to 13 hours ago
        old_time = time.time() - (13 * 3600)
        old_artifact_path.touch()  # Create file
        import os
        os.utime(old_artifact_path, (old_time, old_time))

        # Create a recent artifact
        recent_artifact_path = file_service.temp_artifact_dir / 'recent_artifact.txt'
        recent_artifact_path.write_text('Recent content')

        # Run cleanup (12 hour threshold)
        cleaned_count = await file_service.cleanup_old_artifacts(max_age_hours=12)

        # Verify old artifact was deleted
        assert not old_artifact_path.exists()
        assert recent_artifact_path.exists()
        assert cleaned_count == 1

    @pytest.mark.asyncio
    async def test_cleanup_old_artifacts_none_to_clean(self, file_service):
        """Test cleanup when no old artifacts exist."""
        # Create only recent artifacts
        recent_path = file_service.temp_artifact_dir / 'recent.txt'
        recent_path.write_text('Recent')

        cleaned_count = await file_service.cleanup_old_artifacts(max_age_hours=12)

        assert cleaned_count == 0
        assert recent_path.exists()

    @pytest.mark.asyncio
    async def test_cleanup_old_uploads(self, file_service):
        """Test cleanup of stale upload files."""
        # Create a stale upload file
        stale_upload_path = file_service.temp_upload_dir / 'stale_upload.png'
        stale_upload_path.write_bytes(b'stale data')

        # Set modification time to 2 hours ago
        old_time = time.time() - (2 * 3600)
        import os
        os.utime(stale_upload_path, (old_time, old_time))

        # Run cleanup (1 hour threshold)
        cleaned_count = await file_service.cleanup_old_uploads(max_age_hours=1)

        # Verify stale upload was deleted
        assert not stale_upload_path.exists()
        assert cleaned_count == 1

    @pytest.mark.asyncio
    async def test_multiple_files_different_users(self, file_service):
        """Test handling multiple files from different users."""
        user1_result = await file_service.save_temp_file(
            file_data=b'User 1 file',
            filename='user1.txt',
            content_type='text/plain',
            user_id='user1'
        )

        user2_result = await file_service.save_temp_file(
            file_data=b'User 2 file',
            filename='user2.txt',
            content_type='text/plain',
            user_id='user2'
        )

        # Verify both files saved with different IDs
        assert user1_result['file_id'] != user2_result['file_id']
        assert user1_result['user_id'] == 'user1'
        assert user2_result['user_id'] == 'user2'

        # Verify both files exist
        assert Path(user1_result['storage_path']).exists()
        assert Path(user2_result['storage_path']).exists()

    def test_file_service_initialization(self, mock_ocr_service):
        """Test file service initializes with directories."""
        service = FileService(mock_ocr_service)

        assert service.ocr_service == mock_ocr_service
        assert service.temp_upload_dir.exists()
        assert service.temp_artifact_dir.exists()
