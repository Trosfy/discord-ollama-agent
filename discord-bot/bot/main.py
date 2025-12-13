"""Discord bot entry point."""
import asyncio
import os
import sys
sys.path.insert(0, '/shared')

from dotenv import load_dotenv

from bot.client import DiscordBotClient
from bot.config import BotSettings

# Import logging client and health server
import logging_client
from health_server import HealthCheckServer

load_dotenv()

# Global bot instance for health checks
bot_instance = None


def check_websocket_connected() -> bool:
    """Check if WebSocket is connected to FastAPI."""
    if bot_instance is None:
        return False
    return bot_instance.ws_manager.connected


async def main():
    """Main entry point."""
    global bot_instance

    # Initialize logger
    logger = logging_client.setup_logger('discord-bot')
    logger.info("Initializing Discord bot...")

    settings = BotSettings()

    # Create bot client
    bot = DiscordBotClient(settings)
    bot_instance = bot  # Store for health checks

    # Setup and start health check server
    health_server = HealthCheckServer(service_name="discord-bot", port=9998)
    health_server.register_check("websocket", check_websocket_connected)
    health_server.start()
    logger.info("Health check endpoint started on port 9998")

    # Run bot
    logger.info("Starting Discord bot...")
    async with bot:
        await bot.start(settings.DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
