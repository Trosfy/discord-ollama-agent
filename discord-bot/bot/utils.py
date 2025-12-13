"""Utility functions for Discord bot."""
from typing import List
import discord
import base64


def split_message(content: str, max_length: int = 2000) -> List[str]:
    """
    Split long message into chunks for Discord, preserving formatting.
    Splits by lines to maintain newlines, code blocks, lists, and paragraphs.
    Matches FastAPI's message splitting logic.

    Args:
        content: Message content to split
        max_length: Maximum length per chunk (Discord limit: 2000)

    Returns:
        List of message chunks
    """
    if len(content) <= max_length:
        return [content]

    # Split by lines first (preserves formatting)
    lines = content.split('\n')

    chunks = []
    current_chunk = []
    current_length = 0

    for line in lines:
        line_length = len(line) + 1  # +1 for newline

        # Handle single line that's too long (rare edge case)
        if line_length > max_length:
            # Save current chunk if exists
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_length = 0

            # Split long line by words as fallback
            chunks.extend(_split_long_line(line, max_length))
            continue

        # Check if adding this line exceeds limit
        if current_length + line_length > max_length:
            # Save current chunk
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
            # Start new chunk with current line
            current_chunk = [line]
            current_length = line_length
        else:
            # Add line to current chunk
            current_chunk.append(line)
            current_length += line_length

    # Add final chunk
    if current_chunk:
        chunks.append('\n'.join(current_chunk))

    return chunks


def _split_long_line(line: str, max_length: int) -> List[str]:
    """
    Fallback for splitting a single line that's too long.
    Uses word-based splitting since there's no formatting to preserve.

    Args:
        line: The line to split
        max_length: Maximum length per chunk

    Returns:
        List of line chunks
    """
    words = line.split()
    chunks = []
    current = ""

    for word in words:
        if len(current) + len(word) + 1 <= max_length:
            current += word + " "
        else:
            if current:
                chunks.append(current.strip())
            current = word + " "

    if current:
        chunks.append(current.strip())

    return chunks if chunks else [line[:max_length]]  # Fallback for single long word


def validate_attachment(attachment: discord.Attachment) -> bool:
    """
    Validate file attachment size and type using config settings.

    Args:
        attachment: Discord attachment object

    Returns:
        bool: True if valid, False otherwise
    """
    from bot.config import settings

    # Check file size (convert MB to bytes)
    max_size = settings.MAX_FILE_SIZE_MB * 1_000_000
    if attachment.size > max_size:
        return False

    # Check content type
    if attachment.content_type and attachment.content_type in settings.ALLOWED_FILE_TYPES:
        return True

    # Fallback: check file extension if content_type not set
    filename_lower = attachment.filename.lower()
    return any(filename_lower.endswith(ext) for ext in settings.ALLOWED_FILE_EXTENSIONS)


def encode_file_base64(file_data: bytes) -> str:
    """
    Encode file data as base64 string for transmission.

    Args:
        file_data: Binary file data

    Returns:
        str: Base64-encoded string
    """
    return base64.b64encode(file_data).decode('utf-8')
