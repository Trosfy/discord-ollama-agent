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
