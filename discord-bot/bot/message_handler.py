"""Message handling for Discord bot."""
import sys
sys.path.insert(0, '/shared')

import discord
import io
import asyncio
import re
from bot.websocket_manager import WebSocketManager
from bot.utils import split_message, validate_attachment, encode_file_base64
from bot.animation_manager import AnimationManager
import logging_client

# Initialize logger
logger = logging_client.setup_logger('discord-bot')


class MessageHandler:
    """Handles Discord messages and responses."""

    def __init__(self, bot, ws_manager: WebSocketManager):
        self.bot = bot
        self.ws_manager = ws_manager
        self.animation_manager = AnimationManager()  # Dedicated animation management

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

        # Process file attachments
        attachments = []
        if message.attachments:
            logger.info(f"📎 Processing {len(message.attachments)} attachment(s)")

            for attachment in message.attachments:
                # Validate attachment
                if not validate_attachment(attachment):
                    logger.warning(f"⚠️  Skipping invalid attachment: {attachment.filename} ({attachment.size} bytes, {attachment.content_type})")
                    await thread.send(f"⚠️ Skipped `{attachment.filename}`: file too large or unsupported type")
                    continue

                # Download and encode file
                try:
                    file_data = await attachment.read()
                    file_base64 = encode_file_base64(file_data)

                    attachments.append({
                        'filename': attachment.filename,
                        'content_type': attachment.content_type or 'application/octet-stream',
                        'size': attachment.size,
                        'data_base64': file_base64
                    })

                    logger.info(f"✅ Encoded attachment: {attachment.filename} ({attachment.size} bytes)")
                except Exception as e:
                    logger.error(f"❌ Failed to process attachment {attachment.filename}: {e}")
                    await thread.send(f"❌ Failed to process `{attachment.filename}`: {str(e)}")

        # Send to FastAPI
        data = {
            'type': 'message',
            'user_id': str(message.author.id),
            'conversation_id': thread_id,  # Discord thread ID = conversation ID
            'message': content,
            'message_id': str(message.id),
            'channel_id': str(thread.id),  # Thread ID for responses
            'message_channel_id': str(message.channel.id),  # Where the message actually is (for reactions)
            'guild_id': str(message.guild.id) if message.guild else None,
            'attachments': attachments  # NEW: Include file attachments
        }

        await self.ws_manager.send_message(data)

    async def handle_response(self, data: dict):
        """
        Handle response from FastAPI.

        Args:
            data: Response data dictionary
        """
        response_type = data.get('type')

        if response_type == 'queued':
            await self._handle_queued(data)

        elif response_type == 'processing':
            await self._handle_processing(data)

        # 'result' removed - now handled by 'stream_chunk' (unified)

        elif response_type == 'failed':
            await self._handle_failed(data)

        elif response_type == 'error':
            await self._handle_error(data)

        elif response_type == 'maintenance_warning':
            await self._handle_maintenance_warning(data)

        elif response_type == 'cancelled':
            logger.info(f"✅ Request {data.get('request_id')} cancelled")

        elif response_type == 'summarize_response':
            await self._handle_summarize_response(data)

        elif response_type == 'configure_response':
            await self._handle_configure_response(data)

        elif response_type == 'stream_chunk':
            await self._handle_stream_chunk(data)  # ✅ Unified handler for both streaming and non-streaming

        # 'stream_complete' removed - artifacts now in final stream_chunk

        elif response_type == 'early_status':
            await self._handle_early_status(data)

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
