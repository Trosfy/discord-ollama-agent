#!/usr/bin/env python3
"""Quick script to test if Discord bot token is valid."""
import asyncio
import discord
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

async def test_token():
    token = os.getenv('DISCORD_TOKEN')

    if not token:
        print("❌ No DISCORD_TOKEN found in .env file")
        return False

    print(f"📋 Testing token (length: {len(token)} chars)")
    print(f"📋 First 30 chars: {token[:30]}...")

    # Create a minimal client
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"✅ Token is VALID!")
        print(f"✅ Logged in as: {client.user.name} (ID: {client.user.id})")
        await client.close()

    try:
        await client.start(token)
    except discord.LoginFailure as e:
        print(f"❌ Token is INVALID: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

    return True

if __name__ == "__main__":
    asyncio.run(test_token())
