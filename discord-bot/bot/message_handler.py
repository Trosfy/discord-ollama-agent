"""Message handling for Discord bot."""
import sys
sys.path.insert(0, '/shared')

import base64
import discord
import io
import asyncio
import re
import time
from bot.websocket_manager import WebSocketManager
from bot.utils import split_message, validate_attachment, encode_file_base64, find_stream_split_point
from bot.animation_manager import AnimationManager
import logging_client

# Initialize logger
logger = logging_client.setup_logger('discord-bot')


class GlobalRateLimiter:
    """
    Global rate limiter for Discord API edits using token bucket algorithm.

    Coordinates all edit operations across channels to prevent hitting
    Discord's global rate limit when multiple streams are active.
    """

    def __init__(self, rate: float = 2.5):
        """
        Initialize rate limiter.

        Args:
            rate: Maximum edits per second globally (default 2.5)
        """
        self.rate = rate
        self.tokens = rate  # Start with full bucket
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """
        Acquire a token before making a Discord API edit.

        Blocks if no tokens available until one is refilled.
        """
        async with self._lock:
            now = time.time()
            # Refill tokens based on elapsed time
            elapsed = now - self.last_refill
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_refill = now

            # Wait if no tokens available
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                logger.debug(f"Rate limiter: waiting {wait_time:.2f}s for token")
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


# Global rate limiter instance (shared across all streams and animations)
global_rate_limiter = GlobalRateLimiter(rate=2.5)

# Discord rate limit: increased from 1000ms to reduce concurrent edit collisions
MIN_STREAM_INTERVAL_MS = 1500

# Multi-message streaming thresholds
SPLIT_THRESHOLD = 1800           # When to trigger mid-stream split
MIN_NEW_MESSAGE_CONTENT = 100    # Minimum content for new message


class MessageHandler:
    """Handles Discord messages and responses."""

    def __init__(self, bot, ws_manager: WebSocketManager):
        self.bot = bot
        self.ws_manager = ws_manager
        self.rate_limiter = global_rate_limiter  # Shared rate limiter
        self.animation_manager = AnimationManager(rate_limiter=global_rate_limiter)  # Share rate limiter

    async def handle_user_message(self, message: discord.Message):
        """
        Handle incoming user message.

        Args:
            message: Discord message object
        """
        # Remove bot mention from message
        content = message.content
        if self.bot.user.mentioned_in(message):
            content = content.replace(f"<@{self.bot.user.id}>", "").strip()

        # Log incoming message
        logger.info(f"📨 User message from {message.author.name} (ID: {message.author.id}): {content}")

        # Determine thread (Phase 0 & 1: Fix thread_id bug + create Discord threads)
        if isinstance(message.channel, discord.Thread):
            # Already in a thread, use existing thread
            thread = message.channel
            thread_id = str(thread.id)
            logger.info(f"🧵 Using existing thread: {thread.name} (ID: {thread_id})")
        else:
            # In a channel, create a new thread from this message
            thread_name = f"💬 {content[:50]}..." if len(content) > 50 else f"💬 {content}"
            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=60  # Archive after 1 hour of inactivity
            )
            thread_id = str(thread.id)
            logger.info(f"🧵 Created new thread: {thread.name} (ID: {thread_id})")

        # Add initial processing reaction (Phase 3: Reactions)
        try:
            await message.add_reaction("⏳")
        except Exception as e:
            logger.error(f"Failed to add reaction: {e}")

        # Process file attachments (TROISE AI format)
        files = []
        if message.attachments:
            logger.info(f"Processing {len(message.attachments)} attachment(s)")

            for attachment in message.attachments:
                # Validate attachment
                if not validate_attachment(attachment):
                    logger.warning(f"Skipping invalid attachment: {attachment.filename} ({attachment.size} bytes, {attachment.content_type})")
                    await thread.send(f"Skipped `{attachment.filename}`: file too large or unsupported type")
                    continue

                # Download and encode file
                try:
                    file_data = await attachment.read()
                    file_base64 = encode_file_base64(file_data)

                    files.append({
                        'filename': attachment.filename,
                        'mimetype': attachment.content_type or 'application/octet-stream',
                        'base64_data': file_base64
                    })

                    logger.info(f"Encoded attachment: {attachment.filename} ({attachment.size} bytes)")
                except Exception as e:
                    logger.error(f"Failed to process attachment {attachment.filename}: {e}")
                    await thread.send(f"Failed to process `{attachment.filename}`: {str(e)}")

        # Send to TROISE AI (native protocol)
        data = {
            'type': 'message',
            'content': content,
            'message_id': str(message.id),
            'files': files,
            'metadata': {
                'user_id': str(message.author.id),
                'conversation_id': thread_id,  # Discord thread ID = conversation ID
                'channel_id': str(thread.id),  # Thread ID for responses
                'message_channel_id': str(message.channel.id),  # Where the message is (for reactions)
                'message_id': str(message.id),  # For reaction targeting
                'guild_id': str(message.guild.id) if message.guild else None,
            }
        }

        await self.ws_manager.send_message(data)

    async def handle_response(self, data: dict):
        """
        Handle response from TROISE AI.

        Args:
            data: Response data dictionary
        """
        response_type = data.get('type')

        # TROISE AI native message types
        if response_type == 'session_start':
            # Connection established with session
            session_id = data.get('session_id')
            logger.info(f"Session started: {session_id}")

        elif response_type == 'pong':
            # Heartbeat response - no action needed
            pass

        elif response_type == 'routing':
            # Skill/agent routing info (already routed by troise-ai)
            logger.info(f"Routed to: {data.get('skill_or_agent')} ({data.get('routing_type')})")

        elif response_type == 'queued':
            await self._handle_queued(data)

        elif response_type == 'early_status':
            # Early status indicator (triggers animation)
            await self._handle_early_status(data)

        elif response_type == 'stream':
            # TROISE AI streaming partial chunk
            await self._handle_stream(data)

        elif response_type == 'stream_end':
            # TROISE AI streaming complete
            await self._handle_stream_end(data)

        elif response_type == 'response':
            # Complete non-streaming response
            await self._handle_response_complete(data)

        elif response_type == 'file':
            # Artifact with base64_data
            await self._handle_file_artifact(data)

        elif response_type == 'file_suggestion':
            # Low-confidence artifact suggestion
            await self._handle_file_artifact(data, is_suggestion=True)

        elif response_type == 'tool_start':
            # Tool execution started
            logger.debug(f"Tool started: {data.get('tool_name')}")

        elif response_type == 'stream_fallback':
            # Fallback to non-streaming mode
            logger.info(f"Streaming fallback: {data.get('message')}")

        elif response_type == 'question':
            # Agent asking user a question - treat as normal Discord reply
            await self._handle_question(data)

        elif response_type == 'error':
            await self._handle_error(data)

        elif response_type == 'cancelled':
            logger.info(f"Request {data.get('request_id')} cancelled")

    async def _update_reaction(self, channel_id: str, message_id: str,
                               remove_emoji: str = None, add_emoji: str = None):
        """
        Update reactions on a message.

        Args:
            channel_id: Channel/thread ID where message is located
            message_id: Message ID to update reactions on
            remove_emoji: Emoji to remove (optional)
            add_emoji: Emoji to add (optional)
        """
        try:
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                logger.error(f"Channel {channel_id} not found for reaction update")
                return

            message = await channel.fetch_message(int(message_id))

            if remove_emoji:
                await message.remove_reaction(remove_emoji, self.bot.user)
            if add_emoji:
                await message.add_reaction(add_emoji)
        except discord.NotFound:
            logger.warning(f"Message {message_id} not found for reaction update")
        except discord.Forbidden:
            logger.error(f"Missing permissions to update reactions on message {message_id}")
        except Exception as e:
            logger.error(f"Failed to update reaction: {e}")

    async def _handle_queued(self, data: dict):
        """Handle queued response."""
        request_id = data['request_id']
        position = data.get('queue_position', 0)

        # Could optionally send a "queued" reaction/message
        logger.info(f"✅ Request {request_id} queued at position {position}")

    async def _handle_processing(self, data: dict):
        """Handle processing notification."""
        request_id = data['request_id']
        logger.info(f"🔄 Processing request {request_id}")

    # _handle_result() removed - now handled by unified _handle_stream_chunk()
    # Non-streaming mode now sends 'stream_chunk' with is_complete=True

    async def _handle_failed(self, data: dict):
        """Handle failed request after max retries."""
        channel_id = int(data['channel_id'])
        message_channel_id = data.get('message_channel_id', channel_id)  # Fallback for backwards compat
        message_id = data.get('message_id')
        user_id = int(data['user_id'])
        error = data['error']
        attempts = data['attempts']

        # Update reaction: ⏳ → ❌ (use message_channel_id where message actually is)
        if message_id:
            await self._update_reaction(
                str(message_channel_id),
                str(message_id),
                remove_emoji="⏳",
                add_emoji="❌"
            )

        # Get thread to reply in
        thread = self.bot.get_channel(channel_id)
        if not thread:
            return

        await thread.send(
            f"❌ <@{user_id}> Sorry, your request failed after {attempts} attempts.\n"
            f"Error: {error}\n"
            f"Please try again or contact an admin."
        )

    async def _handle_error(self, data: dict):
        """Handle error response."""
        error = data['error']
        channel_id = data.get('channel_id')
        message_channel_id = data.get('message_channel_id', channel_id)  # Fallback for backwards compat
        message_id = data.get('message_id')

        logger.error(f"❌ Error: {error}")

        # Update reaction: ⏳ → ❌ (use message_channel_id where message actually is)
        if message_channel_id and message_id:
            await self._update_reaction(
                str(message_channel_id),
                str(message_id),
                remove_emoji="⏳",
                add_emoji="❌"
            )

    async def _handle_maintenance_warning(self, data: dict):
        """Handle maintenance warning."""
        message = data['message']
        logger.warning(f"⚠️  Maintenance: {message}")

    async def _handle_summarize_response(self, data: dict):
        """Handle summarize response."""
        interaction_id = data.get('interaction_id')
        thread_id = data.get('thread_id')
        summary = data.get('summary')
        error = data.get('error')
        messages_summarized = data.get('messages_summarized', 0)

        # Get pending interaction if exists
        if hasattr(self.bot, 'pending_interactions') and interaction_id in self.bot.pending_interactions:
            interaction = self.bot.pending_interactions[interaction_id]

            try:
                if error:
                    await interaction.followup.send(
                        f"❌ Failed to generate summary: {error}",
                        ephemeral=True
                    )
                    logger.error(f"Summary failed: {error}")
                elif summary:
                    # Send confirmation to user (ephemeral)
                    await interaction.followup.send(
                        f"✅ Summarized {messages_summarized} messages. Summary posted to thread!",
                        ephemeral=True
                    )

                    # Post summary to thread (public message)
                    thread = self.bot.get_channel(int(thread_id))
                    if thread:
                        chunks = split_message(summary)

                        # Send first chunk with header
                        await thread.send(f"📝 **Thread Summary:**\n\n{chunks[0]}")

                        # Send remaining chunks if any
                        for chunk in chunks[1:]:
                            await thread.send(chunk)

                        logger.info(f"✅ Posted summary to thread {thread_id} ({messages_summarized} messages summarized)")
                    else:
                        logger.error(f"Thread {thread_id} not found for summary")
                else:
                    await interaction.followup.send(
                        "⚠️ No conversation to summarize yet!",
                        ephemeral=True
                    )

                # Clean up pending interaction
                del self.bot.pending_interactions[interaction_id]
            except Exception as e:
                logger.error(f"Failed to send summary response: {e}")
        else:
            logger.warning(f"Received summary response for unknown interaction: {interaction_id}")

    async def _handle_configure_response(self, data: dict):
        """Handle configure response."""
        interaction_id = data.get('interaction_id')
        success = data.get('success')
        message = data.get('message')
        error = data.get('error')
        setting = data.get('setting')

        # Get pending interaction if exists
        if hasattr(self.bot, 'pending_interactions') and interaction_id in self.bot.pending_interactions:
            interaction = self.bot.pending_interactions[interaction_id]

            try:
                if error:
                    await interaction.followup.send(
                        f"❌ Configuration failed: {error}",
                        ephemeral=True
                    )
                    logger.error(f"Configuration failed for setting {setting}: {error}")
                elif success and message:
                    # Send success message
                    await interaction.followup.send(
                        message,
                        ephemeral=True
                    )
                    logger.info(f"✅ Configuration updated: {setting}")
                else:
                    await interaction.followup.send(
                        "⚠️ Configuration request completed but no confirmation received",
                        ephemeral=True
                    )

                # Clean up pending interaction
                del self.bot.pending_interactions[interaction_id]
            except Exception as e:
                logger.error(f"Failed to send configure response: {e}")
        else:
            logger.warning(f"Received configure response for unknown interaction: {interaction_id}")

    def _has_meaningful_content(self, content: str) -> bool:
        """
        Check if content has meaningful characters for Discord.
        Returns True if content has alphanumeric characters.
        Returns False if only whitespace, symbols, or empty.
        """
        if not content or not content.strip():
            return False
        # Check for at least one alphanumeric character
        return bool(re.search(r'[a-zA-Z0-9]', content))

    # =========================================================================
    # TROISE AI Native Protocol Handlers
    # =========================================================================

    async def _handle_stream(self, data: dict):
        """
        Handle TROISE AI streaming partial chunk.

        Accumulates content and updates Discord message with "..." indicator.
        """
        request_id = data.get('request_id')
        channel_id = data.get('channel_id')
        content = data.get('content', '')

        if not channel_id:
            logger.warning("Stream chunk missing channel_id")
            return

        channel_id = int(channel_id)

        # Get thread
        thread = self.bot.get_channel(channel_id)
        if not thread:
            logger.error(f"Thread {channel_id} not found for streaming")
            return

        # Initialize streaming buffers
        if not hasattr(self.bot, 'streaming_buffers'):
            self.bot.streaming_buffers = {}
        if not hasattr(self.bot, 'streaming_messages'):
            self.bot.streaming_messages = {}
        if not hasattr(self.bot, 'stream_backoff'):
            self.bot.stream_backoff = {}
        if not hasattr(self.bot, 'stream_last_edit'):
            self.bot.stream_last_edit = {}

        # Use request_id as key if available, otherwise channel_id
        buffer_key = request_id or str(channel_id)

        # Get or create buffer state
        if buffer_key not in self.bot.streaming_buffers:
            self.bot.streaming_buffers[buffer_key] = {
                'content': '',
                'committed_length': 0,  # Track content already in finalized messages
                'channel_id': channel_id,
                'request_id': request_id,
            }
            # Use list to track multiple Discord messages per request
            self.bot.streaming_messages[buffer_key] = []
            logger.debug(f"Started streaming buffer for {buffer_key}")

        state = self.bot.streaming_buffers[buffer_key]
        state['content'] += content  # Accumulate tokens from TROISE AI

        # Apply rate limit backoff if needed
        backoff_delay, last_attempt = self.bot.stream_backoff.get(buffer_key, (0, 0))
        if backoff_delay > 0:
            time_since_last = time.time() - last_attempt
            if time_since_last < backoff_delay:
                wait_time = backoff_delay - time_since_last
                logger.debug(f"Backing off for {wait_time:.2f}s due to rate limits")
                await asyncio.sleep(wait_time)

        self.bot.stream_backoff[buffer_key] = (backoff_delay, time.time())

        # Check for early status message to reuse
        early_msg = None
        if hasattr(self.bot, 'early_status_messages'):
            early_msg = self.bot.early_status_messages.get(channel_id)

        try:
            # Get message list for this request
            messages = self.bot.streaming_messages.get(buffer_key, [])

            # Cancel animation when first meaningful chunk arrives
            if not messages:
                await self.animation_manager.cancel(channel_id)
                await asyncio.sleep(0.15)  # Let pending Discord edits complete

            # Calculate pending (uncommitted) content
            committed = state.get('committed_length', 0)
            pending_content = state['content'][committed:]

            # Validate content before Discord operations
            if not self._has_meaningful_content(pending_content):
                logger.debug(f"Not enough meaningful content yet: {len(pending_content)} chars")
                return

            # Check if we need to split (approaching threshold)
            if len(pending_content) >= SPLIT_THRESHOLD and messages:
                split_point, suffix, prefix = find_stream_split_point(
                    pending_content,
                    threshold=SPLIT_THRESHOLD,
                    min_remaining=MIN_NEW_MESSAGE_CONTENT
                )

                if split_point >= MIN_NEW_MESSAGE_CONTENT:
                    # Finalize current message
                    finalize_content = pending_content[:split_point]
                    if suffix:
                        finalize_content += suffix  # Close code block

                    current_msg = messages[-1]
                    await self.rate_limiter.acquire()
                    await current_msg.edit(content=finalize_content)

                    # Update committed length
                    state['committed_length'] = committed + split_point

                    # Prepare content for new message
                    new_pending = pending_content[split_point:]
                    if prefix:
                        new_pending = prefix + new_pending  # Reopen code block

                    # Create new message
                    display_new = new_pending.rstrip() + " ..."
                    new_msg = await thread.send(display_new)
                    messages.append(new_msg)
                    self.bot.streaming_messages[buffer_key] = messages
                    self.bot.stream_last_edit[buffer_key] = time.time()

                    logger.debug(f"Split streaming message for {buffer_key}, now {len(messages)} messages")

                    # Reset backoff on success
                    self.bot.stream_backoff[buffer_key] = (0, time.time())
                    return

            # Normal streaming update (content below threshold or first message)
            display_content = pending_content.rstrip() + " ..."

            if not messages:
                # First chunk with meaningful content
                if early_msg:
                    # Reuse early status message
                    discord_msg = early_msg
                    del self.bot.early_status_messages[channel_id]
                    await self.rate_limiter.acquire()
                    await discord_msg.edit(content=display_content)
                    logger.debug(f"Updated early status message for {buffer_key}")
                else:
                    # Create new message
                    discord_msg = await thread.send(display_content)
                    logger.debug(f"Created streaming message for {buffer_key}")

                messages.append(discord_msg)
                self.bot.streaming_messages[buffer_key] = messages
                self.bot.stream_last_edit[buffer_key] = time.time()
            else:
                # Subsequent chunks - throttle edits to 1 per second
                last_edit = self.bot.stream_last_edit.get(buffer_key, 0)
                elapsed_ms = (time.time() - last_edit) * 1000

                if elapsed_ms < MIN_STREAM_INTERVAL_MS:
                    # Too soon - skip this edit, content is buffered for next time
                    return

                current_msg = messages[-1]
                await self.rate_limiter.acquire()
                await current_msg.edit(content=display_content)
                self.bot.stream_last_edit[buffer_key] = time.time()

            # Reset backoff on success
            self.bot.stream_backoff[buffer_key] = (0, time.time())

        except discord.HTTPException as e:
            if e.status == 429:
                # Rate limited - apply exponential backoff
                retry_after = getattr(e, 'retry_after', None)
                if retry_after:
                    new_backoff = float(retry_after)
                else:
                    current_backoff = self.bot.stream_backoff.get(buffer_key, (0, 0))[0]
                    new_backoff = max(2.0, current_backoff * 2.0) if current_backoff > 0 else 2.0
                self.bot.stream_backoff[buffer_key] = (new_backoff, time.time())
                logger.warning(f"Rate limited, backing off to {new_backoff}s")
            elif e.code == 50006:
                logger.error(f"Empty message error: {repr(display_content[:50])}")
            else:
                logger.error(f"Discord HTTP error during streaming: {e}")
        except Exception as e:
            logger.error(f"Error handling stream for {buffer_key}: {e}")

    async def _handle_stream_end(self, data: dict):
        """
        Handle TROISE AI streaming completion.

        Finalizes message, splits if >2000 chars, cleans up buffers.
        """
        request_id = data.get('request_id')
        channel_id = data.get('channel_id')
        message_channel_id = data.get('message_channel_id', channel_id)
        message_id = data.get('message_id')

        if not channel_id:
            logger.warning("stream_end missing channel_id")
            return

        channel_id = int(channel_id)

        # Get thread
        thread = self.bot.get_channel(channel_id)
        if not thread:
            logger.error(f"Thread {channel_id} not found for stream_end")
            return

        # Find buffer by request_id or channel_id
        buffer_key = request_id or str(channel_id)

        # Check streaming buffers
        if not hasattr(self.bot, 'streaming_buffers'):
            self.bot.streaming_buffers = {}

        state = self.bot.streaming_buffers.get(buffer_key)
        if not state:
            logger.warning(f"No streaming buffer found for {buffer_key}")
            return

        full_content = state['content']
        committed = state.get('committed_length', 0)
        logger.debug(f"Stream completed for {buffer_key}: {len(full_content)} total chars, {committed} committed")

        # Cancel animation
        await self.animation_manager.cancel(channel_id)

        # Get Discord messages list
        if not hasattr(self.bot, 'streaming_messages'):
            self.bot.streaming_messages = {}

        messages = self.bot.streaming_messages.get(buffer_key, [])

        # Calculate remaining uncommitted content
        remaining_content = full_content[committed:]

        try:
            if messages:
                last_msg = messages[-1]

                if len(remaining_content) > 2000:
                    # Split remaining content
                    chunks = split_message(remaining_content)
                    await self.rate_limiter.acquire()
                    await last_msg.edit(content=chunks[0])

                    # Send remaining chunks
                    for chunk in chunks[1:]:
                        await thread.send(chunk)

                    logger.debug(f"Finalized with {len(messages)} messages + {len(chunks) - 1} overflow chunks")
                elif remaining_content:
                    # Finalize last message (remove "..." indicator)
                    await self.rate_limiter.acquire()
                    await last_msg.edit(content=remaining_content)
                    logger.debug(f"Finalized stream with {len(messages)} message(s)")
                else:
                    # No remaining content - edge case, just log
                    logger.debug(f"Stream ended with no remaining content, {len(messages)} message(s) already sent")
            elif full_content:
                # No messages exist yet (all chunks were too short) - send final content
                if len(full_content) > 2000:
                    chunks = split_message(full_content)
                    for chunk in chunks:
                        await thread.send(chunk)
                else:
                    await thread.send(full_content)

            # Remove loading reaction from original message
            if message_channel_id and message_id:
                await self._update_reaction(
                    str(message_channel_id),
                    str(message_id),
                    remove_emoji="⏳"
                )

        except discord.HTTPException as e:
            logger.error(f"Discord error finalizing stream: {e}")
        except Exception as e:
            logger.error(f"Error finalizing stream for {buffer_key}: {e}")

        # Clean up buffers
        if buffer_key in self.bot.streaming_buffers:
            del self.bot.streaming_buffers[buffer_key]
        if buffer_key in self.bot.streaming_messages:
            del self.bot.streaming_messages[buffer_key]
        if buffer_key in self.bot.stream_backoff:
            del self.bot.stream_backoff[buffer_key]
        if hasattr(self.bot, 'stream_last_edit') and buffer_key in self.bot.stream_last_edit:
            del self.bot.stream_last_edit[buffer_key]

    async def _handle_response_complete(self, data: dict):
        """
        Handle complete non-streaming response from TROISE AI.
        """
        content = data.get('content', '')
        channel_id = data.get('channel_id')
        message_channel_id = data.get('message_channel_id', channel_id)
        message_id = data.get('message_id')
        part = data.get('part')
        total_parts = data.get('total_parts')
        artifacts = data.get('artifacts', [])

        if not channel_id:
            logger.warning("Response missing channel_id")
            return

        channel_id = int(channel_id)

        # Get thread
        thread = self.bot.get_channel(channel_id)
        if not thread:
            logger.error(f"Thread {channel_id} not found for response")
            return

        # Cancel any animation
        await self.animation_manager.cancel(channel_id)

        # Check for early status message to reuse
        early_msg = None
        if hasattr(self.bot, 'early_status_messages'):
            early_msg = self.bot.early_status_messages.get(channel_id)
            if early_msg:
                del self.bot.early_status_messages[channel_id]

        try:
            if not content:
                logger.warning("Response has no content")
                return

            # Handle multi-part responses (already split by TROISE AI)
            if part and total_parts:
                prefix = f"**[{part}/{total_parts}]** " if part > 1 else ""
                display_content = prefix + content
            else:
                display_content = content

            # Split if still too long (shouldn't happen with TROISE AI formatting)
            if len(display_content) > 2000:
                chunks = split_message(display_content)
                if early_msg:
                    await self.rate_limiter.acquire()
                    await early_msg.edit(content=chunks[0])
                    for chunk in chunks[1:]:
                        await thread.send(chunk)
                else:
                    for chunk in chunks:
                        await thread.send(chunk)
            else:
                if early_msg:
                    await self.rate_limiter.acquire()
                    await early_msg.edit(content=display_content)
                else:
                    await thread.send(display_content)

            # Remove loading reaction from original message (only on last part)
            if message_channel_id and message_id and (not part or part == total_parts):
                await self._update_reaction(
                    str(message_channel_id),
                    str(message_id),
                    remove_emoji="⏳"
                )

            # Handle artifacts
            for artifact in artifacts:
                await self._handle_file_artifact({'file': artifact, 'channel_id': channel_id})

        except discord.HTTPException as e:
            logger.error(f"Discord error sending response: {e}")
        except Exception as e:
            logger.error(f"Error handling response: {e}")

    async def _handle_question(self, data: dict):
        """
        Handle question from agent - displays as normal Discord message.

        The user's next message in the thread becomes the answer,
        which is naturally captured in conversation history.
        """
        question = data.get('question', '')
        options = data.get('options', [])
        channel_id = data.get('channel_id')
        message_channel_id = data.get('message_channel_id', channel_id)
        message_id = data.get('message_id')

        if not channel_id:
            logger.warning("Question missing channel_id")
            return

        channel_id = int(channel_id)

        # Get thread
        thread = self.bot.get_channel(channel_id)
        if not thread:
            logger.error(f"Thread {channel_id} not found for question")
            return

        # Cancel any animation
        await self.animation_manager.cancel(channel_id)

        # Check for early status message to reuse
        early_msg = None
        if hasattr(self.bot, 'early_status_messages'):
            early_msg = self.bot.early_status_messages.get(channel_id)
            if early_msg:
                del self.bot.early_status_messages[channel_id]

        try:
            # Format the question with options if provided
            if options:
                options_text = "\n".join(f"• {opt}" for opt in options)
                display_content = f"{question}\n\n{options_text}"
            else:
                display_content = question

            if not display_content:
                logger.warning("Question has no content")
                return

            # Split if too long
            if len(display_content) > 2000:
                chunks = split_message(display_content)
                if early_msg:
                    await self.rate_limiter.acquire()
                    await early_msg.edit(content=chunks[0])
                    for chunk in chunks[1:]:
                        await thread.send(chunk)
                else:
                    for chunk in chunks:
                        await thread.send(chunk)
            else:
                if early_msg:
                    await self.rate_limiter.acquire()
                    await early_msg.edit(content=display_content)
                else:
                    await thread.send(display_content)

            # Remove loading reaction from original message
            if message_channel_id and message_id:
                await self._update_reaction(
                    str(message_channel_id),
                    str(message_id),
                    remove_emoji="⏳"
                )

            logger.info(f"Displayed agent question in thread {channel_id}")

        except discord.HTTPException as e:
            logger.error(f"Discord error sending question: {e}")
        except Exception as e:
            logger.error(f"Error handling question: {e}")

    async def _handle_file_artifact(self, data: dict, is_suggestion: bool = False):
        """
        Handle artifact with base64_data from TROISE AI.

        Args:
            data: Message data containing file info
            is_suggestion: If True, treat as low-confidence suggestion
        """
        # File info may be in 'file' key or directly in data
        file_info = data.get('file', data)
        channel_id = data.get('channel_id')

        filename = file_info.get('filename')
        base64_data = file_info.get('base64_data')
        mimetype = file_info.get('mimetype', 'application/octet-stream')

        if not channel_id:
            logger.warning("File artifact missing channel_id")
            return

        channel_id = int(channel_id)

        if not filename or not base64_data:
            logger.warning(f"File artifact missing required fields: filename={filename}, has_data={bool(base64_data)}")
            return

        # Get thread
        thread = self.bot.get_channel(channel_id)
        if not thread:
            logger.error(f"Thread {channel_id} not found for artifact")
            return

        try:
            # Decode base64 data
            file_bytes = base64.b64decode(base64_data)

            # Create Discord file object
            discord_file = discord.File(
                fp=io.BytesIO(file_bytes),
                filename=filename
            )

            # Send with appropriate label
            if is_suggestion:
                label = f"💡 **Suggested: {filename}** _(AI-generated, may need review)_"
            else:
                label = f"📎 **{filename}**"

            await thread.send(label, file=discord_file)

            logger.info(f"Uploaded artifact: {filename} ({len(file_bytes)} bytes)")

        except Exception as e:
            logger.error(f"Failed to upload artifact {filename}: {e}")
            await thread.send(f"❌ Failed to upload artifact `{filename}`: {str(e)}")

    # =========================================================================
    # Legacy Handler (fastapi-service compatibility - can be removed later)
    # =========================================================================

    async def _handle_stream_chunk(self, data: dict):
        """Handle streaming chunk update."""
        request_id = data.get('request_id')
        channel_id = int(data['channel_id'])
        message_channel_id = data.get('message_channel_id', channel_id)
        message_id = data.get('message_id')
        content = data['content']
        is_complete = data.get('is_complete', False)
        has_error = data.get('error', False)
        artifacts = data.get('artifacts', [])

        # Get thread
        thread = self.bot.get_channel(channel_id)
        if not thread:
            logger.error(f"❌ Thread {channel_id} not found for streaming")
            return

        # Initialize streaming_messages dict if not exists
        if not hasattr(self.bot, 'streaming_messages'):
            self.bot.streaming_messages = {}

        # Initialize rate limit backoff tracking
        if not hasattr(self.bot, 'stream_backoff'):
            self.bot.stream_backoff = {}  # request_id -> (backoff_delay, last_attempt_time)

        # Get current backoff state for this request
        backoff_delay, last_attempt = self.bot.stream_backoff.get(request_id, (0, 0))

        # Apply backoff delay if needed
        if backoff_delay > 0:
            import time
            time_since_last = time.time() - last_attempt
            if time_since_last < backoff_delay:
                wait_time = backoff_delay - time_since_last
                logger.info(f"⏱️  Backing off for {wait_time:.2f}s due to rate limits")
                await asyncio.sleep(wait_time)

        try:
            import time
            self.bot.stream_backoff[request_id] = (backoff_delay, time.time())

            # Check if there's an early status message for this thread
            early_msg = None
            if hasattr(self.bot, 'early_status_messages'):
                early_msg = self.bot.early_status_messages.get(channel_id)

            if request_id not in self.bot.streaming_messages:
                # First chunk
                # Debug logging to see what we're receiving
                logger.debug(f"🔍 First chunk for request {request_id}: "
                            f"length={len(content)}, "
                            f"stripped_length={len(content.strip())}, "
                            f"preview={repr(content[:100])}")

                # Cancel animation when first chunk arrives
                await self.animation_manager.cancel(channel_id)
                # Small delay to ensure any in-flight Discord edits from animation complete
                await asyncio.sleep(0.15)

                # If first chunk is a status message (e.g., retry message), restart animation
                # This handles the case where streaming returns empty and retry message is the first chunk
                if self.animation_manager.is_status_message(content) and early_msg:
                    base_text = content.strip('*\n. ')
                    await self.animation_manager.start_animation(channel_id, early_msg, base_text)
                    logger.debug(f"🔄 Restarted animation for first chunk status message: {base_text}")

                if early_msg:
                    # Reuse early status message - update it with new content
                    discord_msg = early_msg
                    # Remove from early_status_messages and move to streaming_messages
                    del self.bot.early_status_messages[channel_id]
                    self.bot.streaming_messages[request_id] = discord_msg

                    # Validate content before sending to Discord
                    # NOTE: Orchestrator already validates, but this is a safety net
                    if not self._has_meaningful_content(content):
                        logger.warning(f"⚠️  First chunk has no alphanumeric content, keeping status indicator")
                        # Message already moved to streaming_messages, next chunk will update it
                        return

                    # Update the message content (strip trailing whitespace before adding "...")
                    stripped = content.rstrip()
                    if stripped.endswith("...*") or stripped.endswith("..."):
                        display_content = content
                    else:
                        display_content = stripped + " ..."  # Use stripped version

                    # Truncate if too long (Discord 2000 char limit)
                    if len(display_content) > 2000:
                        display_content = display_content[:1900] + "\n\n... _(message too long, will send in multiple chunks)_"

                    logger.debug(f"🔍 Editing early status message with: {repr(display_content[:100])}")

                    # Wrap Discord API call in try-except for additional safety
                    try:
                        await self.rate_limiter.acquire()
                        await discord_msg.edit(content=display_content)
                        logger.debug(f"📡 Updated early status message for request {request_id}")
                    except discord.errors.HTTPException as e:
                        if e.code == 50006:
                            logger.error(f"❌ Empty message error despite validation: {repr(display_content[:50])}")
                        else:
                            raise  # Re-raise other errors
                else:
                    # Create new message with typing indicator

                    # Validate content before sending
                    if not self._has_meaningful_content(content):
                        logger.warning(f"⚠️  First chunk has no alphanumeric content, skipping")
                        # CRITICAL: Add placeholder so next chunk doesn't try to create another message
                        self.bot.streaming_messages[request_id] = None
                        return

                    stripped = content.rstrip()
                    if stripped.endswith("...*") or stripped.endswith("..."):
                        display_content = content
                    else:
                        display_content = stripped + " ..."  # Use stripped version

                    # Truncate if too long (Discord 2000 char limit)
                    if len(display_content) > 2000:
                        display_content = display_content[:1900] + "\n\n... _(message too long, will send in multiple chunks)_"

                    try:
                        discord_msg = await thread.send(display_content)
                        self.bot.streaming_messages[request_id] = discord_msg
                        logger.debug(f"📡 Started streaming for request {request_id}")

                        # Start animation if this is a status message
                        if self.animation_manager.is_status_message(content):
                            base_text = content.strip('*\n. ')
                            await self.animation_manager.start_animation(channel_id, discord_msg, base_text)
                            logger.debug(f"▶️  Started animation for new status message: {base_text}")
                    except discord.errors.HTTPException as e:
                        if e.code == 50006:
                            logger.error(f"❌ Empty message error: {repr(display_content[:50])}")
                        else:
                            raise
            else:
                # Subsequent chunks - edit existing message
                discord_msg = self.bot.streaming_messages.get(request_id)

                # Cancel animation if this is a status message update (prevents race condition)
                # Status messages: "*Retrying with non-streaming mode...*\n\n", etc.
                # Pass discord_msg to enable animation restart for retry messages
                await self.animation_manager.cancel_if_status_message(channel_id, content, discord_msg)

                # Handle case where first chunk was invalid (discord_msg is None)
                if discord_msg is None:
                    # First chunk had no alphanumeric content, treat this as first real chunk
                    if not self._has_meaningful_content(content):
                        logger.warning(f"⚠️  Still no alphanumeric content, skipping")
                        return

                    # Create message now
                    stripped = content.rstrip()
                    if stripped.endswith("...*") or stripped.endswith("..."):
                        display_content = content
                    else:
                        display_content = stripped + " ..."

                    # Truncate if too long (Discord 2000 char limit)
                    if len(display_content) > 2000:
                        display_content = display_content[:1900] + "\n\n... _(message too long, will send in multiple chunks)_"

                    try:
                        discord_msg = await thread.send(display_content)
                        self.bot.streaming_messages[request_id] = discord_msg
                        logger.debug(f"📡 Started streaming for request {request_id} (delayed)")
                    except discord.errors.HTTPException as e:
                        if e.code == 50006:
                            logger.error(f"❌ Empty message error: {repr(display_content[:50])}")
                        else:
                            raise
                    return

                # Normal update flow
                # Cancel animation before editing with actual content (if not already cancelled)
                # This ensures animation dots don't overwrite the real content
                if channel_id in self.animation_manager.tasks:
                    await self.animation_manager.cancel(channel_id)
                    await asyncio.sleep(0.15)  # Let pending Discord edits complete

                # Add typing indicator if incomplete, remove if complete
                stripped = content.rstrip()
                if is_complete:
                    display_content = content
                elif stripped.endswith("...*") or stripped.endswith("..."):
                    display_content = content
                else:
                    display_content = stripped + " ..."  # Use stripped version

                # Split if too long (Discord 2000 char limit)
                if len(display_content) > 2000:
                    display_content = display_content[:1900] + "\n\n... _(message too long, will send in multiple chunks)_"

                try:
                    await self.rate_limiter.acquire()
                    await discord_msg.edit(content=display_content)
                except discord.errors.HTTPException as e:
                    if e.code == 50006:
                        logger.error(f"❌ Empty message error on update: {repr(display_content[:50])}")
                        # Don't raise - next chunk will retry
                    else:
                        raise

            # If complete, clean up and handle artifacts
            if is_complete:
                logger.debug(f"✅ Completed streaming for request {request_id}")

                # Cancel animation when streaming completes (handles error messages)
                await self.animation_manager.cancel(channel_id)

                # Remove loading reaction from original message
                if message_id:
                    await self._update_reaction(
                        str(message_channel_id),
                        str(message_id),
                        remove_emoji="⏳"
                    )

                    # Add error reaction if failed
                    if has_error:
                        await self._update_reaction(
                            str(message_channel_id),
                            str(message_id),
                            add_emoji="❌"
                        )

                # Handle message splitting if final content is too long
                if len(content) > 2000:
                    logger.debug(f"📝 Splitting long streaming response ({len(content)} chars)")

                    # Get the split utility function
                    from bot.utils import split_message
                    chunks = split_message(content)

                    # Update first message with first chunk
                    await self.rate_limiter.acquire()
                    await discord_msg.edit(content=chunks[0])

                    # Send remaining chunks
                    for chunk in chunks[1:]:
                        await thread.send(chunk)

                # Upload artifacts if present
                if artifacts:
                    logger.debug(f"📎 Uploading {len(artifacts)} artifact(s) from streaming request")
                    for artifact in artifacts:
                        storage_path = artifact.get('storage_path')
                        filename = artifact.get('filename')

                        if not storage_path or not filename:
                            logger.warning(f"⚠️  Skipping artifact with missing data: {artifact}")
                            continue

                        try:
                            # Read artifact file
                            with open(storage_path, 'rb') as f:
                                file_data = f.read()

                            # Create Discord file object
                            discord_file = discord.File(
                                fp=io.BytesIO(file_data),
                                filename=filename
                            )

                            # Send as separate message
                            await thread.send(
                                f"📎 **{filename}**",
                                file=discord_file
                            )

                            logger.info(f"✅ Uploaded artifact: {filename} ({len(file_data)} bytes)")

                        except FileNotFoundError:
                            logger.error(f"❌ Artifact file not found: {storage_path}")
                            await thread.send(f"❌ Failed to upload artifact `{filename}`: file not found")
                        except Exception as e:
                            logger.error(f"❌ Failed to upload artifact {filename}: {e}")
                            await thread.send(f"❌ Failed to upload artifact `{filename}`: {str(e)}")

                # Clean up tracking
                if request_id in self.bot.streaming_messages:
                    del self.bot.streaming_messages[request_id]

                # Clean up backoff tracking on completion
                if request_id in self.bot.stream_backoff:
                    del self.bot.stream_backoff[request_id]

        except discord.HTTPException as e:
            # Handle Discord rate limits with exponential backoff
            if e.status == 429:
                # Get retry-after header if available (Discord provides this)
                retry_after = getattr(e, 'retry_after', None)

                if retry_after:
                    # Use Discord's suggested retry time
                    new_backoff = float(retry_after)
                    logger.warning(f"⚠️  Rate limited! Discord says retry after {new_backoff}s")
                else:
                    # Use exponential backoff: start at 2s, double each time
                    current_backoff = self.bot.stream_backoff.get(request_id, (0, 0))[0]
                    new_backoff = max(2.0, current_backoff * 2.0) if current_backoff > 0 else 2.0
                    logger.warning(f"⚠️  Rate limited! Backing off to {new_backoff}s (exponential)")

                # Update backoff state
                import time
                self.bot.stream_backoff[request_id] = (new_backoff, time.time())

                # Don't raise - just log and continue (next chunk will apply backoff)
            else:
                logger.error(f"❌ Discord HTTP error during streaming: {e}")
        except Exception as e:
            logger.error(f"❌ Error handling stream chunk for request {request_id}: {e}")

    # _handle_stream_complete() removed - artifacts now included in final stream_chunk

    async def _handle_early_status(self, data: dict):
        """
        Handle early status indicator (before file processing).

        This is sent immediately when files are detected, before OCR/processing.
        Stores message with thread_id as key since request_id isn't assigned yet.
        """
        channel_id = int(data['channel_id'])
        content = data['content']

        # Get thread
        thread = self.bot.get_channel(channel_id)
        if not thread:
            logger.error(f"❌ Thread {channel_id} not found for early status")
            return

        try:
            # Send initial status message
            # Don't add "..." since content already ends with it
            discord_msg = await thread.send(content)

            # Store message with thread_id as key (will be moved to request_id by stream_chunk)
            if not hasattr(self.bot, 'streaming_messages'):
                self.bot.streaming_messages = {}
            if not hasattr(self.bot, 'early_status_messages'):
                self.bot.early_status_messages = {}

            # Store in early_status_messages dict with thread_id as key
            self.bot.early_status_messages[channel_id] = discord_msg

            # Start animation (AnimationManager handles cancellation automatically)
            base_text = content.strip('*\n. ')
            await self.animation_manager.start_animation(channel_id, discord_msg, base_text)

            logger.debug(f"📡 Sent early status for thread {channel_id}: {content.strip()} (animating)")

        except Exception as e:
            logger.error(f"❌ Failed to send early status: {e}")
