"""
Discord-specific file handling extension.

Implements IFileExtension without modifying Strands tools.
Handles Discord artifact registration and metadata enrichment.
"""
import sys
sys.path.insert(0, '/shared')

from app.extensions.interface import IFileExtension
from strands.types.tools import ToolResult
from typing import Dict
import os
import uuid
import logging_client

logger = logging_client.setup_logger('discord-extension')


class DiscordFileExtension(IFileExtension):
    """
    Discord platform extension for file operations.

    Responsibilities:
    - Register artifacts for Discord upload (file_write)
    - Add Discord metadata to file operations
    - Log Discord-specific file operations for audit trail

    Follows Open/Closed Principle:
    - Extends Strands file tools without modifying them
    - Can be removed from orchestrator to disable Discord integration
    """

    def on_file_read(
        self,
        tool_result: ToolResult,
        request_context: Dict
    ) -> ToolResult:
        """
        Enrich file_read results with Discord context.

        Adds audit logging for Discord file access.
        Can optionally add Discord metadata to tool_result.

        Args:
            tool_result: Result from Strands file_read
            request_context: Context with Discord info (user_id, channel_id, etc.)

        Returns:
            Enriched tool_result (currently just logs and returns original)
        """
        user_id = request_context.get('user_id', 'unknown')
        channel_id = request_context.get('channel_id', 'unknown')
        status = tool_result.get('status', 'unknown')

        # Log for audit trail
        logger.info(
            f"📖 Discord file_read | "
            f"User: {user_id} | "
            f"Channel: {channel_id} | "
            f"Status: {status}"
        )

        # Optional: Add Discord metadata to result
        # tool_result['discord_context'] = {
        #     'user_id': user_id,
        #     'channel_id': channel_id,
        #     'message_id': request_context.get('message_id'),
        # }

        return tool_result

    def on_file_write(
        self,
        tool_result: ToolResult,
        request_context: Dict
    ) -> None:
        """
        Register file_write artifacts for Discord upload.

        Extracts file info from Strands file_write result and registers
        in request_context['artifacts_created'] for Discord bot to collect.

        Args:
            tool_result: Result from Strands file_write
                        Expected format: {'status': 'success', 'content': [...]}
            request_context: Context dict (modified in-place)
        """
        if tool_result.get('status') != 'success':
            logger.warning(f"❌ file_write failed, skipping artifact registration")
            return

        # Extract file information from tool_result
        file_path = self._extract_file_path(tool_result)
        filename = self._extract_filename(tool_result)

        if not file_path:
            logger.error("❌ Could not extract file path from tool_result")
            logger.debug(f"tool_result content: {tool_result.get('content', [])}")
            return

        if not filename:
            # Fallback: Extract filename from path
            filename = os.path.basename(file_path)

        # Validate file exists
        if not os.path.exists(file_path):
            logger.error(f"❌ File does not exist at path: {file_path}")
            return

        # Get file size
        file_size = os.path.getsize(file_path)

        # Generate artifact metadata for Discord upload
        artifact_metadata = {
            'artifact_id': str(uuid.uuid4()),
            'filename': filename,
            'storage_path': file_path,
            'size': str(file_size),
            'type': 'file',  # Could be enriched with MIME type detection
            'status': 'created',
            'discord_context': {
                'user_id': request_context.get('user_id'),
                'channel_id': request_context.get('channel_id'),
                'message_id': request_context.get('message_id'),
            }
        }

        # Register artifact in request context
        if 'artifacts_created' not in request_context:
            request_context['artifacts_created'] = []
        request_context['artifacts_created'].append(artifact_metadata)

        logger.info(
            f"📦 Discord artifact registered | "
            f"File: {filename} ({file_size} bytes) | "
            f"User: {request_context.get('user_id', 'unknown')}"
        )

    def _extract_file_path(self, tool_result: ToolResult) -> str | None:
        """
        Extract file path from Strands file_write tool_result.

        Strands file_write returns file path in the content blocks.
        We need to parse the content to find the path.

        Args:
            tool_result: ToolResult from Strands file_write

        Returns:
            File path string or None if not found
        """
        content = tool_result.get('content', [])

        for block in content:
            # Check if block contains text with file path
            if isinstance(block, dict) and 'text' in block:
                text = block['text']

                # Look for common path patterns in text
                # Example: "Successfully wrote to /tmp/discord-bot-artifacts/file.py"
                # We need to extract the path

                # Try to find absolute path (starts with /)
                if '/' in text:
                    # Split by whitespace and find tokens that look like paths
                    tokens = text.split()
                    for token in tokens:
                        if token.startswith('/') and os.path.exists(token):
                            return token

            # Check if block has a 'path' key directly
            if isinstance(block, dict) and 'path' in block:
                return block['path']

        logger.debug(f"Could not extract file path from content: {content}")
        return None

    def _extract_filename(self, tool_result: ToolResult) -> str | None:
        """
        Extract filename from Strands file_write tool_result.

        Args:
            tool_result: ToolResult from Strands file_write

        Returns:
            Filename string or None if not found
        """
        content = tool_result.get('content', [])

        for block in content:
            # Check if block has a 'filename' key directly
            if isinstance(block, dict) and 'filename' in block:
                return block['filename']

        # If no explicit filename found, will fallback to basename(path) in on_file_write
        return None
