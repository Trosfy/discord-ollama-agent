"""
Unit tests for ExtensionOrchestrator and IFileExtension interface.

Tests cover:
- Extension protocol compliance
- Orchestrator coordination
- Extension chaining behavior
- Error handling and isolation
"""
import pytest
from unittest.mock import Mock, patch
from typing import Dict

from app.extensions.interface import IFileExtension
from app.extensions.orchestrator import ExtensionOrchestrator
from strands.types.tools import ToolResult


# Mock Extension Implementations for Testing
class MockSuccessExtension:
    """Mock extension that successfully processes tool results."""

    def __init__(self, name: str = "MockSuccess"):
        self.name = name
        self.on_file_read_called = False
        self.on_file_write_called = False
        self.read_call_count = 0
        self.write_call_count = 0

    def on_file_read(
        self,
        tool_result: ToolResult,
        request_context: Dict
    ) -> ToolResult:
        """Mock file_read handler that adds metadata."""
        self.on_file_read_called = True
        self.read_call_count += 1

        # Add extension marker to tool_result
        if 'content' not in tool_result:
            tool_result['content'] = []

        tool_result['content'].append({
            'type': 'text',
            'text': f'\n[Processed by {self.name}]'
        })

        return tool_result

    def on_file_write(
        self,
        tool_result: ToolResult,
        request_context: Dict
    ) -> None:
        """Mock file_write handler."""
        self.on_file_write_called = True
        self.write_call_count += 1

        # Simulate artifact registration
        if 'artifacts_created' not in request_context:
            request_context['artifacts_created'] = []

        request_context['artifacts_created'].append({
            'extension': self.name,
            'processed': True
        })


class MockFailingExtension:
    """Mock extension that raises exceptions."""

    def __init__(self, fail_on: str = "both"):
        """
        Initialize failing extension.

        Args:
            fail_on: "read", "write", or "both"
        """
        self.fail_on = fail_on
        self.exception_message = "Mock extension failure"

    def on_file_read(
        self,
        tool_result: ToolResult,
        request_context: Dict
    ) -> ToolResult:
        """Raises exception if configured to fail on read."""
        if self.fail_on in ["read", "both"]:
            raise RuntimeError(self.exception_message)
        return tool_result

    def on_file_write(
        self,
        tool_result: ToolResult,
        request_context: Dict
    ) -> None:
        """Raises exception if configured to fail on write."""
        if self.fail_on in ["write", "both"]:
            raise RuntimeError(self.exception_message)


class MockSkipExtension:
    """Mock extension that does nothing (pass-through)."""

    def on_file_read(
        self,
        tool_result: ToolResult,
        request_context: Dict
    ) -> ToolResult:
        """Pass-through handler."""
        return tool_result

    def on_file_write(
        self,
        tool_result: ToolResult,
        request_context: Dict
    ) -> None:
        """Pass-through handler."""
        pass


# Fixtures
@pytest.fixture
def sample_tool_result_success() -> ToolResult:
    """Sample successful ToolResult."""
    return {
        'status': 'success',
        'toolUseId': 'test-tool-id-123',
        'content': [
            {
                'type': 'text',
                'text': 'File content here'
            }
        ]
    }


@pytest.fixture
def sample_tool_result_error() -> ToolResult:
    """Sample error ToolResult."""
    return {
        'status': 'error',
        'toolUseId': 'test-tool-id-456',
        'content': [
            {
                'type': 'text',
                'text': 'Error: File not found'
            }
        ]
    }


@pytest.fixture
def sample_request_context() -> Dict:
    """Sample request context."""
    return {
        'user_id': 'user123',
        'channel_id': 'channel456',
        'message_id': 'message789',
        'file_refs': []
    }


# ExtensionOrchestrator Tests
class TestExtensionOrchestrator:
    """Tests for ExtensionOrchestrator coordination logic."""

    def test_initialization_with_single_extension(self):
        """Test orchestrator initialization with one extension."""
        extension = MockSuccessExtension()
        orchestrator = ExtensionOrchestrator([extension])

        assert orchestrator.extensions == [extension]
        assert len(orchestrator.extensions) == 1

    def test_initialization_with_multiple_extensions(self):
        """Test orchestrator initialization with multiple extensions."""
        ext1 = MockSuccessExtension("Ext1")
        ext2 = MockSuccessExtension("Ext2")
        ext3 = MockSuccessExtension("Ext3")

        orchestrator = ExtensionOrchestrator([ext1, ext2, ext3])

        assert len(orchestrator.extensions) == 3
        assert orchestrator.extensions[0].name == "Ext1"
        assert orchestrator.extensions[1].name == "Ext2"
        assert orchestrator.extensions[2].name == "Ext3"

    def test_initialization_with_empty_list(self):
        """Test orchestrator initialization with no extensions."""
        orchestrator = ExtensionOrchestrator([])

        assert orchestrator.extensions == []
        assert len(orchestrator.extensions) == 0

    def test_handle_file_read_single_extension(
        self,
        sample_tool_result_success,
        sample_request_context
    ):
        """Test file_read processing with single extension."""
        extension = MockSuccessExtension()
        orchestrator = ExtensionOrchestrator([extension])

        result = orchestrator.handle_file_read(
            sample_tool_result_success,
            sample_request_context
        )

        assert extension.on_file_read_called
        assert extension.read_call_count == 1
        assert result['status'] == 'success'
        assert '[Processed by MockSuccess]' in result['content'][1]['text']

    def test_handle_file_read_extension_chain(
        self,
        sample_tool_result_success,
        sample_request_context
    ):
        """Test file_read processing chains through multiple extensions."""
        ext1 = MockSuccessExtension("Ext1")
        ext2 = MockSuccessExtension("Ext2")
        ext3 = MockSuccessExtension("Ext3")

        orchestrator = ExtensionOrchestrator([ext1, ext2, ext3])

        result = orchestrator.handle_file_read(
            sample_tool_result_success,
            sample_request_context
        )

        # All extensions should be called
        assert ext1.on_file_read_called
        assert ext2.on_file_read_called
        assert ext3.on_file_read_called

        # Each extension called exactly once
        assert ext1.read_call_count == 1
        assert ext2.read_call_count == 1
        assert ext3.read_call_count == 1

        # Extensions processed in order
        content_text = '\n'.join(block['text'] for block in result['content'])
        assert content_text.index('Ext1') < content_text.index('Ext2')
        assert content_text.index('Ext2') < content_text.index('Ext3')

    def test_handle_file_read_with_failing_extension(
        self,
        sample_tool_result_success,
        sample_request_context
    ):
        """Test file_read continues after extension failure."""
        ext1 = MockSuccessExtension("Ext1")
        ext2 = MockFailingExtension(fail_on="read")
        ext3 = MockSuccessExtension("Ext3")

        orchestrator = ExtensionOrchestrator([ext1, ext2, ext3])

        # Should not raise exception
        result = orchestrator.handle_file_read(
            sample_tool_result_success,
            sample_request_context
        )

        # Ext1 and Ext3 should still process
        assert ext1.on_file_read_called
        assert ext3.on_file_read_called

        # Result should include both successful extensions
        content_text = '\n'.join(block['text'] for block in result['content'])
        assert '[Processed by Ext1]' in content_text
        assert '[Processed by Ext3]' in content_text

    def test_handle_file_read_with_no_extensions(
        self,
        sample_tool_result_success,
        sample_request_context
    ):
        """Test file_read with empty extension list returns original result."""
        orchestrator = ExtensionOrchestrator([])

        result = orchestrator.handle_file_read(
            sample_tool_result_success,
            sample_request_context
        )

        # Result should be unchanged
        assert result == sample_tool_result_success
        assert len(result['content']) == 1

    def test_handle_file_write_single_extension(
        self,
        sample_tool_result_success,
        sample_request_context
    ):
        """Test file_write processing with single extension."""
        extension = MockSuccessExtension()
        orchestrator = ExtensionOrchestrator([extension])

        orchestrator.handle_file_write(
            sample_tool_result_success,
            sample_request_context
        )

        assert extension.on_file_write_called
        assert extension.write_call_count == 1
        assert 'artifacts_created' in sample_request_context
        assert len(sample_request_context['artifacts_created']) == 1

    def test_handle_file_write_extension_chain(
        self,
        sample_tool_result_success,
        sample_request_context
    ):
        """Test file_write processing chains through multiple extensions."""
        ext1 = MockSuccessExtension("Ext1")
        ext2 = MockSuccessExtension("Ext2")
        ext3 = MockSuccessExtension("Ext3")

        orchestrator = ExtensionOrchestrator([ext1, ext2, ext3])

        orchestrator.handle_file_write(
            sample_tool_result_success,
            sample_request_context
        )

        # All extensions should be called
        assert ext1.on_file_write_called
        assert ext2.on_file_write_called
        assert ext3.on_file_write_called

        # All extensions should register artifacts
        assert len(sample_request_context['artifacts_created']) == 3
        assert sample_request_context['artifacts_created'][0]['extension'] == 'Ext1'
        assert sample_request_context['artifacts_created'][1]['extension'] == 'Ext2'
        assert sample_request_context['artifacts_created'][2]['extension'] == 'Ext3'

    def test_handle_file_write_with_failing_extension(
        self,
        sample_tool_result_success,
        sample_request_context
    ):
        """Test file_write continues after extension failure."""
        ext1 = MockSuccessExtension("Ext1")
        ext2 = MockFailingExtension(fail_on="write")
        ext3 = MockSuccessExtension("Ext3")

        orchestrator = ExtensionOrchestrator([ext1, ext2, ext3])

        # Should not raise exception
        orchestrator.handle_file_write(
            sample_tool_result_success,
            sample_request_context
        )

        # Ext1 and Ext3 should still process
        assert ext1.on_file_write_called
        assert ext3.on_file_write_called

        # Both successful extensions should register artifacts
        assert len(sample_request_context['artifacts_created']) == 2
        assert sample_request_context['artifacts_created'][0]['extension'] == 'Ext1'
        assert sample_request_context['artifacts_created'][1]['extension'] == 'Ext3'

    def test_handle_file_write_with_no_extensions(
        self,
        sample_tool_result_success,
        sample_request_context
    ):
        """Test file_write with empty extension list is no-op."""
        orchestrator = ExtensionOrchestrator([])

        orchestrator.handle_file_write(
            sample_tool_result_success,
            sample_request_context
        )

        # Context should be unchanged
        assert 'artifacts_created' not in sample_request_context

    def test_handle_file_read_preserves_error_status(
        self,
        sample_tool_result_error,
        sample_request_context
    ):
        """Test extensions can process error results."""
        extension = MockSuccessExtension()
        orchestrator = ExtensionOrchestrator([extension])

        result = orchestrator.handle_file_read(
            sample_tool_result_error,
            sample_request_context
        )

        # Extension should still be called
        assert extension.on_file_read_called

        # Error status should be preserved
        assert result['status'] == 'error'

        # Extension can still add content
        assert '[Processed by MockSuccess]' in result['content'][1]['text']

    def test_handle_file_write_with_error_result(
        self,
        sample_tool_result_error,
        sample_request_context
    ):
        """Test extensions called even with error results."""
        extension = MockSuccessExtension()
        orchestrator = ExtensionOrchestrator([extension])

        orchestrator.handle_file_write(
            sample_tool_result_error,
            sample_request_context
        )

        # Extension should still be called (it can decide to skip)
        assert extension.on_file_write_called

        # Extension can still register artifacts (if it chooses)
        assert 'artifacts_created' in sample_request_context

    def test_extension_isolation(
        self,
        sample_tool_result_success,
        sample_request_context
    ):
        """Test that exception in one extension doesn't affect others."""
        # All extensions fail
        ext1 = MockFailingExtension(fail_on="both")
        ext2 = MockFailingExtension(fail_on="both")
        ext3 = MockFailingExtension(fail_on="both")

        orchestrator = ExtensionOrchestrator([ext1, ext2, ext3])

        # Should not raise exception
        result = orchestrator.handle_file_read(
            sample_tool_result_success,
            sample_request_context
        )

        # Original result should be returned (no modifications)
        assert result == sample_tool_result_success

        # Should not raise exception for file_write either
        orchestrator.handle_file_write(
            sample_tool_result_success,
            sample_request_context
        )


# IFileExtension Protocol Tests
class TestIFileExtensionProtocol:
    """Tests for IFileExtension protocol compliance."""

    def test_mock_success_extension_implements_protocol(self):
        """Test MockSuccessExtension implements IFileExtension."""
        extension = MockSuccessExtension()

        # Should have required methods
        assert hasattr(extension, 'on_file_read')
        assert hasattr(extension, 'on_file_write')

        # Methods should be callable
        assert callable(extension.on_file_read)
        assert callable(extension.on_file_write)

    def test_mock_failing_extension_implements_protocol(self):
        """Test MockFailingExtension implements IFileExtension."""
        extension = MockFailingExtension()

        assert hasattr(extension, 'on_file_read')
        assert hasattr(extension, 'on_file_write')
        assert callable(extension.on_file_read)
        assert callable(extension.on_file_write)

    def test_mock_skip_extension_implements_protocol(self):
        """Test MockSkipExtension implements IFileExtension."""
        extension = MockSkipExtension()

        assert hasattr(extension, 'on_file_read')
        assert hasattr(extension, 'on_file_write')
        assert callable(extension.on_file_read)
        assert callable(extension.on_file_write)

    def test_extension_on_file_read_signature(
        self,
        sample_tool_result_success,
        sample_request_context
    ):
        """Test on_file_read has correct signature."""
        extension = MockSuccessExtension()

        # Should accept ToolResult and Dict
        result = extension.on_file_read(
            sample_tool_result_success,
            sample_request_context
        )

        # Should return ToolResult
        assert isinstance(result, dict)
        assert 'status' in result
        assert 'content' in result

    def test_extension_on_file_write_signature(
        self,
        sample_tool_result_success,
        sample_request_context
    ):
        """Test on_file_write has correct signature."""
        extension = MockSuccessExtension()

        # Should accept ToolResult and Dict
        # Should return None
        result = extension.on_file_write(
            sample_tool_result_success,
            sample_request_context
        )

        assert result is None
