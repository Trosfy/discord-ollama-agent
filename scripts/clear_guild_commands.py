"""Clear guild-specific slash commands."""
import discord
from discord import app_commands
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

if len(sys.argv) < 2:
    print("Usage: python clear_guild_commands.py <GUILD_ID>")
    exit(1)

GUILD_ID = sys.argv[1].strip()

if not DISCORD_TOKEN:
    print("❌ DISCORD_TOKEN not found in .env file")
    exit(1)


class ClearCommandsBot(discord.Client):
    """Minimal bot to clear guild commands."""

    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.guild_id = int(GUILD_ID)

    async def setup_hook(self):
        """Clear guild commands."""
        guild = discord.Object(id=self.guild_id)

        # Clear all commands in the guild
        self.tree.clear_commands(guild=guild)
        await self.tree.sync(guild=guild)

        print(f"✅ Cleared all guild-specific commands from guild {self.guild_id}")
        print("\nGlobal commands will remain (they take up to 1 hour to fully propagate)")

        await self.close()


async def main():
    """Run the clear bot."""
    print("🧹 Clearing guild-specific slash commands...\n")

    client = ClearCommandsBot()
    async with client:
        await client.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
