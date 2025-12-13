"""Unit tests for File Tools."""
import pytest
from unittest.mock import Mock, patch, AsyncMock

from app.tools.file_tools import list_attachments, get_file_content, create_artifact


@pytest.fixture
def mock_request_with_files():
    """Mock request with file references."""
    return {
        'file_refs': [
            {
                'file_id': 'file-001',
                'filename': 'screenshot.png',
                'content_type': 'image/png',
                'size': 50000,
                'extracted_content': 'Text from screenshot'
            },
            {
                'file_id': 'file-002',
                'filename': 'document.txt',
                'content_type': 'text/plain',
                'size': 1500,
                'extracted_content': 'Text from document'
            }
        ]
    }


@pytest.fixture
def mock_request_empty():
    """Mock request with no files."""
    return {}


class TestListAttachments:
    """Test cases for list_attachments tool."""

    def test_list_attachments_with_files(self, mock_request_with_files):
        """Test listing attachments when files exist."""
        with patch('app.dependencies.get_current_request', return_value=mock_request_with_files):
            result = list_attachments()

            assert len(result) == 2
            assert result[0]['file_id'] == 'file-001'
            assert result[0]['filename'] == 'screenshot.png'
            assert result[0]['content_type'] == 'image/png'
            assert result[0]['size'] == '50000'
            assert result[0]['has_content'] == 'yes'

            assert result[1]['file_id'] == 'file-002'
            assert result[1]['filename'] == 'document.txt'
            assert result[1]['has_content'] == 'yes'

    def test_list_attachments_no_files(self, mock_request_empty):
        """Test listing attachments when no files exist."""
        with patch('app.dependencies.get_current_request', return_value=mock_request_empty):
            result = list_attachments()

            assert result == []

    def test_list_attachments_no_extracted_content(self):
        """Test listing files without extracted content."""
        mock_request = {
            'file_refs': [
                {
                    'file_id': 'file-003',
                    'filename': 'image.jpg',
                    'content_type': 'image/jpeg',
                    'size': 100000,
                    # No extracted_content field
                }
            ]
        }

        with patch('app.dependencies.get_current_request', return_value=mock_request):
            result = list_attachments()

            assert len(result) == 1
            assert result[0]['has_content'] == 'no'


class TestGetFileContent:
    """Test cases for get_file_content tool."""

    def test_get_file_content_success(self, mock_request_with_files):
        """Test retrieving content from existing file."""
        with patch('app.dependencies.get_current_request', return_value=mock_request_with_files):
            result = get_file_content('file-001')

            assert result['filename'] == 'screenshot.png'
            assert result['content_type'] == 'image/png'
            assert result['extracted_content'] == 'Text from screenshot'

    def test_get_file_content_second_file(self, mock_request_with_files):
        """Test retrieving content from second file."""
        with patch('app.dependencies.get_current_request', return_value=mock_request_with_files):
            result = get_file_content('file-002')

            assert result['filename'] == 'document.txt'
            assert result['extracted_content'] == 'Text from document'

    def test_get_file_content_not_found(self, mock_request_with_files):
        """Test retrieving content from non-existent file."""
        with patch('app.dependencies.get_current_request', return_value=mock_request_with_files):
            result = get_file_content('file-999')

            assert 'error' in result
            assert 'not found' in result['error']

    def test_get_file_content_no_extracted_content(self):
        """Test retrieving file with no extracted content."""
        mock_request = {
            'file_refs': [
                {
                    'file_id': 'file-004',
                    'filename': 'binary.bin',
                    'content_type': 'application/octet-stream',
                    'size': 500
                    # No extracted_content
                }
            ]
        }

        with patch('app.dependencies.get_current_request', return_value=mock_request):
            result = get_file_content('file-004')

            assert result['extracted_content'] == '[No content extracted]'


class TestCreateArtifact:
    """Test cases for create_artifact tool."""

    @pytest.mark.asyncio
    async def test_create_artifact_success(self):
        """Test successful artifact creation."""
        mock_file_service = AsyncMock()
        mock_file_service.save_artifact = AsyncMock(return_value='/tmp/artifacts/art-123_script.py')

        with patch('app.dependencies.get_file_service', return_value=mock_file_service), \
             patch('app.tools.file_tools.asyncio.run') as mock_run:

            mock_run.return_value = '/tmp/artifacts/art-123_script.py'

            result = create_artifact(
                content='print("Hello")',
                filename='script.py',
                artifact_type='code'
            )

            assert 'artifact_id' in result
            assert result['filename'] == 'script.py'
            assert result['type'] == 'code'
            assert result['status'] == 'created'
            assert 'storage_path' in result
            assert result['size'] == str(len('print("Hello")'))

    @pytest.mark.asyncio
    async def test_create_artifact_default_type(self):
        """Test artifact creation with default type."""
        mock_file_service = AsyncMock()
        mock_file_service.save_artifact = AsyncMock(return_value='/tmp/artifacts/art-456_data.json')

        with patch('app.dependencies.get_file_service', return_value=mock_file_service), \
             patch('app.tools.file_tools.asyncio.run') as mock_run:

            mock_run.return_value = '/tmp/artifacts/art-456_data.json'

            result = create_artifact(
                content='{"key": "value"}',
                filename='data.json'
            )

            assert result['type'] == 'text'  # Default type
            assert result['status'] == 'created'

    def test_create_artifact_large_content(self):
        """Test creating artifact with large content."""
        large_content = 'x' * 50000  # 50KB content

        mock_file_service = AsyncMock()
        mock_file_service.save_artifact = AsyncMock(return_value='/tmp/artifacts/art-789_large.txt')

        with patch('app.dependencies.get_file_service', return_value=mock_file_service), \
             patch('app.tools.file_tools.asyncio.run') as mock_run:

            mock_run.return_value = '/tmp/artifacts/art-789_large.txt'

            result = create_artifact(
                content=large_content,
                filename='large.txt',
                artifact_type='data'
            )

            assert result['size'] == str(50000)
            assert result['status'] == 'created'

    def test_create_artifact_error_handling(self):
        """Test artifact creation with error."""
        mock_file_service = AsyncMock()
        mock_file_service.save_artifact = AsyncMock(side_effect=Exception("Storage error"))

        with patch('app.dependencies.get_file_service', return_value=mock_file_service), \
             patch('app.tools.file_tools.asyncio.run', side_effect=Exception("Storage error")):

            result = create_artifact(
                content='test',
                filename='test.txt',
                artifact_type='text'
            )

            assert 'error' in result
            assert result['status'] == 'error'
            assert 'Storage error' in result['error']

    def test_create_artifact_different_types(self):
        """Test creating artifacts of different types."""
        mock_file_service = AsyncMock()

        artifact_types = ['code', 'data', 'diagram', 'text']

        for artifact_type in artifact_types:
            mock_file_service.save_artifact = AsyncMock(return_value=f'/tmp/artifacts/art_{artifact_type}')

            with patch('app.dependencies.get_file_service', return_value=mock_file_service), \
                 patch('app.tools.file_tools.asyncio.run', return_value=f'/tmp/artifacts/art_{artifact_type}'):

                result = create_artifact(
                    content=f'Content for {artifact_type}',
                    filename=f'file.{artifact_type}',
                    artifact_type=artifact_type
                )

                assert result['type'] == artifact_type
                assert result['status'] == 'created'


class TestToolIntegration:
    """Integration tests for tool workflows."""

    def test_list_then_get_workflow(self, mock_request_with_files):
        """Test workflow: list attachments then get specific file content."""
        with patch('app.dependencies.get_current_request', return_value=mock_request_with_files):
            # First, list all files
            files = list_attachments()
            assert len(files) == 2

            # Then get content of first file
            first_file_id = files[0]['file_id']
            content = get_file_content(first_file_id)

            assert content['filename'] == 'screenshot.png'
            assert content['extracted_content'] == 'Text from screenshot'

    def test_multiple_artifact_creation(self):
        """Test creating multiple artifacts in sequence."""
        mock_file_service = AsyncMock()

        artifacts_to_create = [
            ('script.py', 'print("Hello")', 'code'),
            ('README.md', '# Project\n\nDescription', 'text'),
            ('data.json', '{"key": "value"}', 'data')
        ]

        created_artifacts = []

        for filename, content, artifact_type in artifacts_to_create:
            mock_file_service.save_artifact = AsyncMock(
                return_value=f'/tmp/artifacts/art_{filename}'
            )

            with patch('app.dependencies.get_file_service', return_value=mock_file_service), \
                 patch('app.tools.file_tools.asyncio.run', return_value=f'/tmp/artifacts/art_{filename}'):

                result = create_artifact(
                    content=content,
                    filename=filename,
                    artifact_type=artifact_type
                )

                created_artifacts.append(result)

        # Verify all artifacts created successfully
        assert len(created_artifacts) == 3
        assert all(a['status'] == 'created' for a in created_artifacts)
        assert created_artifacts[0]['type'] == 'code'
        assert created_artifacts[1]['type'] == 'text'
        assert created_artifacts[2]['type'] == 'data'
