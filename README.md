# Discord-Trollama Agent

A production-grade Discord bot that connects users to a local Ollama LLM (gpt-oss:20b) through a FastAPI backend.

## Architecture

- **Discord Bot** - Message relay via WebSocket
- **FastAPI Monolith** - All business logic, FIFO queue, orchestration
- **DynamoDB Local** - Conversation history & user management
- **Ollama** (on host) - LLM inference

## Features

- Token-based usage tracking (weekly budgets)
- Automatic conversation summarization
- FIFO queue with visibility timeout (SQS-like)
- WebSocket-based real-time updates
- Request cancellation support
- Maintenance mode (soft + hard)
- Failure recovery with retries
- SOLID architecture for easy microservices extraction

## Prerequisites

- Docker & Docker Compose
- Ollama running on host with `gpt-oss:20b` model
- Discord bot token

## Quick Start

1. **Clone and configure:**
   ```bash
   cd discord-ollama-agent
   cp .env.example .env
   # Edit .env with your Discord token
   ```

2. **Start Ollama on host:**
   ```bash
   ollama serve
   ollama pull gpt-oss:20b
   ```

3. **Start all services:**
   ```bash
   docker-compose up --build
   ```

4. **Verify health:**
   ```bash
   curl http://localhost:8001/health
   ```

5. **Test in Discord:**
   - Mention your bot: `@YourBot Hello!`
   - Or DM the bot directly

## Development

### Project Structure

```
discord-ollama-agent/
├── docker-compose.yml
├── .env.example
├── fastapi-service/      # FastAPI backend
│   ├── app/
│   │   ├── interfaces/   # Abstract base classes (SOLID)
│   │   ├── implementations/  # Concrete implementations
│   │   ├── services/     # Business logic
│   │   ├── models/       # Pydantic models
│   │   ├── api/          # API endpoints
│   │   └── utils/        # Utilities
├── discord-bot/          # Discord bot client
│   └── bot/
└── data/                 # DynamoDB volume
```

### Running Tests

```bash
# FastAPI service tests
cd fastapi-service
uv pip install --dev
pytest

# Discord bot tests
cd discord-bot
uv pip install --dev
pytest
```

### Development Commands

```bash
# View logs
docker-compose logs -f fastapi-service
docker-compose logs -f discord-bot

# Restart a service
docker-compose restart fastapi-service

# Stop all services
docker-compose down

# Reset database (removes all data)
docker-compose down -v
```

## API Endpoints

### Health & Status
- `GET /health` - Service health check
- `GET /` - Service info

### WebSocket
- `WS /ws/discord` - Discord bot communication

### Discord API (REST fallback)
- `POST /api/discord/message` - Submit message
- `GET /api/discord/status/{request_id}` - Get request status
- `DELETE /api/discord/cancel/{request_id}` - Cancel request

### User API
- `GET /api/user/{user_id}` - Get user info
- `PATCH /api/user/{user_id}/preferences` - Update preferences
- `GET /api/user/{user_id}/history` - Get conversation history

### Admin API
- `POST /api/admin/grant-tokens` - Grant bonus tokens
- `POST /api/admin/maintenance/soft` - Enable soft maintenance
- `POST /api/admin/maintenance/hard` - Enable hard maintenance
- `GET /api/admin/queue/stats` - Get queue statistics

## Configuration

All configuration is done via environment variables. See `.env.example` for all available options.

### Key Settings

- `OLLAMA_DEFAULT_MODEL` - Default Ollama model (default: gpt-oss:20b)
- `MAX_QUEUE_SIZE` - Maximum queue size (default: 50)
- `MAX_RETRIES` - Retry attempts for failed requests (default: 3)
- `FREE_TIER_WEEKLY_BUDGET` - Free tier token budget (default: 100k)
- `ADMIN_TIER_WEEKLY_BUDGET` - Admin tier token budget (default: 500k)

## SOLID Architecture

This project follows SOLID principles for easy refactoring and microservices extraction:

- **Single Responsibility**: Each service has one clear purpose
- **Open/Closed**: Open for extension via interfaces, closed for modification
- **Liskov Substitution**: All implementations can replace their interfaces
- **Interface Segregation**: Clean, focused interfaces
- **Dependency Inversion**: Services depend on interfaces, not implementations

### Future Microservices Path

The current monolithic FastAPI service can be extracted into separate containers:
- API Gateway
- Orchestrator Service
- LLM Service
- Storage Service (swap DynamoDB for PostgreSQL/Redis)
- Queue Service (swap in-memory for Redis/SQS)

Each extraction only requires implementing the same interface with a new backend.

## License

MIT

## Support

For issues, please open a GitHub issue with detailed information.
