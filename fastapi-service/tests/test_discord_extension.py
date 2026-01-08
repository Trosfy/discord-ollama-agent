"""
Unit tests for DiscordFileExtension.

Tests cover:
- Discord artifact registration
- File path and filename extraction from ToolResult
- Artifact metadata structure
- Discord context enrichment
- Error handling
"""
import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from typing import Dict

from app.extensions.discord_extension import DiscordFileExtension
from strands.types.tools import ToolResult


# Fixtures
@pytest.fixture
def discord_extension():
    """Create DiscordFileExtension instance."""
    return DiscordFileExtension()


@pytest.fixture
def sample_request_context() -> Dict:
    """Sample Discord request context."""
    return {
        'user_id': 'user123',
        'channel_id': 'channel456',
        'message_id': 'message789',
        'file_refs': []
    }


@pytest.fixture
def sample_file_write_success() -> ToolResult:
    """Sample successful file_write ToolResult."""
    return {
        'status': 'success',
        'toolUseId': 'test-tool-id-123',
        'content': [
            {
                'type': 'text',
                'text': 'File written successfully'
            },
            {
                'type': 'text',
                'text': 'Path: /tmp/discord-bot-artifacts/script.py',
                'path': '/tmp/discord-bot-artifacts/script.py'
            }
        ]
    }


@pytest.fixture
def sample_file_write_error() -> ToolResult:
    """Sample error file_write ToolResult."""
    return {
        'status': 'error',
        'toolUseId': 'test-tool-id-456',
        'content': [
            {
                'type': 'text',
                'text': 'Error: Permission denied'
            }
        ]
    }


@pytest.fixture
def sample_file_read_success() -> ToolResult:
    """Sample successful file_read ToolResult."""
    return {
        'status': 'success',
        'toolUseId': 'test-tool-id-789',
        'content': [
            {
                'type': 'text',
                'text': 'File content: Hello World'
            }
        ]
    }


@pytest.fixture
def temp_artifact_file():
    """Create temporary artifact file for testing."""
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.py',
        delete=False,
        dir='/tmp'
    ) as f:
        f.write('print("Hello from artifact")')
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


# DiscordFileExtension.on_file_read Tests
class TestDiscordFileExtensionOnFileRead:
    """Tests for DiscordFileExtension.on_file_read()."""

    def test_on_file_read_logs_access(
        self,
        discord_extension,
        sample_file_read_success,
        sample_request_context
    ):
        """Test on_file_read logs Discord file access."""
        result = discord_extension.on_file_read(
            sample_file_read_success,
            sample_request_context
        )

        # Should return the same result (pass-through)
        assert result == sample_file_read_success
        assert result['status'] == 'success'

    def test_on_file_read_with_error_result(
        self,
        discord_extension,
        sample_request_context
    ):
        """Test on_file_read handles error results."""
        error_result: ToolResult = {
            'status': 'error',
            'toolUseId': 'test-error',
            'content': [
                {'type': 'text', 'text': 'File not found'}
            ]
        }

        result = discord_extension.on_file_read(
            error_result,
            sample_request_context
        )

        # Should still return result (logged as error)
        assert result == error_result
        assert result['status'] == 'error'

    def test_on_file_read_with_missing_context(
        self,
        discord_extension,
        sample_file_read_success
    ):
        """Test on_file_read handles missing Discord context gracefully."""
        # Context without Discord fields
        minimal_context = {}

        # Should not raise exception
        result = discord_extension.on_file_read(
            sample_file_read_success,
            minimal_context
        )

        assert result == sample_file_read_success

    def test_on_file_read_preserves_tool_result_structure(
        self,
        discord_extension,
        sample_file_read_success,
        sample_request_context
    ):
        """Test on_file_read doesn't modify tool_result structure."""
        original_content_length = len(sample_file_read_success['content'])

        result = discord_extension.on_file_read(
            sample_file_read_success,
            sample_request_context
        )

        # Content should be unchanged
        assert len(result['content']) == original_content_length
        assert result['content'] == sample_file_read_success['content']


# DiscordFileExtension.on_file_write Tests
class TestDiscordFileExtensionOnFileWrite:
    """Tests for DiscordFileExtension.on_file_write()."""

    def test_on_file_write_registers_artifact(
        self,
        discord_extension,
        sample_file_write_success,
        sample_request_context,
        temp_artifact_file
    ):
        """Test on_file_write registers artifact for Discord upload."""
        # Patch file info to use temp file
        sample_file_write_success['content'][1]['path'] = temp_artifact_file

        discord_extension.on_file_write(
            sample_file_write_success,
            sample_request_context
        )

        # Should register artifact in request context
        assert 'artifacts_created' in sample_request_context
        assert len(sample_request_context['artifacts_created']) == 1

        artifact = sample_request_context['artifacts_created'][0]
        assert 'artifact_id' in artifact
        assert 'filename' in artifact
        assert 'storage_path' in artifact
        assert artifact['storage_path'] == temp_artifact_file
        assert 'size' in artifact
        assert 'type' in artifact
        assert artifact['type'] == 'file'
        assert 'status' in artifact
        assert artifact['status'] == 'created'

    def test_on_file_write_includes_discord_context(
        self,
        discord_extension,
        sample_file_write_success,
        sample_request_context,
        temp_artifact_file
    ):
        """Test artifact includes Discord context metadata."""
        sample_file_write_success['content'][1]['path'] = temp_artifact_file

        discord_extension.on_file_write(
            sample_file_write_success,
            sample_request_context
        )

        artifact = sample_request_context['artifacts_created'][0]
        assert 'discord_context' in artifact

        discord_context = artifact['discord_context']
        assert discord_context['user_id'] == 'user123'
        assert discord_context['channel_id'] == 'channel456'
        assert discord_context['message_id'] == 'message789'

    def test_on_file_write_skips_error_results(
        self,
        discord_extension,
        sample_file_write_error,
        sample_request_context
    ):
        """Test on_file_write skips artifact registration on error."""
        discord_extension.on_file_write(
            sample_file_write_error,
            sample_request_context
        )

        # Should not register artifact
        assert 'artifacts_created' not in sample_request_context

    def test_on_file_write_handles_multiple_artifacts(
        self,
        discord_extension,
        sample_file_write_success,
        sample_request_context,
        temp_artifact_file
    ):
        """Test on_file_write appends to existing artifacts list."""
        # Pre-existing artifact
        sample_request_context['artifacts_created'] = [
            {'filename': 'existing.txt', 'status': 'created'}
        ]

        sample_file_write_success['content'][1]['path'] = temp_artifact_file

        discord_extension.on_file_write(
            sample_file_write_success,
            sample_request_context
        )

        # Should have 2 artifacts now
        assert len(sample_request_context['artifacts_created']) == 2
        assert sample_request_context['artifacts_created'][0]['filename'] == 'existing.txt'
        assert 'filename' in sample_request_context['artifacts_created'][1]

    def test_on_file_write_with_missing_file_path(
        self,
        discord_extension,
        sample_request_context
    ):
        """Test on_file_write handles missing file path gracefully."""
        malformed_result: ToolResult = {
            'status': 'success',
            'toolUseId': 'test-malformed',
            'content': [
                {
                    'type': 'text',
                    'text': 'File written'
                    # Missing 'path' key
                }
            ]
        }

        # Should not raise exception
        discord_extension.on_file_write(
            malformed_result,
            sample_request_context
        )

        # Should not register artifact (missing required info)
        assert 'artifacts_created' not in sample_request_context

    def test_on_file_write_with_missing_filename(
        self,
        discord_extension,
        sample_request_context
    ):
        """Test on_file_write handles missing filename gracefully."""
        malformed_result: ToolResult = {
            'status': 'success',
            'toolUseId': 'test-malformed',
            'content': [
                {
                    'type': 'text',
                    'text': '',  # Empty text, can't extract filename
                    'path': '/tmp/unknown'  # Path exists but can't determine filename
                }
            ]
        }

        # Should not raise exception
        discord_extension.on_file_write(
            malformed_result,
            sample_request_context
        )

        # Should not register artifact (missing required info)
        assert 'artifacts_created' not in sample_request_context

    def test_on_file_write_generates_unique_artifact_ids(
        self,
        discord_extension,
        sample_file_write_success,
        sample_request_context,
        temp_artifact_file
    ):
        """Test each artifact gets unique ID."""
        sample_file_write_success['content'][1]['path'] = temp_artifact_file

        # Register first artifact
        discord_extension.on_file_write(
            sample_file_write_success,
            sample_request_context
        )

        # Register second artifact
        discord_extension.on_file_write(
            sample_file_write_success,
            sample_request_context
        )

        # Should have 2 artifacts with different IDs
        assert len(sample_request_context['artifacts_created']) == 2
        id1 = sample_request_context['artifacts_created'][0]['artifact_id']
        id2 = sample_request_context['artifacts_created'][1]['artifact_id']
        assert id1 != id2

    def test_on_file_write_calculates_file_size(
        self,
        discord_extension,
        sample_file_write_success,
        sample_request_context,
        temp_artifact_file
    ):
        """Test artifact includes correct file size."""
        sample_file_write_success['content'][1]['path'] = temp_artifact_file

        discord_extension.on_file_write(
            sample_file_write_success,
            sample_request_context
        )

        artifact = sample_request_context['artifacts_created'][0]
        expected_size = os.path.getsize(temp_artifact_file)

        assert 'size' in artifact
        assert int(artifact['size']) == expected_size
        assert int(artifact['size']) > 0  # Should have content


# File Path/Filename Extraction Tests
class TestFileInfoExtraction:
    """Tests for _extract_file_path and _extract_filename methods."""

    def test_extract_file_path_from_path_key(
        self,
        discord_extension
    ):
        """Test file path extraction from 'path' key in content block."""
        tool_result: ToolResult = {
            'status': 'success',
            'content': [
                {
                    'type': 'text',
                    'text': 'File written',
                    'path': '/tmp/test.txt'
                }
            ]
        }

        path = discord_extension._extract_file_path(tool_result)
        assert path == '/tmp/test.txt'

    def test_extract_file_path_from_text_content(
        self,
        discord_extension,
        temp_artifact_file
    ):
        """Test file path extraction from text content."""
        tool_result: ToolResult = {
            'status': 'success',
            'content': [
                {
                    'type': 'text',
                    'text': f'Written to: {temp_artifact_file}'
                }
            ]
        }

        path = discord_extension._extract_file_path(tool_result)
        # Should extract path from text
        assert path == temp_artifact_file

    def test_extract_file_path_returns_none_when_missing(
        self,
        discord_extension
    ):
        """Test file path extraction returns None when no path found."""
        tool_result: ToolResult = {
            'status': 'success',
            'content': [
                {
                    'type': 'text',
                    'text': 'No path here'
                }
            ]
        }

        path = discord_extension._extract_file_path(tool_result)
        assert path is None

    def test_extract_filename_from_path(
        self,
        discord_extension,
        temp_artifact_file
    ):
        """Test filename extraction from tool_result."""
        tool_result: ToolResult = {
            'status': 'success',
            'content': [
                {
                    'type': 'text',
                    'text': f'Written to: {temp_artifact_file}',
                    'filename': os.path.basename(temp_artifact_file)
                }
            ]
        }

        filename = discord_extension._extract_filename(tool_result)
        assert filename is not None
        assert filename.endswith('.py')
        assert '/' not in filename  # Should be basename only

    def test_extract_filename_returns_none_when_no_path(
        self,
        discord_extension
    ):
        """Test filename extraction returns None when no path available."""
        tool_result: ToolResult = {
            'status': 'success',
            'content': [
                {
                    'type': 'text',
                    'text': 'No path info'
                }
            ]
        }

        filename = discord_extension._extract_filename(tool_result)
        assert filename is None


# Error Handling Tests
class TestDiscordExtensionErrorHandling:
    """Tests for DiscordFileExtension error handling."""

    def test_on_file_write_handles_nonexistent_file(
        self,
        discord_extension,
        sample_request_context
    ):
        """Test on_file_write handles nonexistent file path gracefully."""
        nonexistent_result: ToolResult = {
            'status': 'success',
            'toolUseId': 'test-nonexistent',
            'content': [
                {
                    'type': 'text',
                    'text': 'File written',
                    'path': '/nonexistent/path/file.txt'
                }
            ]
        }

        # Should not raise exception
        discord_extension.on_file_write(
            nonexistent_result,
            sample_request_context
        )

        # May or may not register artifact (implementation dependent)
        # But should not crash

    def test_on_file_write_handles_empty_content(
        self,
        discord_extension,
        sample_request_context
    ):
        """Test on_file_write handles empty content list."""
        empty_result: ToolResult = {
            'status': 'success',
            'toolUseId': 'test-empty',
            'content': []
        }

        # Should not raise exception
        discord_extension.on_file_write(
            empty_result,
            sample_request_context
        )

        # Should not register artifact (no info available)
        assert 'artifacts_created' not in sample_request_context

    def test_on_file_read_handles_empty_content(
        self,
        discord_extension,
        sample_request_context
    ):
        """Test on_file_read handles empty content list."""
        empty_result: ToolResult = {
            'status': 'success',
            'toolUseId': 'test-empty',
            'content': []
        }

        # Should not raise exception
        result = discord_extension.on_file_read(
            empty_result,
            sample_request_context
        )

        assert result == empty_result

    def test_on_file_write_with_minimal_context(
        self,
        discord_extension,
        sample_file_write_success,
        temp_artifact_file
    ):
        """Test on_file_write works with minimal request context."""
        minimal_context = {}  # No Discord fields
        sample_file_write_success['content'][1]['path'] = temp_artifact_file

        # Should not raise exception
        discord_extension.on_file_write(
            sample_file_write_success,
            minimal_context
        )

        # Should still register artifact
        assert 'artifacts_created' in minimal_context

        # Discord context should have None values
        artifact = minimal_context['artifacts_created'][0]
        assert artifact['discord_context']['user_id'] is None
        assert artifact['discord_context']['channel_id'] is None
        assert artifact['discord_context']['message_id'] is None
