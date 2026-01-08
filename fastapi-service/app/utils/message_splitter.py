"""Utility for splitting long messages for Discord."""
from typing import List
from app.config import settings


def split_message(
    content: str,
    max_length: int = settings.DISCORD_MESSAGE_MAX_LENGTH
) -> List[str]:
    """
    Split long message into chunks, preserving formatting.
    Splits by lines to maintain newlines, code blocks, lists, and paragraphs.

    Args:
        content: The message content to split
        max_length: Maximum length per chunk (default: 2000 for Discord)

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
