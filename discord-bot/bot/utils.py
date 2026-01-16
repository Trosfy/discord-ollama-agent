"""Utility functions for Discord bot."""
from typing import List, Tuple, Optional
import discord
import base64
import sys
sys.path.insert(0, '/shared')
import jwt
from datetime import datetime, timezone, timedelta
import logging_client

logger = logging_client.setup_logger('discord-bot-admin')


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


def track_code_block_state(content: str) -> Tuple[bool, Optional[str]]:
    """
    Determine if content ends inside an unclosed code block.

    Tracks ``` markers to determine if we're currently inside a code block.
    Handles code blocks with and without language specifiers.

    Args:
        content: The content to analyze

    Returns:
        Tuple of (is_in_code_block, language)
        - is_in_code_block: True if content ends inside an unclosed code block
        - language: The code block language (e.g., 'python', '') or None if not in block
    """
    import re

    # Find all code block markers (``` optionally followed by language)
    # This pattern matches ``` at the start of a line or after whitespace
    pattern = re.compile(r'```(\w*)')
    matches = list(pattern.finditer(content))

    # Track open/close state
    is_open = False
    language = None

    for match in matches:
        if is_open:
            # This closes the block (``` closes any open block)
            is_open = False
            language = None
        else:
            # This opens a block
            is_open = True
            language = match.group(1) or ''  # Empty string for plain ```

    return (is_open, language)


def find_stream_split_point(
    content: str,
    threshold: int = 1800,
    min_remaining: int = 100
) -> Tuple[int, Optional[str], Optional[str]]:
    """
    Find optimal point to split streaming content for Discord messages.

    Priorities for split points:
    1. Paragraph boundary (double newline)
    2. Line boundary (single newline)
    3. Sentence boundary (. followed by space)
    4. Word boundary (space)
    5. Hard split at threshold (fallback)

    Handles code blocks by adding close/open markers to maintain valid markdown.

    Args:
        content: Content to find split point in
        threshold: Target character count for split (default 1800)
        min_remaining: Minimum content that must remain after split (default 100)

    Returns:
        Tuple of (split_index, suffix_for_current, prefix_for_next)
        - split_index: Where to split (0 if no valid split possible)
        - suffix: String to append to current message (e.g., "\\n```" to close code block)
        - prefix: String to prepend to next message (e.g., "```python\\n" to reopen)
    """
    if len(content) < threshold + min_remaining:
        return (0, None, None)  # Not enough content to warrant a split

    # Search window: from threshold-200 to threshold
    # This gives us room to find natural break points
    search_start = max(0, threshold - 200)
    search_end = threshold
    search_region = content[search_start:search_end]

    split_at = None

    # Priority 1: Paragraph boundary (double newline)
    para_idx = search_region.rfind('\n\n')
    if para_idx != -1:
        split_at = search_start + para_idx + 2  # After the double newline
    else:
        # Priority 2: Line boundary (single newline)
        line_idx = search_region.rfind('\n')
        if line_idx != -1:
            split_at = search_start + line_idx + 1  # After the newline
        else:
            # Priority 3: Sentence boundary (period followed by space)
            sentence_idx = search_region.rfind('. ')
            if sentence_idx != -1:
                split_at = search_start + sentence_idx + 2  # After the ". "
            else:
                # Priority 4: Word boundary (space)
                space_idx = search_region.rfind(' ')
                if space_idx != -1:
                    split_at = search_start + space_idx + 1  # After the space
                else:
                    # Priority 5: Hard split at threshold
                    split_at = threshold

    # Check code block state at the split point
    is_in_block, language = track_code_block_state(content[:split_at])

    suffix = None
    prefix = None

    if is_in_block:
        # Need to close the code block in current message and reopen in next
        suffix = '\n```'
        prefix = f'```{language}\n' if language else '```\n'

    return (split_at, suffix, prefix)


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


def has_admin_role(interaction: discord.Interaction) -> Tuple[bool, Optional[str]]:
    """
    Check if user has any of the whitelisted admin roles.

    Args:
        interaction: Discord interaction

    Returns:
        Tuple of (has_role, matched_role_id)
        - (True, role_id) if user has admin role
        - (False, None) if user does not have admin role
    """
    from bot.config import settings

    # Parse admin role IDs from config
    admin_role_ids_str = settings.ADMIN_ROLE_IDS
    if not admin_role_ids_str:
        logger.warning("ADMIN_ROLE_IDS not configured - no users can use admin commands")
        return (False, None)

    # Split comma-separated role IDs
    admin_role_ids = [role_id.strip() for role_id in admin_role_ids_str.split(',') if role_id.strip()]

    if not admin_role_ids:
        logger.warning("ADMIN_ROLE_IDS is empty - no users can use admin commands")
        return (False, None)

    # Get user's roles
    if not isinstance(interaction.user, discord.Member):
        logger.debug("User is not a guild member - cannot check roles")
        return (False, None)

    user_role_ids = [str(role.id) for role in interaction.user.roles]

    # Check if user has any admin role
    for role_id in admin_role_ids:
        if role_id in user_role_ids:
            logger.info(f"User {interaction.user.id} has admin role {role_id}")
            return (True, role_id)

    logger.debug(f"User {interaction.user.id} does not have any admin roles")
    return (False, None)


def generate_admin_token(user_id: str, role_id: str) -> str:
    """
    Generate a short-lived JWT token for admin API authentication.

    This token is signed by the bot and can be verified by admin-service
    to prove the user has an admin role in Discord.

    Args:
        user_id: Discord user ID
        role_id: Matched admin role ID

    Returns:
        str: JWT token string

    Raises:
        ValueError: If BOT_SECRET is not configured
    """
    from bot.config import settings

    if not settings.BOT_SECRET:
        logger.error("BOT_SECRET not configured - cannot generate admin tokens")
        raise ValueError("Bot secret not configured")

    # Create JWT payload
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "role_id": role_id,
        "iat": int(now.timestamp()),  # Issued at
        "exp": int((now + timedelta(minutes=5)).timestamp()),  # Expires in 5 minutes
        "nonce": f"{user_id}_{int(now.timestamp())}"  # Prevent token reuse
    }

    # Sign token with bot secret
    token = jwt.encode(payload, settings.BOT_SECRET, algorithm="HS256")

    logger.debug(f"Generated admin token for user {user_id} (expires in 5 minutes)")

    return token
