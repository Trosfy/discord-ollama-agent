# Discord-Trollama Agent

A production-grade Discord bot that intelligently routes user messages to specialized local Ollama language models, providing an AI assistant experience with thread-based conversations, automatic context management, and artifact generation.

## What is this?

This system connects Discord users to locally-hosted LLMs (via Ollama) through an intelligent routing system that automatically selects the best model for each task. Whether you're asking a math question, requesting code generation, or conducting research, the bot routes your query to a specialized model optimized for that specific task type.

**Key Innovation**: Instead of using one model for everything, the system uses LLM-based semantic routing to classify queries and assign them to specialized models, resulting in better quality responses at faster speeds.

## Key Features

- **Intelligent Routing** - Automatically classifies queries and routes to specialized models:
  - Math problems → rnj-1:8b (optimized for mathematical reasoning)
  - Simple code → rnj-1:8b (fast function/algorithm generation)
  - Complex code → deepcoder:14b (system design and architecture)
  - Reasoning → magistral:24b (analysis, comparisons, trade-offs)
  - Research → magistral:24b (deep research with web search)
  - General chat → gpt-oss:20b (fast, versatile daily driver)

- **Thread-Based Conversations** - Each Discord thread maintains isolated conversation history

- **Token Budget Tracking** - Weekly token budgets per user (100k free tier, 500k admin tier)

- **Automatic Summarization** - Long conversations are automatically summarized to stay within context limits

- **Artifact Generation** - Automatically detects when you want code/documents and saves them as downloadable files

- **Web Search Integration** - Research and reasoning routes can search the web for current information

- **Real-Time Streaming** - See responses as they're generated, with status indicators

- **File Upload Support** - Upload images for OCR/vision analysis

- **Request Cancellation** - Cancel long-running requests anytime

- **Maintenance Modes** - Soft (queue requests) and hard (reject requests) maintenance

- **Comprehensive Monitoring** - Health dashboard, centralized logging, alert management

## Architecture

```
┌─────────────┐
│   Discord   │  Users interact via Discord
│    Users    │
└──────┬──────┘
       │ Messages
       ↓
┌──────────────────┐
│  Discord Bot     │  Relays messages via WebSocket
│  (Python)        │
└──────┬───────────┘
       │ WebSocket (ws://fastapi-service:8000/ws/discord)
       ↓
┌──────────────────────────────────────────────────────────┐
│  FastAPI Service (Main Brain)                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │ 1. Queue: FIFO queue with visibility timeout      │  │
│  │ 2. Router: LLM-based query classification         │  │
│  │ 3. Context Manager: Conversation history + summary│  │
│  │ 4. Orchestrator: Coordinates all services         │  │
│  │ 5. Strands LLM: Generates responses with tools    │  │
│  │ 6. Post-Processor: Detects and saves artifacts    │  │
│  └────────────────────────────────────────────────────┘  │
└──────┬──────────────────────────────┬────────────────────┘
       │                              │
       ↓                              ↓
┌──────────────┐              ┌──────────────┐
│  DynamoDB    │              │   Ollama     │
│  Local       │              │   (Host)     │
│              │              │              │
│ - Users      │              │ - Models     │
│ - Convos     │              │ - Inference  │
│ - Tokens     │              │              │
└──────────────┘              └──────────────┘

Supporting Services:
- Logging Service: Centralized log collection
- Monitoring Service: Health dashboard + alerts
```

## Quick Start

### Prerequisites

1. **Docker & Docker Compose** - For running all services
2. **Ollama** - Running on host machine with models pulled
3. **Discord Bot Token** - From Discord Developer Portal
4. **System Requirements**:
   - 16GB+ RAM (for model inference)
   - 50GB+ disk space (for models)
   - Linux/WSL2 recommended

### Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/discord-ollama-agent.git
cd discord-ollama-agent
```

#### 2. Set Up Ollama Models

Install Ollama on your host machine (outside Docker):

```bash
# Install Ollama (if not already installed)
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
ollama serve

# Pull required models (in separate terminal)
ollama pull gpt-oss:20b          # Router + general chat (14GB)
ollama pull rnj-1:8b             # Math + simple code (5GB)
ollama pull deepcoder:14b        # Complex code (9GB)
ollama pull magistral:24b        # Reasoning + research (15GB)
ollama pull qwen3-vl:8b          # OCR/vision (5GB)
```

**Note**: Models will download to `~/.ollama/models` and can be shared across projects.

#### 3. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your Discord token
nano .env  # or use your preferred editor
```

**Required Configuration** in `.env`:

```bash
# Discord Bot Token (REQUIRED)
DISCORD_TOKEN=your_discord_bot_token_here

# Ollama Configuration
OLLAMA_HOST=http://host.docker.internal:11434  # Default for Docker
OLLAMA_DEFAULT_MODEL=gpt-oss:20b

# Queue Settings (defaults are fine for most users)
MAX_QUEUE_SIZE=50
MAX_RETRIES=3

# Maintenance (set to false for normal operation)
MAINTENANCE_MODE=false
MAINTENANCE_MODE_HARD=false
```

**Getting a Discord Bot Token**:
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create New Application
3. Go to "Bot" section and create a bot
4. Copy the token and paste into `.env`
5. Enable required intents: Message Content Intent, Server Members Intent
6. Invite bot to your server with permissions: Send Messages, Create Threads, Read Message History

#### 4. Start All Services

```bash
# Build and start all containers
docker-compose up --build

# Or run in background
docker-compose up --build -d
```

**Services will start in order**:
1. `logging-service` (port 9999) - Centralized logging
2. `dynamodb-local` (port 8000) - Local database
3. `fastapi-service` (port 8001) - Main API
4. `discord-bot` (port 9997) - Discord connection
5. `monitoring-service` (port 8080) - Health dashboard

#### 5. Verify Health

```bash
# Check FastAPI service health
curl http://localhost:8001/health

# Check monitoring dashboard
open http://localhost:8080
```

Expected response:
```json
{
  "status": "healthy",
  "service": "Discord-Trollama Agent",
  "version": "0.1.0",
  "components": {
    "database": "healthy",
    "ollama": "healthy",
    "queue": "healthy"
  }
}
```

#### 6. Test in Discord

1. Go to your Discord server
2. Mention the bot: `@YourBot Hello! Can you help me with math?`
3. Or send a DM directly
4. Bot will create a thread and respond

**Test different routes**:
- Math: `@YourBot solve x^2 + 5x + 6 = 0`
- Code: `@YourBot write a Python function to check if a number is prime`
- Research: `@YourBot research the latest developments in quantum computing`
- General: `@YourBot what's the weather like today?`

## Configuration Reference

### Environment Variables

#### Discord Configuration

```bash
# REQUIRED: Your Discord bot token from Developer Portal
DISCORD_TOKEN=your_token_here

# WebSocket URL for Discord bot to connect to FastAPI
# Default is fine if using docker-compose
FASTAPI_WS_URL=ws://fastapi-service:8000/ws/discord
```

#### Ollama Configuration

```bash
# Ollama host URL
# Use host.docker.internal for Docker on Mac/Windows
# Use 172.17.0.1 for Docker on Linux
OLLAMA_HOST=http://host.docker.internal:11434

# Default model for general tasks
OLLAMA_DEFAULT_MODEL=gpt-oss:20b

# Model keep-alive time (seconds)
# 0 = unload immediately after use (saves memory)
# 60 = keep loaded for 1 minute
OLLAMA_KEEP_ALIVE=0
```

#### Queue Settings

```bash
# Maximum number of queued requests
MAX_QUEUE_SIZE=50

# Maximum retry attempts for failed requests
MAX_RETRIES=3

# Visibility timeout (seconds) - how long a request is invisible while processing
# 1200 = 20 minutes (handles long-running tasks)
VISIBILITY_TIMEOUT=1200
```

#### Token Budget Settings

```bash
# Weekly token budget for free tier users
FREE_TIER_WEEKLY_BUDGET=100000  # 100k tokens

# Weekly token budget for admin tier users
ADMIN_TIER_WEEKLY_BUDGET=500000  # 500k tokens

# Set to true to disable budget enforcement (unlimited usage)
DISABLE_TOKEN_BUDGET=true
```

#### Logging Configuration

```bash
# Days to retain log files
LOG_RETENTION_DAYS=2

# How often to run log cleanup (hours)
LOG_CLEANUP_INTERVAL_HOURS=6

# Maximum log file size before rotation (bytes)
LOG_MAX_BYTES=10485760  # 10MB

# Number of rotated backup files to keep
LOG_BACKUP_COUNT=5
```

#### Streaming Configuration

```bash
# Enable real-time streaming responses
ENABLE_STREAMING=true

# Interval between stream chunk updates (seconds)
# 1.1s is safe for Discord rate limits (5 requests per 5 seconds)
STREAM_CHUNK_INTERVAL=1.1

# Maximum chunk size (characters)
MAX_STREAM_CHUNK_SIZE=1900  # Discord message limit is 2000
```

#### File Upload Configuration

```bash
# Maximum file upload size (MB)
MAX_FILE_SIZE_MB=10

# How long to keep generated artifacts (hours)
ARTIFACT_TTL_HOURS=12

# How long to keep uploaded files (hours)
UPLOAD_CLEANUP_HOURS=1
```

#### Maintenance Mode

```bash
# Soft maintenance - still queues new requests
MAINTENANCE_MODE=false

# Hard maintenance - rejects all new requests
MAINTENANCE_MODE_HARD=false
```

### Model Configuration

Model assignments are configured in `fastapi-service/app/config.py`. You can modify which models are used for each route:

```python
# Router Settings (in config.py)
ROUTER_MODEL = "gpt-oss:20b"           # Classifies user queries
MATH_MODEL = "rnj-1:8b"                # Math problem solving
SIMPLE_CODER_MODEL = "rnj-1:8b"        # Simple code generation
COMPLEX_CODER_MODEL = "deepcoder:14b"  # Complex system design
REASONING_MODEL = "magistral:24b"      # Analysis and reasoning
RESEARCH_MODEL = "magistral:24b"       # Research with web search
OCR_MODEL = "qwen3-vl:8b"              # Image/vision analysis
OLLAMA_SUMMARIZATION_MODEL = "gpt-oss:20b"  # Conversation summarization
```

#### Model Capabilities Matrix

| Model | Size | Tools | Thinking | Vision | Best For |
|-------|------|-------|----------|--------|----------|
| gpt-oss:20b | 14GB | ✅ | ✅ (level) | ❌ | General chat, routing |
| rnj-1:8b | 5GB | ✅ | ❌ | ❌ | Math, simple code |
| deepcoder:14b | 9GB | ❌ | ❌ | ❌ | Complex code |
| magistral:24b | 15GB | ✅ | ✅ (boolean) | ❌ | Reasoning, research |
| qwen3-vl:8b | 5GB | ✅ | ✅ | ✅ | OCR, image analysis |

#### Adding New Models

1. Pull the model with Ollama:
   ```bash
   ollama pull model-name:tag
   ```

2. Add to `AVAILABLE_MODELS` in `config.py`:
   ```python
   ModelCapabilities(
       name="model-name:tag",
       supports_tools=True,      # Can use web_search, fetch_webpage
       supports_thinking=True,   # Supports chain-of-thought
       supports_vision=False,    # Can process images
       thinking_format="boolean" # "boolean" or "level"
   )
   ```

3. Update route model assignment (e.g., `REASONING_MODEL = "model-name:tag"`)

4. Restart FastAPI service:
   ```bash
   docker-compose restart fastapi-service
   ```

### Docker Configuration

#### Service Ports

| Service | External Port | Internal Port | Purpose |
|---------|--------------|---------------|---------|
| FastAPI | 8001 | 8000 | Main API, WebSocket |
| DynamoDB | 8000 | 8000 | Local database |
| Logging | 9999 | 9999 | Log collection |
| Logging Health | 9998 | 9998 | Health endpoint |
| Discord Bot Health | 9997 | 9998 | Health endpoint |
| Monitoring Dashboard | 8080 | 8080 | Web UI |

#### Volume Mounts

- `./logs` → `/app/logs` - Shared log directory
- `./monitoring-service/data` → `/app/data` - Monitoring database
- `temp-files` - Temporary file storage (Docker volume)

#### Service Dependencies

Services start in this order:
```
logging-service (base)
    ↓
dynamodb-local (base)
    ↓
fastapi-service (depends on dynamodb, logging)
    ↓
discord-bot (depends on fastapi, logging)

monitoring-service (independent, only depends on logging)
```

## Using the Bot

### Discord Commands

#### Slash Commands

- `/help` - Show bot usage instructions
- `/reset` - Clear conversation history in current thread
- `/summarize` - Manually trigger conversation summarization
- `/close` - Close thread and delete conversation history

#### Mentioning the Bot

```
@YourBot your message here
```

The bot will create a thread for the conversation and respond there.

### Features in Action

#### Automatic Routing

The bot automatically detects query type and routes to the best model:

**Math Query** → rnj-1:8b
```
You: @Bot solve ∫ x² dx

Bot: Let me solve this integral step by step.

**Step-by-Step Breakdown:**
1. Apply power rule: ∫ xⁿ dx = xⁿ⁺¹/(n+1)
2. For x²: n = 2
3. Result: x³/3 = ⅓x³

**Final Answer:**
∫ x² dx = ⅓x³ + C
```

**Code Request** → rnj-1:8b
```
You: @Bot write a Python function to check if a number is prime

Bot: Here's a prime number checker:

[Bot generates and saves code as artifact]
✅ Artifact saved: prime_checker.py
```

**Research Question** → magistral:24b (with web search)
```
You: @Bot research the latest quantum computing breakthroughs

Bot: *Searching the web...*
*Analyzing results...*

Based on recent developments:
1. [Information from web searches]
2. [Citations included]
...
```

#### File Uploads

Upload images for analysis:

```
You: [uploads screenshot] @Bot what does this error mean?

Bot: *Analyzing image with OCR...*
The error message shows: [extracted text]
This error typically means: [explanation]
```

Supported file types:
- Images: PNG, JPEG, WebP, GIF
- Documents: PDF, text files, markdown
- Code files: .py, .js, .java, .cpp, etc.

#### Artifact Generation

When you request code or documents, the bot automatically saves them:

```
You: @Bot create a markdown guide for Docker

Bot: [Generates comprehensive Docker guide]

✅ Artifact saved: docker_guide.md
[Download link provided]
```

Artifacts are automatically detected when you use phrases like:
- "create a file..."
- "write [content] to a file..."
- "save as .py"
- "generate a markdown..."

#### Web Search

Research and reasoning routes automatically use web search when needed:

```
You: @Bot what's the current price of Bitcoin?

Bot: *Using web_search for current information...*
According to recent data: [answer with sources]
```

You can explicitly request web search:
```
You: @Bot search for the latest Python release notes
```

#### Request Cancellation

Cancel long-running requests using the slash command:
```
/cancel
```

Or simply ask:
```
You: cancel that request
```

### Thread-Based Conversations

- Each conversation happens in its own Discord thread
- Conversation history is maintained per thread
- Threads auto-archive after inactivity
- Use `/reset` to clear history without closing thread
- Use `/close` to close thread and delete all history

## Deployment & Operations

### Starting Services

```bash
# Start all services (builds if needed)
docker-compose up --build

# Start in background
docker-compose up --build -d

# Start specific service
docker-compose up fastapi-service

# Rebuild specific service
docker-compose build --no-cache fastapi-service
docker-compose restart fastapi-service
```

### Viewing Logs

#### Real-time logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f fastapi-service
docker-compose logs -f discord-bot

# Last N lines
docker-compose logs --tail=50 fastapi-service
```

#### Log files

Logs are stored in `./logs/YYYY-MM-DD/`:
- `app.log` - INFO level application logs
- `error.log` - ERROR level logs
- `debug.log` - DEBUG level logs

```bash
# View today's application logs
tail -f logs/$(date +%Y-%m-%d)/app.log

# View errors
tail -f logs/$(date +%Y-%m-%d)/error.log
```

### Health Monitoring

#### FastAPI Health Endpoint

```bash
# Check service health
curl http://localhost:8001/health | jq

# Check specific component
curl http://localhost:8001/health | jq '.components.ollama'
```

#### Monitoring Dashboard

Open http://localhost:8080 in browser for:
- Service health status
- 24-hour uptime metrics
- Alert history
- Database statistics
- Log cleanup status

#### Health Check Endpoints

- FastAPI: http://localhost:8001/health
- Logging: http://localhost:9998/health
- Discord Bot: http://localhost:9997/health
- Monitoring: http://localhost:8080/health

### Restarting Services

```bash
# Restart single service
docker-compose restart fastapi-service
docker-compose restart discord-bot

# Restart all services
docker-compose restart

# Stop and start (full restart)
docker-compose down
docker-compose up -d
```

### Database Management

#### DynamoDB Local

The system uses DynamoDB Local (runs in Docker):
- Endpoint: http://localhost:8000
- Tables: Conversations, Users, ThreadMessages, Tokens, Sessions, Artifacts, Preferences
- Data: In-memory (lost on container restart, can be persisted if needed)

#### Reset Database

```bash
# Stop services and remove volumes (DELETES ALL DATA)
docker-compose down -v

# Restart (creates fresh database)
docker-compose up -d
```

#### View Database Contents

```bash
# Install AWS CLI if needed
pip install awscli

# List tables
aws dynamodb list-tables \
  --endpoint-url http://localhost:8000 \
  --region us-east-1

# Query conversations
aws dynamodb scan \
  --table-name Conversations \
  --endpoint-url http://localhost:8000 \
  --region us-east-1
```

### Maintenance Mode

#### Soft Maintenance

Queues new requests but still processes them:

```bash
# In .env
MAINTENANCE_MODE=true
```

Users see: "🔧 Bot is under maintenance. Your request has been queued."

#### Hard Maintenance

Rejects all new requests:

```bash
# In .env
MAINTENANCE_MODE_HARD=true
```

Users see: "🚫 Bot is under emergency maintenance. Please try again later."

Apply changes:
```bash
docker-compose restart fastapi-service
```

## Troubleshooting

### Common Issues

#### Bot Not Responding

**Symptom**: Bot shows online but doesn't respond to messages

**Checks**:
1. WebSocket connection status:
   ```bash
   curl http://localhost:9997/health
   # Should show: websocket_connected: true
   ```

2. FastAPI service health:
   ```bash
   curl http://localhost:8001/health
   ```

3. Discord bot logs:
   ```bash
   docker-compose logs --tail=50 discord-bot
   ```

**Solutions**:
- Restart Discord bot: `docker-compose restart discord-bot`
- Check Discord token is valid in `.env`
- Verify bot has Message Content Intent enabled

#### Ollama Connection Failures

**Symptom**: Errors like "Failed to connect to Ollama" or "model not found"

**Checks**:
1. Ollama is running on host:
   ```bash
   curl http://localhost:11434/api/tags
   ```

2. Models are pulled:
   ```bash
   ollama list
   ```

3. OLLAMA_HOST is correct in `.env`:
   - Mac/Windows: `http://host.docker.internal:11434`
   - Linux: `http://172.17.0.1:11434` or `http://host.docker.internal:11434`

**Solutions**:
- Start Ollama: `ollama serve`
- Pull missing models: `ollama pull gpt-oss:20b`
- Verify host networking: `docker run --rm curlimages/curl http://host.docker.internal:11434/api/tags`

#### Queue Full Errors

**Symptom**: "Queue is full" errors

**Checks**:
```bash
# Check queue stats
curl http://localhost:8001/api/admin/queue/stats
```

**Solutions**:
- Increase MAX_QUEUE_SIZE in `.env`
- Check if requests are stuck (long VISIBILITY_TIMEOUT)
- Restart FastAPI service to clear queue

#### Token Budget Exceeded

**Symptom**: "Weekly token budget exceeded"

**Checks**:
```bash
# Check user's token usage
curl http://localhost:8001/api/user/{user_id}
```

**Solutions**:
- Disable budgets: Set `DISABLE_TOKEN_BUDGET=true` in `.env`
- Grant bonus tokens via admin API
- Wait for weekly reset (Mondays)

#### Model Not Found

**Symptom**: "Model not available" errors

**Checks**:
```bash
# List available models
ollama list

# Check model is in AVAILABLE_MODELS (config.py)
docker-compose exec fastapi-service python -c "from app.config import settings; print(settings.AVAILABLE_MODELS)"
```

**Solutions**:
- Pull missing model: `ollama pull model-name:tag`
- Add model to AVAILABLE_MODELS in `config.py`
- Restart FastAPI service

### Log Locations

- **Container logs**: `docker-compose logs [service-name]`
- **Application logs**: `./logs/YYYY-MM-DD/app.log`
- **Error logs**: `./logs/YYYY-MM-DD/error.log`
- **Debug logs**: `./logs/YYYY-MM-DD/debug.log`

### Discord Bot Permissions

Required Discord bot permissions:
- **Intents** (Developer Portal → Bot → Privileged Gateway Intents):
  - Message Content Intent ✅
  - Server Members Intent ✅
- **Bot Permissions** (Invite URL):
  - Read Messages/View Channels
  - Send Messages
  - Send Messages in Threads
  - Create Public Threads
  - Manage Threads
  - Embed Links
  - Attach Files
  - Read Message History
  - Add Reactions

Generate invite URL:
```
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=326417685504&scope=bot%20applications.commands
```

## Development

### Project Structure

```
discord-ollama-agent/
├── docker-compose.yml          # Service orchestration
├── .env.example                # Environment template
├── .env                        # Your config (not in git)
│
├── fastapi-service/            # Main API service
│   ├── app/
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── config.py           # Configuration & settings
│   │   ├── dependencies.py     # Dependency injection
│   │   │
│   │   ├── interfaces/         # Abstract interfaces (SOLID)
│   │   ├── implementations/    # Concrete implementations
│   │   │   ├── strands_llm.py  # LLM interface via Strands
│   │   │   └── ...
│   │   │
│   │   ├── services/           # Business logic
│   │   │   ├── orchestrator.py # Main coordinator
│   │   │   ├── router_service.py # Intelligent routing
│   │   │   ├── queue_worker.py # Background processor
│   │   │   └── ...
│   │   │
│   │   ├── routing/            # Routing system
│   │   │   ├── router.py       # Route classification
│   │   │   ├── route_handler.py # Route config
│   │   │   └── route.py        # Route definitions
│   │   │
│   │   ├── prompts/            # Prompt management
│   │   │   ├── composer.py     # Prompt composition
│   │   │   ├── registry.py     # Prompt loading
│   │   │   ├── routes/         # Route prompts
│   │   │   ├── layers/         # Prompt layers
│   │   │   └── ...
│   │   │
│   │   ├── streaming/          # Streaming components
│   │   ├── strategies/         # Strategy patterns
│   │   ├── models/             # Pydantic models
│   │   ├── api/                # API routers
│   │   └── utils/              # Utilities
│   │
│   ├── tests/                  # Test suite
│   └── Dockerfile
│
├── discord-bot/                # Discord client
│   ├── bot/
│   │   ├── main.py             # Bot entry point
│   │   ├── client.py           # Discord client
│   │   └── message_handler.py  # Message processing
│   └── Dockerfile
│
├── monitoring-service/         # Health & monitoring
│   ├── monitor.py              # FastAPI dashboard
│   ├── database.py             # SQLite for metrics
│   ├── health_checker.py       # Service health checks
│   └── alerts.py               # Alert management
│
├── logging-service/            # Centralized logging
│   ├── server.py               # TCP log server
│   └── Dockerfile
│
├── shared/                     # Shared utilities
│   ├── log_config.py           # Logging setup
│   ├── logging_client.py       # Log client
│   └── health_server.py        # Health endpoints
│
├── scripts/                    # Utility scripts
│   ├── sync_commands.py        # Discord command sync
│   └── run-tests.sh            # Test runner
│
└── logs/                       # Application logs
    └── YYYY-MM-DD/             # Date-partitioned
```

### Running Tests

```bash
# FastAPI service tests
cd fastapi-service
python -m pytest

# With coverage
python -m pytest --cov=app tests/

# Discord bot tests
cd discord-bot
python -m pytest

# Run all tests via Docker
./scripts/run-tests.sh
```

See [fastapi-service/tests/TESTING.md](fastapi-service/tests/TESTING.md) for detailed testing documentation.

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `pytest`
5. Commit changes: `git commit -m 'Add amazing feature'`
6. Push to branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Utility Scripts

See [scripts/README.md](scripts/README.md) for documentation on utility scripts:
- `sync_commands.py` - Sync Discord slash commands
- `run-tests.sh` - Run test suite
- `test_token.py` - Test Discord token

### Code Style

- Python 3.11+
- Type hints required
- Black formatter
- Pydantic v2 for data validation
- Async/await for I/O operations

## Technical Documentation

For in-depth technical documentation, see [TECHNICAL.md](TECHNICAL.md):
- Detailed architecture overview
- Unique implementation details (routing, artifacts, streaming)
- End-to-end flow diagrams
- Component reference
- Infrastructure & DevOps
- LLM expert analysis and rating

## Additional Resources

- **Model Tool Support**: [fastapi-service/MODEL-TOOL-SUPPORT.md](fastapi-service/MODEL-TOOL-SUPPORT.md)
- **Testing Guide**: [fastapi-service/tests/TESTING.md](fastapi-service/tests/TESTING.md)
- **Scripts Documentation**: [scripts/README.md](scripts/README.md)
- **Archived Docs**: [archive/docs/](archive/docs/)

## License

MIT

## Support

For issues, questions, or feature requests:
1. Check existing GitHub issues
2. Review troubleshooting section above
3. Check logs for errors
4. Open a new GitHub issue with:
   - Detailed description
   - Steps to reproduce
   - Relevant logs
   - Environment details (OS, Docker version, etc.)

---

**Built with**: FastAPI, Discord.py, Strands AI, Ollama, DynamoDB, Docker

**Status**: Production-ready with active development
