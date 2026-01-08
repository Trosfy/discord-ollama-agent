"""Discord bot client."""
import sys
sys.path.insert(0, '/shared')

import discord
from discord import app_commands
from discord.ext import commands
import asyncio

from bot.websocket_manager import WebSocketManager
from bot.message_handler import MessageHandler
from bot.config import BotSettings
import logging_client

# Initialize logger
logger = logging_client.setup_logger('discord-bot')


class DiscordBotClient(commands.Bot):
    """Discord bot with WebSocket connection to FastAPI."""

    def __init__(self, settings: BotSettings):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True

        super().__init__(command_prefix="!", intents=intents)

        self.settings = settings
        self.ws_manager = WebSocketManager(settings.FASTAPI_WS_URL)
        self.message_handler = MessageHandler(self, self.ws_manager)

        # Track pending requests
        self.pending_requests = {}  # message_id -> request_id

        # Register slash commands (tree is already created by commands.Bot)
        self._register_commands()

    def _register_commands(self):
        """Register slash commands."""

        @self.tree.command(name="help", description="Show bot usage instructions")
        async def help_command(interaction: discord.Interaction):
            """Show help message."""
            help_text = """**Discord Trollama Agent Help**

**How to use**:
- Mention me in any channel: `@bot your question`
- I'll create a thread and reply there
- Continue conversation in the thread by mentioning me

**Thread Commands**:
- `/help` - Show this help message
- `/reset` - Clear context in current thread
- `/summarize` - Summarize the conversation in this thread
- `/close` - Close thread and delete conversation history

**Configuration Commands**:
- `/configure-temperature <value|default>` - Set temperature (0.0-2.0)
- `/configure-thinking <true|false|default>` - Enable/disable thinking mode
- `/configure-model <model_name|default>` - Set preferred model
- `/configure-reset` - Reset all preferences to system defaults

**Status indicators**:
- ⏳ - Processing your request
- ❌ - Request failed"""

            await interaction.response.send_message(help_text, ephemeral=True)

        @self.tree.command(name="reset", description="Clear conversation context in this thread")
        async def reset_command(interaction: discord.Interaction):
            """Reset context in current thread."""
            # Check if in thread
            if not isinstance(interaction.channel, discord.Thread):
                await interaction.response.send_message(
                    "⚠️ `/reset` can only be used in a thread!",
                    ephemeral=True
                )
                return

            # Send reset request to FastAPI via WebSocket
            thread_id = str(interaction.channel.id)

            try:
                await self.ws_manager.send_message({
                    'type': 'reset',
                    'conversation_id': thread_id,
                    'user_id': str(interaction.user.id)
                })

                await interaction.response.send_message(
                    "🔄 Context reset for this thread!",
                    ephemeral=True
                )
                logger.info(f"🔄 Reset context for thread {thread_id} by user {interaction.user.id}")
            except Exception as e:
                logger.error(f"Failed to reset thread {thread_id}: {e}")
                await interaction.response.send_message(
                    f"❌ Failed to reset context: {str(e)}",
                    ephemeral=True
                )

        @self.tree.command(name="summarize", description="Summarize the conversation in this thread")
        async def summarize_command(interaction: discord.Interaction):
            """Summarize conversation in current thread."""
            # Check if in thread
            if not isinstance(interaction.channel, discord.Thread):
                await interaction.response.send_message(
                    "⚠️ `/summarize` can only be used in a thread!",
                    ephemeral=True
                )
                return

            thread_id = str(interaction.channel.id)

            # Defer response as summarization may take time
            await interaction.response.defer(ephemeral=True)

            try:
                await self.ws_manager.send_message({
                    'type': 'summarize',
                    'conversation_id': thread_id,
                    'user_id': str(interaction.user.id),
                    'interaction_id': str(interaction.id)  # Track interaction for follow-up
                })

                # Store interaction for later follow-up
                if not hasattr(self, 'pending_interactions'):
                    self.pending_interactions = {}
                self.pending_interactions[str(interaction.id)] = interaction

                logger.info(f"📝 Summarize request for thread {thread_id} by user {interaction.user.id}")
            except Exception as e:
                logger.error(f"Failed to request summary for thread {thread_id}: {e}")
                await interaction.followup.send(
                    f"❌ Failed to request summary: {str(e)}",
                    ephemeral=True
                )

        @self.tree.command(name="close", description="Close thread and delete conversation history")
        async def close_command(interaction: discord.Interaction):
            """Close thread and delete conversation history."""
            # Check if in thread
            if not isinstance(interaction.channel, discord.Thread):
                await interaction.response.send_message(
                    "⚠️ `/close` can only be used in a thread!",
                    ephemeral=True
                )
                return

            thread_id = str(interaction.channel.id)
            thread = interaction.channel

            try:
                # Send close request to FastAPI to delete from DynamoDB
                await self.ws_manager.send_message({
                    'type': 'close',
                    'conversation_id': thread_id,
                    'user_id': str(interaction.user.id)
                })

                await interaction.response.send_message(
                    "🗑️ Thread closed and conversation history deleted!",
                    ephemeral=True
                )

                # Archive/lock the Discord thread
                await thread.edit(archived=True, locked=True)
                logger.info(f"🗑️ Closed thread {thread_id} by user {interaction.user.id}")
            except Exception as e:
                logger.error(f"Failed to close thread {thread_id}: {e}")
                await interaction.response.send_message(
                    f"❌ Failed to close thread: {str(e)}",
                    ephemeral=True
                )

        @self.tree.command(name="configure-temperature", description="Set your preferred temperature (0.0-2.0)")
        @app_commands.describe(value="Temperature value (0.0-2.0) or 'default' to reset")
        async def configure_temperature_command(interaction: discord.Interaction, value: str):
            """Configure user's preferred temperature."""
            user_id = str(interaction.user.id)

            try:
                # Validate and parse value
                if value.lower() == 'default':
                    temp_value = None
                else:
                    try:
                        temp_value = float(value)
                        if not 0.0 <= temp_value <= 2.0:
                            await interaction.response.send_message(
                                "❌ Temperature must be between 0.0 and 2.0",
                                ephemeral=True
                            )
                            return
                    except ValueError:
                        await interaction.response.send_message(
                            "❌ Invalid temperature value. Use a number (0.0-2.0) or 'default'",
                            ephemeral=True
                        )
                        return

                # Send configure request to FastAPI
                await self.ws_manager.send_message({
                    'type': 'configure',
                    'setting': 'temperature',
                    'value': temp_value,
                    'user_id': user_id,
                    'interaction_id': str(interaction.id)
                })

                # Store interaction for follow-up
                if not hasattr(self, 'pending_interactions'):
                    self.pending_interactions = {}
                self.pending_interactions[str(interaction.id)] = interaction

                await interaction.response.defer(ephemeral=True)
                logger.info(f"⚙️  Temperature config request from user {user_id}: {value}")
            except Exception as e:
                logger.error(f"Failed to configure temperature for user {user_id}: {e}")
                await interaction.response.send_message(
                    f"❌ Failed to update temperature: {str(e)}",
                    ephemeral=True
                )

        @self.tree.command(name="configure-thinking", description="Set thinking mode preference")
        @app_commands.describe(enabled="Enable thinking mode or use system recommendation")
        @app_commands.choices(enabled=[
            app_commands.Choice(name="System Recommendation (auto-detect)", value="default"),
            app_commands.Choice(name="Enable (force on)", value="true"),
            app_commands.Choice(name="Disable (force off)", value="false")
        ])
        async def configure_thinking_command(interaction: discord.Interaction, enabled: app_commands.Choice[str]):
            """Configure user's thinking mode preference."""
            user_id = str(interaction.user.id)

            try:
                # Parse value
                if enabled.value == 'true':
                    thinking_value = True
                elif enabled.value == 'false':
                    thinking_value = False
                else:  # 'default'
                    thinking_value = None

                # Send configure request to FastAPI
                await self.ws_manager.send_message({
                    'type': 'configure',
                    'setting': 'thinking',
                    'value': thinking_value,
                    'user_id': user_id,
                    'interaction_id': str(interaction.id)
                })

                # Store interaction for follow-up
                if not hasattr(self, 'pending_interactions'):
                    self.pending_interactions = {}
                self.pending_interactions[str(interaction.id)] = interaction

                await interaction.response.defer(ephemeral=True)
                logger.info(f"⚙️  Thinking config request from user {user_id}: {enabled.value}")
            except Exception as e:
                logger.error(f"Failed to configure thinking for user {user_id}: {e}")
                await interaction.response.send_message(
                    f"❌ Failed to update thinking mode: {str(e)}",
                    ephemeral=True
                )

        @self.tree.command(name="configure-model", description="Set your preferred model")
        @app_commands.describe(model="Select model or use system recommendation")
        @app_commands.choices(model=[
            app_commands.Choice(name="System Recommendation (auto-select)", value="default"),
            app_commands.Choice(name="gpt-oss:20b (tools, thinking)", value="gpt-oss:20b"),
            app_commands.Choice(name="magistral:24b (tools, thinking)", value="magistral:24b"),
            app_commands.Choice(name="deepseek-r1:14b (thinking only)", value="deepseek-r1:14b"),
            app_commands.Choice(name="qwen2.5-coder:7b (tools)", value="qwen2.5-coder:7b"),
            app_commands.Choice(name="qwen3-coder:30b (tools)", value="qwen3-coder:30b"),
            app_commands.Choice(name="ministral-3:14b (vision, tools)", value="ministral-3:14b"),
            app_commands.Choice(name="qwen3-vl:8b (vision, tools, thinking)", value="qwen3-vl:8b"),
        ])
        async def configure_model_command(interaction: discord.Interaction, model: app_commands.Choice[str]):
            """Configure user's preferred model."""
            user_id = str(interaction.user.id)

            try:
                # Parse value
                if model.value.lower() == 'default':
                    model_value = None
                else:
                    model_value = model.value

                # Send configure request to FastAPI
                await self.ws_manager.send_message({
                    'type': 'configure',
                    'setting': 'model',
                    'value': model_value,
                    'user_id': user_id,
                    'interaction_id': str(interaction.id)
                })

                # Store interaction for follow-up
                if not hasattr(self, 'pending_interactions'):
                    self.pending_interactions = {}
                self.pending_interactions[str(interaction.id)] = interaction

                await interaction.response.defer(ephemeral=True)
                logger.info(f"⚙️  Model config request from user {user_id}: {model.value}")
            except Exception as e:
                logger.error(f"Failed to configure model for user {user_id}: {e}")
                await interaction.response.send_message(
                    f"❌ Failed to update model: {str(e)}",
                    ephemeral=True
                )

        @self.tree.command(name="configure-reset", description="Reset all preferences to system defaults")
        async def configure_reset_command(interaction: discord.Interaction):
            """Reset all user preferences to defaults."""
            user_id = str(interaction.user.id)

            try:
                # Send configure reset request to FastAPI
                await self.ws_manager.send_message({
                    'type': 'configure',
                    'setting': 'reset',
                    'value': None,
                    'user_id': user_id,
                    'interaction_id': str(interaction.id)
                })

                # Store interaction for follow-up
                if not hasattr(self, 'pending_interactions'):
                    self.pending_interactions = {}
                self.pending_interactions[str(interaction.id)] = interaction

                await interaction.response.defer(ephemeral=True)
                logger.info(f"⚙️  Reset preferences request from user {user_id}")
            except Exception as e:
                logger.error(f"Failed to reset preferences for user {user_id}: {e}")
                await interaction.response.send_message(
                    f"❌ Failed to reset preferences: {str(e)}",
                    ephemeral=True
                )

        # Register admin command group
        from bot.admin_commands import admin
        self.tree.add_command(admin)
        logger.info("✅ Admin commands registered")

    async def setup_hook(self):
        """Setup hook called when bot starts."""
        # Connect to FastAPI WebSocket
        await self.ws_manager.connect(str(self.user.id))

        # Start listening for responses
        asyncio.create_task(self.ws_manager.listen_for_responses(
            self.message_handler.handle_response
        ))

        # Sync slash commands globally
        await self.tree.sync()
        logger.info("✅ Slash commands synced globally")

    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"✅ Logged in as {self.user.name} ({self.user.id})")
        logger.info(f"✅ Connected to FastAPI at {self.settings.FASTAPI_WS_URL}")

    async def on_message(self, message: discord.Message):
        """
        Handle incoming messages.

        Args:
            message: Discord message object
        """
        # Ignore own messages
        if message.author == self.user:
            return

        # Only respond to mentions or DMs
        if self.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
            await self.message_handler.handle_user_message(message)

    async def on_message_delete(self, message: discord.Message):
        """
        Handle message deletion - cancel request if queued.

        Args:
            message: Deleted Discord message object
        """
        if message.id in self.pending_requests:
            request_id = self.pending_requests[message.id]
            await self.ws_manager.cancel_request(request_id)
            del self.pending_requests[message.id]

    async def close(self):
        """Cleanup on shutdown."""
        await self.ws_manager.disconnect()
        await super().close()
