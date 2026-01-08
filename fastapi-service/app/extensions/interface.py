"""
IFileExtension interface for platform-specific file handling extensions.

Implements Dependency Inversion Principle:
- High-level orchestrator depends on this interface
- Low-level platform extensions (Discord, Slack, etc.) implement this interface
"""
from typing import Protocol, Dict
from strands.types.tools import ToolResult


class IFileExtension(Protocol):
    """
    Interface for platform-specific file handling extensions.

    Extensions can enhance file_read and file_write operations
    with platform-specific logic like:
    - Registering artifacts for upload
    - Adding platform metadata
    - Logging file operations
    - Transforming results

    Follows Open/Closed Principle:
    - Strands tools are closed for modification
    - Extensions are open for adding new behavior
    """

    def on_file_read(
        self,
        tool_result: ToolResult,
        request_context: Dict
    ) -> ToolResult:
        """
        Post-process file_read results.

        Called after Strands file_read completes. Extensions can:
        - Add platform-specific metadata (user_id, channel_id, etc.)
        - Log file access for audit trails
        - Transform result format for platform
        - Enhance content (e.g., run OCR on images)

        Args:
            tool_result: Result from Strands file_read tool
                        Format: {'status': 'success'|'error', 'content': [...], 'toolUseId': str}
            request_context: Request context dict containing:
                            - user_id: Platform user ID
                            - channel_id: Platform channel/thread ID
                            - message_id: Platform message ID
                            - file_refs: List of uploaded file references

        Returns:
            Enhanced ToolResult (can be modified or original)

        Note: Extensions should not raise exceptions - handle errors gracefully
              and log them. Other extensions should continue processing.
        """
        ...

    def on_file_write(
        self,
        tool_result: ToolResult,
        request_context: Dict
    ) -> None:
        """
        Post-process file_write results.

        Called after Strands file_write completes. Extensions can:
        - Register artifact for platform upload (Discord, Slack, etc.)
        - Trigger platform notification
        - Update platform storage
        - Log file creation for audit trails

        Args:
            tool_result: Result from Strands file_write tool
                        Format: {'status': 'success'|'error', 'content': [...], 'toolUseId': str}
                        Content typically includes file path and metadata
            request_context: Request context dict (see on_file_read for details)

        Returns:
            None (modifications should be made to request_context in-place)

        Note: Extensions should not raise exceptions - handle errors gracefully
              and log them. Other extensions should continue processing.
        """
        ...
