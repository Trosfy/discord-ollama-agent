"""
Integration tests for Strands tool wrappers.

Tests cover:
- file_read_wrapped() integration with Strands file_read
- file_write_wrapped() integration with Strands file_write
- ToolUse format creation
- ToolResult parsing and text extraction
- Extension orchestrator integration
- Request context passing
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict
import uuid

from app.tools.strands_tools_wrapped import (
    file_read_wrapped,
    file_write_wrapped,
    set_orchestrator
)
from strands.types.tools import ToolUse, ToolResult


# Fixtures
@pytest.fixture
def mock_orchestrator():
    """Mock ExtensionOrchestrator for testing."""
    orchestrator = Mock()
    orchestrator.handle_file_read = Mock(side_effect=lambda tr, ctx: tr)
    orchestrator.handle_file_write = Mock(return_value=None)
    return orchestrator


@pytest.fixture
def sample_request_context():
    """Sample request context."""
    return {
        'user_id': 'user123',
        'channel_id': 'channel456',
        'message_id': 'message789',
        'file_refs': []
    }


@pytest.fixture
def mock_strands_file_read_success():
    """Mock Strands file_read that returns success."""
    def _mock_file_read(tool_use: ToolUse) -> ToolResult:
        return {
            'status': 'success',
            'toolUseId': tool_use['toolUseId'],
            'content': [
                {
                    'type': 'text',
                    'text': f"File content from {tool_use['input']['path']}"
                }
            ]
        }
    return _mock_file_read


@pytest.fixture
def mock_strands_file_read_error():
    """Mock Strands file_read that returns error."""
    def _mock_file_read(tool_use: ToolUse) -> ToolResult:
        return {
            'status': 'error',
            'toolUseId': tool_use['toolUseId'],
            'content': [
                {
                    'type': 'text',
                    'text': 'Error: File not found'
                }
            ]
        }
    return _mock_file_read


@pytest.fixture
def mock_strands_file_write_success():
    """Mock Strands file_write that returns success."""
    def _mock_file_write(tool_use: ToolUse) -> ToolResult:
        return {
            'status': 'success',
            'toolUseId': tool_use['toolUseId'],
            'content': [
                {
                    'type': 'text',
                    'text': 'File written successfully',
                    'path': tool_use['input']['path']
                }
            ]
        }
    return _mock_file_write


@pytest.fixture
def mock_strands_file_write_error():
    """Mock Strands file_write that returns error."""
    def _mock_file_write(tool_use: ToolUse) -> ToolResult:
        return {
            'status': 'error',
            'toolUseId': tool_use['toolUseId'],
            'content': [
                {
                    'type': 'text',
                    'text': 'Error: Permission denied'
                }
            ]
        }
    return _mock_file_write


@pytest.fixture
def mock_get_current_request(sample_request_context):
    """Mock get_current_request dependency."""
    with patch('app.dependencies.get_current_request') as mock:
        mock.return_value = sample_request_context
        yield mock


# file_read_wrapped Tests
class TestFileReadWrapped:
    """Tests for file_read_wrapped() function."""

    def test_file_read_wrapped_success(
        self,
        mock_strands_file_read_success,
        mock_get_current_request,
        mock_orchestrator
    ):
        """Test file_read_wrapped with successful read."""
        set_orchestrator(mock_orchestrator)

        with patch('app.tools.strands_tools_wrapped.strands_file_read', mock_strands_file_read_success):
            result = file_read_wrapped('/tmp/test.txt')

        # Should return extracted text
        assert isinstance(result, str)
        assert 'File content from /tmp/test.txt' in result

        # Should call orchestrator
        assert mock_orchestrator.handle_file_read.called

    def test_file_read_wrapped_with_mode(
        self,
        mock_strands_file_read_success,
        mock_get_current_request,
        mock_orchestrator
    ):
        """Test file_read_wrapped with mode parameter."""
        set_orchestrator(mock_orchestrator)

        with patch('app.tools.strands_tools_wrapped.strands_file_read', mock_strands_file_read_success):
            result = file_read_wrapped('/tmp/test.txt', mode='preview')

        assert isinstance(result, str)
        assert 'File content' in result

    def test_file_read_wrapped_creates_tool_use(
        self,
        mock_get_current_request,
        mock_orchestrator
    ):
        """Test file_read_wrapped creates proper ToolUse format."""
        set_orchestrator(mock_orchestrator)

        captured_tool_use = None

        def capture_tool_use(tool_use: ToolUse) -> ToolResult:
            nonlocal captured_tool_use
            captured_tool_use = tool_use
            return {
                'status': 'success',
                'toolUseId': tool_use['toolUseId'],
                'content': [{'type': 'text', 'text': 'content'}]
            }

        with patch('app.tools.strands_tools_wrapped.strands_file_read', capture_tool_use):
            file_read_wrapped('/tmp/test.txt', mode='view')

        # Check ToolUse structure
        assert captured_tool_use is not None
        assert captured_tool_use['name'] == 'file_read'
        assert 'toolUseId' in captured_tool_use
        assert 'input' in captured_tool_use
        assert captured_tool_use['input']['path'] == '/tmp/test.txt'
        assert captured_tool_use['input']['mode'] == 'view'

    def test_file_read_wrapped_extracts_text_from_tool_result(
        self,
        mock_get_current_request,
        mock_orchestrator
    ):
        """Test file_read_wrapped extracts text from ToolResult content."""
        set_orchestrator(mock_orchestrator)

        def multi_block_result(tool_use: ToolUse) -> ToolResult:
            return {
                'status': 'success',
                'toolUseId': tool_use['toolUseId'],
                'content': [
                    {'type': 'text', 'text': 'Line 1'},
                    {'type': 'text', 'text': 'Line 2'},
                    {'type': 'text', 'text': 'Line 3'},
                ]
            }

        with patch('app.tools.strands_tools_wrapped.strands_file_read', multi_block_result):
            result = file_read_wrapped('/tmp/test.txt')

        # Should join all text blocks
        assert 'Line 1' in result
        assert 'Line 2' in result
        assert 'Line 3' in result

    def test_file_read_wrapped_error_handling(
        self,
        mock_strands_file_read_error,
        mock_get_current_request,
        mock_orchestrator
    ):
        """Test file_read_wrapped handles error ToolResult."""
        set_orchestrator(mock_orchestrator)

        with patch('app.tools.strands_tools_wrapped.strands_file_read', mock_strands_file_read_error):
            result = file_read_wrapped('/nonexistent.txt')

        # Should return error message
        assert 'Error reading file' in result
        assert 'File not found' in result

    def test_file_read_wrapped_passes_context_to_orchestrator(
        self,
        mock_strands_file_read_success,
        mock_get_current_request,
        mock_orchestrator,
        sample_request_context
    ):
        """Test file_read_wrapped passes request context to orchestrator."""
        set_orchestrator(mock_orchestrator)

        with patch('app.tools.strands_tools_wrapped.strands_file_read', mock_strands_file_read_success):
            file_read_wrapped('/tmp/test.txt')

        # Check orchestrator was called with context
        assert mock_orchestrator.handle_file_read.called
        call_args = mock_orchestrator.handle_file_read.call_args
        assert call_args[0][1] == sample_request_context  # Second arg is request_context

    def test_file_read_wrapped_without_orchestrator(
        self,
        mock_strands_file_read_success,
        mock_get_current_request
    ):
        """Test file_read_wrapped works without orchestrator."""
        set_orchestrator(None)  # No orchestrator

        with patch('app.tools.strands_tools_wrapped.strands_file_read', mock_strands_file_read_success):
            result = file_read_wrapped('/tmp/test.txt')

        # Should still work (no extension processing)
        assert isinstance(result, str)
        assert 'File content' in result

    def test_file_read_wrapped_orchestrator_exception_handling(
        self,
        mock_strands_file_read_success,
        mock_get_current_request
    ):
        """Test file_read_wrapped handles orchestrator exceptions."""
        failing_orchestrator = Mock()
        failing_orchestrator.handle_file_read = Mock(side_effect=RuntimeError("Extension error"))
        set_orchestrator(failing_orchestrator)

        with patch('app.tools.strands_tools_wrapped.strands_file_read', mock_strands_file_read_success):
            # Should not raise exception
            result = file_read_wrapped('/tmp/test.txt')

        # Should return original result (extension failed)
        assert isinstance(result, str)
        assert 'File content' in result

    def test_file_read_wrapped_with_kwargs(
        self,
        mock_get_current_request,
        mock_orchestrator
    ):
        """Test file_read_wrapped passes through additional kwargs."""
        set_orchestrator(mock_orchestrator)

        captured_tool_use = None

        def capture_tool_use(tool_use: ToolUse) -> ToolResult:
            nonlocal captured_tool_use
            captured_tool_use = tool_use
            return {
                'status': 'success',
                'toolUseId': tool_use['toolUseId'],
                'content': [{'type': 'text', 'text': 'content'}]
            }

        with patch('app.tools.strands_tools_wrapped.strands_file_read', capture_tool_use):
            file_read_wrapped('/tmp/test.txt', mode='view', custom_param='value')

        # Check kwargs were passed
        assert captured_tool_use['input']['custom_param'] == 'value'


# file_write_wrapped Tests
class TestFileWriteWrapped:
    """Tests for file_write_wrapped() function."""

    def test_file_write_wrapped_success(
        self,
        mock_strands_file_write_success,
        mock_get_current_request,
        mock_orchestrator
    ):
        """Test file_write_wrapped with successful write."""
        set_orchestrator(mock_orchestrator)

        with patch('app.tools.strands_tools_wrapped.strands_file_write', mock_strands_file_write_success):
            result = file_write_wrapped('/tmp/test.txt', 'content')

        # Should return success message
        assert isinstance(result, str)
        assert 'File written successfully' in result

        # Should call orchestrator
        assert mock_orchestrator.handle_file_write.called

    def test_file_write_wrapped_creates_tool_use(
        self,
        mock_get_current_request,
        mock_orchestrator
    ):
        """Test file_write_wrapped creates proper ToolUse format."""
        set_orchestrator(mock_orchestrator)

        captured_tool_use = None

        def capture_tool_use(tool_use: ToolUse) -> ToolResult:
            nonlocal captured_tool_use
            captured_tool_use = tool_use
            return {
                'status': 'success',
                'toolUseId': tool_use['toolUseId'],
                'content': [{'type': 'text', 'text': 'success'}]
            }

        with patch('app.tools.strands_tools_wrapped.strands_file_write', capture_tool_use):
            file_write_wrapped('/tmp/test.txt', 'Hello World')

        # Check ToolUse structure
        assert captured_tool_use is not None
        assert captured_tool_use['name'] == 'file_write'
        assert 'toolUseId' in captured_tool_use
        assert 'input' in captured_tool_use
        assert captured_tool_use['input']['path'] == '/tmp/test.txt'
        assert captured_tool_use['input']['content'] == 'Hello World'

    def test_file_write_wrapped_error_handling(
        self,
        mock_strands_file_write_error,
        mock_get_current_request,
        mock_orchestrator
    ):
        """Test file_write_wrapped handles error ToolResult."""
        set_orchestrator(mock_orchestrator)

        with patch('app.tools.strands_tools_wrapped.strands_file_write', mock_strands_file_write_error):
            result = file_write_wrapped('/readonly/test.txt', 'content')

        # Should return error message
        assert 'Error writing file' in result
        assert 'Permission denied' in result

    def test_file_write_wrapped_passes_context_to_orchestrator(
        self,
        mock_strands_file_write_success,
        mock_get_current_request,
        mock_orchestrator,
        sample_request_context
    ):
        """Test file_write_wrapped passes request context to orchestrator."""
        set_orchestrator(mock_orchestrator)

        with patch('app.tools.strands_tools_wrapped.strands_file_write', mock_strands_file_write_success):
            file_write_wrapped('/tmp/test.txt', 'content')

        # Check orchestrator was called with context
        assert mock_orchestrator.handle_file_write.called
        call_args = mock_orchestrator.handle_file_write.call_args
        assert call_args[0][1] == sample_request_context  # Second arg is request_context

    def test_file_write_wrapped_without_orchestrator(
        self,
        mock_strands_file_write_success,
        mock_get_current_request
    ):
        """Test file_write_wrapped works without orchestrator."""
        set_orchestrator(None)  # No orchestrator

        with patch('app.tools.strands_tools_wrapped.strands_file_write', mock_strands_file_write_success):
            result = file_write_wrapped('/tmp/test.txt', 'content')

        # Should still work (no extension processing)
        assert isinstance(result, str)
        assert 'File written successfully' in result

    def test_file_write_wrapped_orchestrator_exception_handling(
        self,
        mock_strands_file_write_success,
        mock_get_current_request
    ):
        """Test file_write_wrapped handles orchestrator exceptions."""
        failing_orchestrator = Mock()
        failing_orchestrator.handle_file_write = Mock(side_effect=RuntimeError("Extension error"))
        set_orchestrator(failing_orchestrator)

        with patch('app.tools.strands_tools_wrapped.strands_file_write', mock_strands_file_write_success):
            # Should not raise exception
            result = file_write_wrapped('/tmp/test.txt', 'content')

        # Should return success (extension failed but file written)
        assert isinstance(result, str)
        assert 'File written successfully' in result

    def test_file_write_wrapped_returns_default_message_on_empty_content(
        self,
        mock_get_current_request,
        mock_orchestrator
    ):
        """Test file_write_wrapped returns default message when ToolResult has no text."""
        set_orchestrator(mock_orchestrator)

        def empty_content_result(tool_use: ToolUse) -> ToolResult:
            return {
                'status': 'success',
                'toolUseId': tool_use['toolUseId'],
                'content': []  # Empty content
            }

        with patch('app.tools.strands_tools_wrapped.strands_file_write', empty_content_result):
            result = file_write_wrapped('/tmp/test.txt', 'content')

        # Should return default message
        assert result == "File written successfully"


# set_orchestrator Tests
class TestSetOrchestrator:
    """Tests for set_orchestrator() function."""

    def test_set_orchestrator(self, mock_orchestrator):
        """Test set_orchestrator sets global orchestrator."""
        set_orchestrator(mock_orchestrator)

        # Should be accessible by wrapped tools
        # (Tested indirectly through file_read/write_wrapped tests)

    def test_set_orchestrator_to_none(self):
        """Test set_orchestrator can clear orchestrator."""
        set_orchestrator(None)

        # Should not crash when tools are called without orchestrator
        # (Tested in file_read/write_wrapped_without_orchestrator tests)


# Integration Tests
class TestStrandsToolsWrappedIntegration:
    """Integration tests for Strands tool wrappers."""

    def test_full_file_read_workflow(
        self,
        mock_strands_file_read_success,
        mock_get_current_request,
        mock_orchestrator
    ):
        """Test complete file_read workflow: wrapper → Strands → orchestrator → result."""
        set_orchestrator(mock_orchestrator)

        # Track calls
        orchestrator_called = False

        def track_orchestrator_call(tool_result, request_context):
            nonlocal orchestrator_called
            orchestrator_called = True
            # Simulate extension enhancement
            tool_result['content'].append({
                'type': 'text',
                'text': '\n[Enhanced by extension]'
            })
            return tool_result

        mock_orchestrator.handle_file_read = track_orchestrator_call

        with patch('app.tools.strands_tools_wrapped.strands_file_read', mock_strands_file_read_success):
            result = file_read_wrapped('/tmp/test.txt')

        # Orchestrator should be called
        assert orchestrator_called

        # Result should include enhancement
        assert '[Enhanced by extension]' in result

    def test_full_file_write_workflow(
        self,
        mock_strands_file_write_success,
        mock_get_current_request,
        mock_orchestrator,
        sample_request_context
    ):
        """Test complete file_write workflow: wrapper → Strands → orchestrator → result."""
        set_orchestrator(mock_orchestrator)

        # Track artifact registration
        def track_orchestrator_call(tool_result, request_context):
            # Simulate artifact registration
            if 'artifacts_created' not in request_context:
                request_context['artifacts_created'] = []
            request_context['artifacts_created'].append({
                'filename': 'test.txt',
                'status': 'created'
            })

        mock_orchestrator.handle_file_write = track_orchestrator_call

        with patch('app.tools.strands_tools_wrapped.strands_file_write', mock_strands_file_write_success):
            result = file_write_wrapped('/tmp/test.txt', 'content')

        # Artifact should be registered
        assert 'artifacts_created' in sample_request_context
        assert len(sample_request_context['artifacts_created']) == 1

    def test_tool_use_id_generation(
        self,
        mock_get_current_request,
        mock_orchestrator
    ):
        """Test each tool call generates unique toolUseId."""
        set_orchestrator(mock_orchestrator)

        captured_ids = []

        def capture_id(tool_use: ToolUse) -> ToolResult:
            captured_ids.append(tool_use['toolUseId'])
            return {
                'status': 'success',
                'toolUseId': tool_use['toolUseId'],
                'content': [{'type': 'text', 'text': 'content'}]
            }

        with patch('app.tools.strands_tools_wrapped.strands_file_read', capture_id):
            file_read_wrapped('/tmp/file1.txt')
            file_read_wrapped('/tmp/file2.txt')
            file_read_wrapped('/tmp/file3.txt')

        # All IDs should be unique
        assert len(captured_ids) == 3
        assert len(set(captured_ids)) == 3  # All unique

    def test_error_propagation_through_layers(
        self,
        mock_strands_file_read_error,
        mock_get_current_request,
        mock_orchestrator
    ):
        """Test errors propagate through all layers correctly."""
        set_orchestrator(mock_orchestrator)

        with patch('app.tools.strands_tools_wrapped.strands_file_read', mock_strands_file_read_error):
            result = file_read_wrapped('/nonexistent.txt')

        # Error should be propagated
        assert 'Error reading file' in result

        # Orchestrator should still be called (can process errors)
        assert mock_orchestrator.handle_file_read.called
