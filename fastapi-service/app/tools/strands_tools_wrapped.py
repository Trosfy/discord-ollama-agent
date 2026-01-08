"""
Wrapped Strands file tools with extension support.

These wrappers call Strands file_read and file_write tools,
then run results through ExtensionOrchestrator for platform-specific enhancements.
"""
import sys
sys.path.insert(0, '/shared')

from strands import tool
from strands.types.tools import ToolUse, ToolResult
from typing import Dict
import uuid
import logging_client

logger = logging_client.setup_logger('strands-tools-wrapped')

# Import Strands file tool handlers
from strands_tools.file_read import file_read as strands_file_read
from strands_tools.file_write import file_write as strands_file_write


# Global reference to orchestrator (set by StrandsLLM)
_orchestrator = None


def set_orchestrator(orchestrator):
    """Set global orchestrator reference."""
    global _orchestrator
    _orchestrator = orchestrator


@tool(
    name="file_read",
    description="""Read file contents with support for PDFs, documents, code files, and images.

Modes:
- view: Full file display (default)
- preview: First 50 lines
- stats: File metadata

Supports:
- PDFs: Text extraction
- Images: OCR text extraction (for uploaded images)
- Code files: Syntax-aware reading
- Documents: Text extraction

Example: file_read('/path/to/document.pdf')
"""
)
def file_read_wrapped(path: str, mode: str = "view", **kwargs) -> str:
    """
    Read file using Strands file_read.

    IMPORTANT: This tool is for reading OTHER files (not user-uploaded files).
    - User-uploaded files: Use list_attachments (content pre-extracted in preprocessing)
    - Other files (system, generated): Use file_read_wrapped

    Workflow:
    1. Call Strands file_read (handles PDF, code files, text, etc.)
    2. Return content

    Args:
        path: File path to read
        mode: Read mode (view, preview, stats)
        **kwargs: Additional parameters

    Returns:
        File content as string
    """
    logger.debug(f"file_read_wrapped called: path={path}, mode={mode}")

    # Get request context
    from app.dependencies import get_current_request
    request_context = get_current_request()

    # Create ToolUse for Strands
    tool_use: ToolUse = {
        'name': 'file_read',
        'toolUseId': str(uuid.uuid4()),
        'input': {'path': path, 'mode': mode, **kwargs}
    }

    # Call Strands file_read
    tool_result: ToolResult = strands_file_read(tool_use)

    # NOTE: ExtensionOrchestrator is for POST-PROCESSING only (file_write artifact registration)
    # File reading does NOT go through extensions - that's for preprocessing via FileExtractionRouter

    # Extract text from ToolResult
    if tool_result.get('status') == 'error':
        error_text = ''
        for block in tool_result.get('content', []):
            if 'text' in block:
                error_text += block['text']
        return f"Error reading file: {error_text}"

    # Concatenate all text blocks
    content_parts = []
    for block in tool_result.get('content', []):
        if 'text' in block:
            content_parts.append(block['text'])

    return '\n'.join(content_parts)


@tool(
    name="file_write",
    description="""Create a file for the user.

WHEN TO USE:
- User says: "create a file", "generate a script", "save to file"
- User wants downloadable content: code, configs, data files

IMPORTANT: File will be automatically uploaded to Discord.

Returns success/error message.
"""
)
def file_write_wrapped(path: str, content: str) -> str:
    """
    Write file using Strands file_write + extensions.

    Workflow:
    1. Call Strands file_write (writes to filesystem)
    2. Run result through DiscordFileExtension (registers artifact for upload)
    3. Return result

    Args:
        path: File path to write
        content: File content

    Returns:
        Success/error message as string
    """
    logger.debug(f"file_write_wrapped called: path={path}, content_length={len(content)}")

    # Get request context
    from app.dependencies import get_current_request
    request_context = get_current_request()

    # Create ToolUse for Strands
    tool_use: ToolUse = {
        'name': 'file_write',
        'toolUseId': str(uuid.uuid4()),
        'input': {'path': path, 'content': content}
    }

    # Call Strands file_write
    tool_result: ToolResult = strands_file_write(tool_use)

    # Run through extensions if orchestrator available
    if _orchestrator:
        try:
            _orchestrator.handle_file_write(tool_result, request_context)
        except Exception as e:
            logger.error(f"Extension error: {e}", exc_info=True)

    # Extract text from ToolResult
    if tool_result.get('status') == 'error':
        error_text = ''
        for block in tool_result.get('content', []):
            if 'text' in block:
                error_text += block['text']
        return f"Error writing file: {error_text}"

    # Concatenate all text blocks
    content_parts = []
    for block in tool_result.get('content', []):
        if 'text' in block:
            content_parts.append(block['text'])

    return '\n'.join(content_parts) or "File written successfully"
