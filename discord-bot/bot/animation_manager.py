"""Animation management for status messages."""
import asyncio
import discord
import logging_client

logger = logging_client.setup_logger('discord-bot')


class AnimationManager:
    """Manages status message animations with cycling dots."""

    def __init__(self, rate_limiter=None):
        """
        Initialize animation manager.

        Args:
            rate_limiter: Optional GlobalRateLimiter instance for coordinated rate limiting
        """
        self.tasks = {}  # channel_id -> asyncio.Task
        self.rate_limiter = rate_limiter

    def is_status_message(self, content: str) -> bool:
        """
        Detect if content is a status message.

        Status messages follow pattern: *<text>...*\n\n
        Examples:
            - "*Thinking...*\n\n"
            - "*Processing files...*\n\n"
            - "*Retrying with non-streaming mode...*\n\n"

        Args:
            content: Message content to check

        Returns:
            True if content matches status message pattern
        """
        return content.startswith('*') and content.endswith('*\n\n') and '...' in content

    async def start_animation(self, channel_id: int, message: discord.Message, base_text: str):
        """
        Start animation for a status message.

        Automatically cancels any existing animation for this channel first.

        Args:
            channel_id: Discord channel ID
            message: Discord message to animate
            base_text: Base text to animate (e.g., "Thinking", "Processing files")
        """
        # Cancel existing animation first (safe even if none exists)
        await self.cancel(channel_id)

        # Start new animation task
        task = asyncio.create_task(self._animate(channel_id, message, base_text))
        self.tasks[channel_id] = task
        logger.debug(f"▶️  Started animation for channel {channel_id}: {base_text}")

    async def cancel(self, channel_id: int):
        """
        Cancel animation for a channel.

        Safe to call even if no animation exists.

        Args:
            channel_id: Discord channel ID
        """
        # Use pop() for atomic operation (prevents race condition with finally block)
        task = self.tasks.pop(channel_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.debug(f"⏹️  Cancelled animation for channel {channel_id}")

    async def cancel_if_status_message(self, channel_id: int, content: str, message: discord.Message = None):
        """
        Cancel animation if content is a status message, optionally restart with new status.

        This prevents race conditions when status messages update
        (e.g., "Thinking..." → "Retrying with non-streaming mode...")

        Args:
            channel_id: Discord channel ID
            content: Message content to check
            message: Discord message object (optional, for animation restart)
        """
        if self.is_status_message(content):
            await self.cancel(channel_id)
            logger.debug(f"🔄 Cancelled animation for status update: {content[:50]}")

            # Restart animation with new status text if message provided
            if message:
                base_text = content.strip('*\n. ')
                await self.start_animation(channel_id, message, base_text)
                logger.debug(f"▶️  Restarted animation: {base_text}")

    async def _animate(self, channel_id: int, message: discord.Message, base_text: str):
        """
        Internal animation loop with cycling dots.

        Animation pattern:
            *base_text.*
            *base_text..*
            *base_text...*
            (cycles forever until cancelled)

        Args:
            channel_id: Discord channel ID (for cleanup tracking)
            message: Discord message to edit
            base_text: Base text to animate
        """
        dot_counts = [1, 2, 3]
        dot_idx = 0

        try:
            while True:
                dots = '.' * dot_counts[dot_idx % 3]
                content = f"*{base_text}{dots}*"

                try:
                    # Acquire rate limit token before edit (if rate limiter available)
                    if self.rate_limiter:
                        await self.rate_limiter.acquire()
                    await message.edit(content=content)
                except discord.errors.NotFound:
                    # Message was deleted
                    logger.debug(f"Animation message deleted for channel {channel_id}")
                    break
                except discord.errors.HTTPException as e:
                    # Check for archived thread (error code 50083)
                    if e.code == 50083:
                        logger.debug(f"Thread archived for channel {channel_id}, stopping animation")
                        break
                    # Other HTTP errors - log and continue
                    logger.warning(f"Failed to update animation for channel {channel_id}: {e}")

                dot_idx += 1
                await asyncio.sleep(1.5)  # Increased from 1.1s to reduce rate limit pressure
        except asyncio.CancelledError:
            # Animation cancelled - normal flow when content arrives
            logger.debug(f"Animation cancelled for channel {channel_id}")
            raise
        finally:
            # Clean up task tracking (use pop for safety - cancel() may have already removed it)
            self.tasks.pop(channel_id, None)
