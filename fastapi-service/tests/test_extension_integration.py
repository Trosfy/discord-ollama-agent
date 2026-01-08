"""
End-to-end integration tests for the extension architecture.

Tests cover:
- Full extension chain (Strands → OCR → Discord)
- Artifact registration in request context
- Error propagation and isolation
- Multiple file operations
- Real-world scenarios
"""
import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from typing import Dict

from app.extensions.orchestrator import ExtensionOrchestrator
from app.extensions.discord_extension import DiscordFileExtension
from app.extensions.image_ocr_extension import ImageOCRExtension
from app.tools.strands_tools_wrapped import (
    file_read_wrapped,
    file_write_wrapped,
    set_orchestrator
)
from strands.types.tools import ToolUse, ToolResult


# Fixtures
@pytest.fixture
def full_orchestrator():
    """Create ExtensionOrchestrator with all extensions."""
    return ExtensionOrchestrator([
        ImageOCRExtension(),
        DiscordFileExtension()
    ])


@pytest.fixture
def sample_request_context_with_image():
    """Request context with image file_refs."""
    return {
        'user_id': 'user123',
        'channel_id': 'channel456',
        'message_id': 'message789',
        'file_refs': [
            {
                'file_id': 'img001',
                'filename': 'screenshot.png',
                'storage_path': '/tmp/discord-bot-uploads/screenshot.png',
                'extracted_content': 'OCR: Hello from image'
            }
        ]
    }


@pytest.fixture
def temp_image_file():
    """Create temporary image file."""
    # Minimal PNG file
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

    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def temp_text_file():
    """Create temporary text file."""
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.txt',
        delete=False,
        dir='/tmp'
    ) as f:
        f.write('Hello World\nThis is a test file.')
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def mock_strands_file_read_image():
    """Mock Strands file_read for image files."""
    def _mock_read(tool_use: ToolUse) -> ToolResult:
        path = tool_use['input']['path']
        return {
            'status': 'success',
            'toolUseId': tool_use['toolUseId'],
            'content': [
                {
                    'type': 'text',
                    'text': f'File: {path} Type: PNG Size: 1KB'
                }
            ]
        }
    return _mock_read


@pytest.fixture
def mock_strands_file_read_text():
    """Mock Strands file_read for text files."""
    def _mock_read(tool_use: ToolUse) -> ToolResult:
        path = tool_use['input']['path']
        return {
            'status': 'success',
            'toolUseId': tool_use['toolUseId'],
            'content': [
                {
                    'type': 'text',
                    'text': f'File: {path}\nContent: Hello World'
                }
            ]
        }
    return _mock_read


@pytest.fixture
def mock_strands_file_write():
    """Mock Strands file_write."""
    def _mock_write(tool_use: ToolUse) -> ToolResult:
        path = tool_use['input']['path']
        return {
            'status': 'success',
            'toolUseId': tool_use['toolUseId'],
            'content': [
                {
                    'type': 'text',
                    'text': f'File written to {path}',
                    'path': path
                }
            ]
        }
    return _mock_write


# Full Extension Chain Tests
class TestFullExtensionChain:
    """Tests for complete extension chain workflow."""

    def test_image_read_full_chain(
        self,
        full_orchestrator,
        mock_strands_file_read_image,
        sample_request_context_with_image,
        temp_image_file
    ):
        """Test image reading goes through OCR → Discord chain."""
        set_orchestrator(full_orchestrator)

        # Update context with temp file path
        sample_request_context_with_image['file_refs'][0]['storage_path'] = temp_image_file

        with patch('app.dependencies.get_current_request', return_value=sample_request_context_with_image):
            with patch('app.tools.strands_tools_wrapped.strands_file_read', mock_strands_file_read_image):
                result = file_read_wrapped(temp_image_file)

        # Should include original content
        assert f'File: {temp_image_file}' in result

        # Should include OCR enhancement
        assert 'OCR Extracted Text' in result
        assert 'Hello from image' in result

    def test_text_file_read_skips_ocr(
        self,
        full_orchestrator,
        mock_strands_file_read_text,
        temp_text_file
    ):
        """Test text file reading skips OCR extension."""
        set_orchestrator(full_orchestrator)

        context = {
            'user_id': 'user123',
            'channel_id': 'channel456',
            'file_refs': []
        }

        with patch('app.dependencies.get_current_request', return_value=context):
            with patch('app.tools.strands_tools_wrapped.strands_file_read', mock_strands_file_read_text):
                result = file_read_wrapped(temp_text_file)

        # Should include file content
        assert 'Hello World' in result

        # Should NOT include OCR marker (not an image)
        assert 'OCR Extracted Text' not in result

    def test_file_write_full_chain(
        self,
        full_orchestrator,
        mock_strands_file_write,
        temp_text_file
    ):
        """Test file writing goes through Discord extension."""
        set_orchestrator(full_orchestrator)

        context = {
            'user_id': 'user123',
            'channel_id': 'channel456',
            'message_id': 'message789',
            'file_refs': []
        }

        with patch('app.dependencies.get_current_request', return_value=context):
            with patch('app.tools.strands_tools_wrapped.strands_file_write', mock_strands_file_write):
                result = file_write_wrapped(temp_text_file, 'New content')

        # Should succeed
        assert 'File written' in result

        # Should register artifact in context
        assert 'artifacts_created' in context
        assert len(context['artifacts_created']) == 1

        # Check artifact metadata
        artifact = context['artifacts_created'][0]
        assert artifact['storage_path'] == temp_text_file
        assert artifact['discord_context']['user_id'] == 'user123'
        assert artifact['discord_context']['channel_id'] == 'channel456'


# Extension Order Tests
class TestExtensionOrder:
    """Tests for extension execution order."""

    def test_extensions_execute_in_order(self):
        """Test extensions execute in registration order."""
        call_order = []

        class OrderTestExtension1:
            def on_file_read(self, tool_result, request_context):
                call_order.append('ext1')
                return tool_result

            def on_file_write(self, tool_result, request_context):
                call_order.append('ext1')

        class OrderTestExtension2:
            def on_file_read(self, tool_result, request_context):
                call_order.append('ext2')
                return tool_result

            def on_file_write(self, tool_result, request_context):
                call_order.append('ext2')

        orchestrator = ExtensionOrchestrator([
            OrderTestExtension1(),
            OrderTestExtension2()
        ])

        tool_result = {
            'status': 'success',
            'content': [{'type': 'text', 'text': 'test'}]
        }
        context = {}

        # Test file_read order
        orchestrator.handle_file_read(tool_result, context)
        assert call_order == ['ext1', 'ext2']

        # Test file_write order
        call_order.clear()
        orchestrator.handle_file_write(tool_result, context)
        assert call_order == ['ext1', 'ext2']

    def test_ocr_before_discord_for_image(
        self,
        full_orchestrator,
        mock_strands_file_read_image,
        sample_request_context_with_image,
        temp_image_file
    ):
        """Test OCR extension runs before Discord extension for images."""
        # Track extension calls
        ocr_called = False
        discord_called = False
        call_order = []

        original_ocr_on_file_read = ImageOCRExtension.on_file_read
        original_discord_on_file_read = DiscordFileExtension.on_file_read

        def track_ocr_call(self, tool_result, request_context):
            nonlocal ocr_called
            ocr_called = True
            call_order.append('ocr')
            return original_ocr_on_file_read(self, tool_result, request_context)

        def track_discord_call(self, tool_result, request_context):
            nonlocal discord_called
            discord_called = True
            call_order.append('discord')
            return original_discord_on_file_read(self, tool_result, request_context)

        with patch.object(ImageOCRExtension, 'on_file_read', track_ocr_call):
            with patch.object(DiscordFileExtension, 'on_file_read', track_discord_call):
                sample_request_context_with_image['file_refs'][0]['storage_path'] = temp_image_file

                with patch('app.dependencies.get_current_request', return_value=sample_request_context_with_image):
                    with patch('app.tools.strands_tools_wrapped.strands_file_read', mock_strands_file_read_image):
                        file_read_wrapped(temp_image_file)

        # Both should be called
        assert ocr_called
        assert discord_called

        # OCR should be called before Discord
        assert call_order == ['ocr', 'discord']


# Error Handling and Isolation Tests
class TestErrorHandlingAndIsolation:
    """Tests for error handling and extension isolation."""

    def test_one_extension_failure_doesnt_break_others(self):
        """Test that if one extension fails, others still execute."""

        class FailingExtension:
            def on_file_read(self, tool_result, request_context):
                raise RuntimeError("Extension crashed!")

            def on_file_write(self, tool_result, request_context):
                raise RuntimeError("Extension crashed!")

        class SuccessExtension:
            def __init__(self):
                self.called = False

            def on_file_read(self, tool_result, request_context):
                self.called = True
                return tool_result

            def on_file_write(self, tool_result, request_context):
                self.called = True

        success_ext = SuccessExtension()
        orchestrator = ExtensionOrchestrator([
            FailingExtension(),
            success_ext
        ])

        tool_result = {
            'status': 'success',
            'content': [{'type': 'text', 'text': 'test'}]
        }
        context = {}

        # Should not raise exception
        orchestrator.handle_file_read(tool_result, context)
        orchestrator.handle_file_write(tool_result, context)

        # Success extension should still execute
        assert success_ext.called

    def test_ocr_extension_failure_doesnt_break_file_write(
        self,
        full_orchestrator,
        mock_strands_file_write,
        temp_text_file
    ):
        """Test OCR failure doesn't prevent Discord artifact registration."""
        # Make OCR fail
        with patch.object(ImageOCRExtension, 'on_file_read', side_effect=RuntimeError("OCR failed")):
            context = {
                'user_id': 'user123',
                'channel_id': 'channel456',
                'file_refs': []
            }

            with patch('app.dependencies.get_current_request', return_value=context):
                with patch('app.tools.strands_tools_wrapped.strands_file_write', mock_strands_file_write):
                    # Should still succeed
                    result = file_write_wrapped(temp_text_file, 'content')

            # Discord extension should still register artifact
            assert 'artifacts_created' in context

    def test_error_result_propagates_through_chain(
        self,
        full_orchestrator
    ):
        """Test error ToolResult propagates through extension chain."""
        error_result: ToolResult = {
            'status': 'error',
            'toolUseId': 'test-error',
            'content': [
                {'type': 'text', 'text': 'Error: File not found'}
            ]
        }

        context = {'file_refs': []}

        result = full_orchestrator.handle_file_read(error_result, context)

        # Error status should be preserved
        assert result['status'] == 'error'
        assert 'File not found' in result['content'][0]['text']


# Multiple File Operations Tests
class TestMultipleFileOperations:
    """Tests for handling multiple file operations."""

    def test_multiple_file_reads(
        self,
        full_orchestrator,
        mock_strands_file_read_text,
        temp_text_file
    ):
        """Test multiple file reads in sequence."""
        set_orchestrator(full_orchestrator)

        context = {'user_id': 'user123', 'file_refs': []}

        with patch('app.dependencies.get_current_request', return_value=context):
            with patch('app.tools.strands_tools_wrapped.strands_file_read', mock_strands_file_read_text):
                result1 = file_read_wrapped(temp_text_file)
                result2 = file_read_wrapped(temp_text_file)
                result3 = file_read_wrapped(temp_text_file)

        # All should succeed
        assert 'Hello World' in result1
        assert 'Hello World' in result2
        assert 'Hello World' in result3

    def test_multiple_file_writes(
        self,
        full_orchestrator,
        mock_strands_file_write,
        temp_text_file
    ):
        """Test multiple file writes register multiple artifacts."""
        set_orchestrator(full_orchestrator)

        context = {
            'user_id': 'user123',
            'channel_id': 'channel456',
            'file_refs': []
        }

        # Patch os.path.exists to return True for test paths
        with patch('os.path.exists', return_value=True):
            with patch('os.path.getsize', return_value=100):
                with patch('app.dependencies.get_current_request', return_value=context):
                    with patch('app.tools.strands_tools_wrapped.strands_file_write', mock_strands_file_write):
                        file_write_wrapped('/tmp/file1.txt', 'content1')
                        file_write_wrapped('/tmp/file2.txt', 'content2')
                        file_write_wrapped('/tmp/file3.txt', 'content3')

        # Should register 3 artifacts
        assert 'artifacts_created' in context
        assert len(context['artifacts_created']) == 3

        # Each artifact should be unique
        paths = [a['storage_path'] for a in context['artifacts_created']]
        assert '/tmp/file1.txt' in paths
        assert '/tmp/file2.txt' in paths
        assert '/tmp/file3.txt' in paths


# Real-World Scenario Tests
class TestRealWorldScenarios:
    """Tests simulating real-world usage scenarios."""

    def test_user_uploads_image_and_asks_about_it(
        self,
        full_orchestrator,
        mock_strands_file_read_image,
        temp_image_file
    ):
        """Test scenario: User uploads image, bot reads it, OCR extracts text."""
        set_orchestrator(full_orchestrator)

        # Simulate Discord bot storing uploaded image
        context = {
            'user_id': 'user123',
            'channel_id': 'channel456',
            'message_id': 'message789',
            'file_refs': [
                {
                    'file_id': 'img001',
                    'filename': 'screenshot.png',
                    'storage_path': temp_image_file,
                    'extracted_content': 'User: Please sign in\nPassword: ******'
                }
            ]
        }

        with patch('app.dependencies.get_current_request', return_value=context):
            with patch('app.tools.strands_tools_wrapped.strands_file_read', mock_strands_file_read_image):
                result = file_read_wrapped(temp_image_file)

        # Should include OCR text
        assert 'OCR Extracted Text' in result
        assert 'Please sign in' in result

    def test_bot_creates_script_for_user(
        self,
        full_orchestrator,
        mock_strands_file_write
    ):
        """Test scenario: Bot creates Python script, uploads to Discord."""
        set_orchestrator(full_orchestrator)

        script_path = '/tmp/discord-bot-artifacts/hello.py'
        script_content = 'print("Hello World")'

        context = {
            'user_id': 'user123',
            'channel_id': 'channel456',
            'message_id': 'message789',
            'file_refs': []
        }

        # Patch os.path.exists to return True for test path
        with patch('os.path.exists', return_value=True):
            with patch('os.path.getsize', return_value=len(script_content)):
                with patch('app.dependencies.get_current_request', return_value=context):
                    with patch('app.tools.strands_tools_wrapped.strands_file_write', mock_strands_file_write):
                        result = file_write_wrapped(script_path, script_content)

        # Should succeed
        assert 'File written' in result

        # Should register artifact
        assert 'artifacts_created' in context
        artifact = context['artifacts_created'][0]
        assert artifact['storage_path'] == script_path
        assert artifact['discord_context']['user_id'] == 'user123'

    def test_mixed_operations_image_read_and_file_write(
        self,
        full_orchestrator,
        mock_strands_file_read_image,
        mock_strands_file_write,
        temp_image_file
    ):
        """Test scenario: Read image, process, create output file."""
        set_orchestrator(full_orchestrator)

        context = {
            'user_id': 'user123',
            'channel_id': 'channel456',
            'file_refs': [
                {
                    'file_id': 'img001',
                    'filename': 'input.png',
                    'storage_path': temp_image_file,
                    'extracted_content': 'Data: 42, 73, 91'
                }
            ]
        }

        with patch('app.dependencies.get_current_request', return_value=context):
            # Read image
            with patch('app.tools.strands_tools_wrapped.strands_file_read', mock_strands_file_read_image):
                read_result = file_read_wrapped(temp_image_file)

            # Create output file
            with patch('os.path.exists', return_value=True):
                with patch('os.path.getsize', return_value=100):
                    with patch('app.tools.strands_tools_wrapped.strands_file_write', mock_strands_file_write):
                        write_result = file_write_wrapped('/tmp/output.txt', 'Processed data')

        # Read should include OCR
        assert 'OCR Extracted Text' in read_result
        assert 'Data: 42, 73, 91' in read_result

        # Write should register artifact
        assert 'artifacts_created' in context
        assert context['artifacts_created'][0]['storage_path'] == '/tmp/output.txt'


# Performance and Cleanup Tests
class TestPerformanceAndCleanup:
    """Tests for performance and resource cleanup."""

    def test_no_memory_leaks_from_repeated_operations(
        self,
        full_orchestrator,
        mock_strands_file_read_text,
        temp_text_file
    ):
        """Test repeated operations don't leak memory."""
        set_orchestrator(full_orchestrator)

        context = {'user_id': 'user123', 'file_refs': []}

        with patch('app.dependencies.get_current_request', return_value=context):
            with patch('app.tools.strands_tools_wrapped.strands_file_read', mock_strands_file_read_text):
                # Perform many reads
                for _ in range(100):
                    file_read_wrapped(temp_text_file)

        # Should complete without issues
        # (Memory leaks would cause test to hang or crash)

    def test_large_artifact_list_handling(
        self,
        full_orchestrator,
        mock_strands_file_write
    ):
        """Test handling many artifacts in single request."""
        set_orchestrator(full_orchestrator)

        context = {
            'user_id': 'user123',
            'channel_id': 'channel456',
            'file_refs': []
        }

        # Patch os.path.exists to return True for test paths
        with patch('os.path.exists', return_value=True):
            with patch('os.path.getsize', return_value=100):
                with patch('app.dependencies.get_current_request', return_value=context):
                    with patch('app.tools.strands_tools_wrapped.strands_file_write', mock_strands_file_write):
                        # Create many artifacts
                        for i in range(50):
                            file_write_wrapped(f'/tmp/file{i}.txt', f'content{i}')

        # Should register all artifacts
        assert len(context['artifacts_created']) == 50

        # Each should be unique
        artifact_ids = [a['artifact_id'] for a in context['artifacts_created']]
        assert len(set(artifact_ids)) == 50  # All unique IDs
