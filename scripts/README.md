# Scripts Directory

Utility scripts for Discord Trollama Agent development and deployment.

## Scripts

### `start.sh`
Starts all Docker Compose services with proper dependency ordering.

```bash
./scripts/start.sh
```

### `sync_commands.py`
Syncs Discord slash commands to a specific guild (server) for instant updates during development.

```bash
# Requires: discord.py, python-dotenv
uv run --with discord.py --with python-dotenv scripts/sync_commands.py <GUILD_ID>
```

**Usage:**
1. Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)
2. Right-click your server icon and select "Copy Server ID"
3. Run the script with your Guild ID

**Commands synced:**
- `/help` - Show bot usage instructions
- `/reset` - Clear conversation context in thread
- `/summarize` - Summarize conversation in thread
- `/close` - Close thread and delete conversation history

### `clear_guild_commands.py`
Clears guild-specific slash commands (removes duplicates if you synced to both global and guild).

```bash
# Requires: discord.py, python-dotenv
uv run --with discord.py --with python-dotenv scripts/clear_guild_commands.py <GUILD_ID>
```

### `test_token.py`
Tests the Discord bot token from `.env` file to verify authentication.

```bash
python scripts/test_token.py
```

### `test_token_discord.py`
Alternative Discord token test script (from discord-bot directory).

```bash
python scripts/test_token_discord.py
```

### `run-tests.sh`
Runs the test suite using Docker Compose test configuration.

```bash
./scripts/run-tests.sh
```

This script:
- Uses a separate test service that doesn't pollute production containers
- Installs dev dependencies (pytest, pytest-asyncio) only in test container
- Runs all tests with proper environment setup

See [fastapi-service/tests/TESTING.md](../fastapi-service/tests/TESTING.md) for detailed testing documentation.

## Notes

- All scripts should be run from the repository root
- Discord scripts require a valid `DISCORD_TOKEN` in `.env`
- Use `uv` for dependency management (faster than pip)
