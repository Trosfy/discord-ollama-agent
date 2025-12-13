"""Sync Discord slash commands to a specific guild for instant updates."""
import discord
from discord import app_commands
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

if len(sys.argv) < 2:
    print("Usage: python sync_commands.py <GUILD_ID>")
    print("\nTo find your Guild ID:")
    print("1. Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)")
    print("2. Right-click your server icon and select 'Copy Server ID'")
    exit(1)

GUILD_ID = sys.argv[1].strip()

if not DISCORD_TOKEN:
    print("❌ DISCORD_TOKEN not found in .env file")
    exit(1)

if not GUILD_ID or not GUILD_ID.isdigit():
    print("❌ Invalid Guild ID")
    exit(1)


class CommandSyncBot(discord.Client):
    """Minimal bot to sync commands."""

    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.guild_id = int(GUILD_ID)

    async def setup_hook(self):
        """Register commands and sync."""
        # Register all commands
        @self.tree.command(name="help", description="Show bot usage instructions")
        async def help_command(interaction: discord.Interaction):
            pass

        @self.tree.command(name="reset", description="Clear conversation context in this thread")
        async def reset_command(interaction: discord.Interaction):
            pass

        @self.tree.command(name="summarize", description="Summarize the conversation in this thread")
        async def summarize_command(interaction: discord.Interaction):
            pass

        @self.tree.command(name="close", description="Close thread and delete conversation history")
        async def close_command(interaction: discord.Interaction):
            pass

        @self.tree.command(name="configure-temperature", description="Set your preferred temperature (0.0-2.0)")
        @app_commands.describe(value="Temperature value (0.0-2.0) or 'default' to reset")
        async def configure_temperature_command(interaction: discord.Interaction, value: str):
            pass

        @self.tree.command(name="configure-thinking", description="Set thinking mode preference")
        @app_commands.describe(enabled="Enable thinking mode or use system recommendation")
        @app_commands.choices(enabled=[
            app_commands.Choice(name="System Recommendation (auto-detect)", value="default"),
            app_commands.Choice(name="Enable (force on)", value="true"),
            app_commands.Choice(name="Disable (force off)", value="false")
        ])
        async def configure_thinking_command(interaction: discord.Interaction, enabled: app_commands.Choice[str]):
            pass

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
            pass

        @self.tree.command(name="configure-reset", description="Reset all preferences to system defaults")
        async def configure_reset_command(interaction: discord.Interaction):
            pass

        # Sync to guild
        guild = discord.Object(id=self.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print(f"✅ Commands synced to guild {self.guild_id}")
        print("\nCommands synced:")
        print("  • /help - Show bot usage instructions")
        print("  • /reset - Clear conversation context in this thread")
        print("  • /summarize - Summarize the conversation in this thread")
        print("  • /close - Close thread and delete conversation history")
        print("  • /configure-temperature - Set your preferred temperature (0.0-2.0)")
        print("  • /configure-thinking - Set thinking mode preference")
        print("  • /configure-model - Set your preferred model")
        print("  • /configure-reset - Reset all preferences to system defaults")
        print("\n✅ Slash commands should appear in your server immediately!")

        await self.close()


async def main():
    """Run the sync bot."""
    print("🔄 Syncing slash commands to your Discord server...\n")

    client = CommandSyncBot()
    async with client:
        await client.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
