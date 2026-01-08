# Discord-Trollama Agent

A production-grade Discord bot that intelligently routes user messages to specialized local Ollama language models, providing an AI assistant experience with thread-based conversations, automatic context management, and artifact generation.

## What is this?

This system connects Discord users to locally-hosted LLMs (via Ollama) through an intelligent routing system that automatically selects the best model for each task. Whether you're asking a math question, requesting code generation, or conducting research, the bot routes your query to a specialized model optimized for that specific task type.

**Key Innovation**: Instead of using one model for everything, the system uses LLM-based semantic routing to classify queries and assign them to specialized models, resulting in better quality responses at faster speeds.

## Key Features

- **Intelligent Routing** - Automatically classifies queries and routes to specialized models (profile-dependent):
  - Math problems → rnj-1:8b (optimized for mathematical reasoning)
  - Simple code → rnj-1:8b (fast function/algorithm generation)
  - Complex code → ministral-3:14b (conservative) | gpt-oss-120b-eagle3 (performance) | gpt-oss:120b (balanced)
  - Reasoning → gpt-oss:20b (conservative) | gpt-oss-120b-eagle3 (performance) | gpt-oss:120b (balanced)
  - Research → gpt-oss:20b (conservative) | gpt-oss-120b-eagle3 (performance) | gpt-oss:120b (balanced)
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

- **🧠 Intelligent VRAM Management** - Production-grade memory orchestration for unified memory systems:
  - **Proactive PSI-Based Eviction** - Monitors Linux Pressure Stall Information (PSI) to prevent OOM kills before they happen
  - **Circuit Breaker Pattern** - Prevents model crash loops by creating safety buffers (20GB) for unstable models
  - **Priority-Weighted LRU** - Smart eviction that protects critical models (router) while evicting least-used models
  - **Multi-Backend Support** - Extensible architecture for Ollama, SGLang, TensorRT-LLM, and vLLM
  - **Registry Reconciliation** - Auto-detects external model kills every 30 seconds and syncs state
  - **Automatic Recovery** - Self-healing system that cleans up after OOM events

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
└──────┬──────────────────────────────┬─────────────────┬──────────┘
       │                              │                 │
       ↓                              ↓                 ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  DynamoDB    │  │ Auth Service │  │   Ollama     │  │   SGLang     │
│  Local       │  │  (JWT Auth)  │  │   (Host)     │  │  (Optional)  │
│              │  │              │  │              │  │              │
│ - users      │  │ - Login      │  │ - Models     │  │ - Eagle3     │
│ - auth_methods│ │ - Register   │  │ - Inference  │  │ - Speculative│
│ - conversations│ │ - Link Auth  │  │              │  │   Decoding   │
│ - webpage_chunks│ │ - Password   │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
       │                  │
       └──────┬───────────┘
              ↓
     ┌────────────────┐
     │  Streamlit UI  │
     │ (Web Interface)│
     │                │
     │ - Chat         │
     │ - Login        │
     │ - Settings     │
     └────────────────┘

Supporting Services:
- **Auth Service**: SOLID-compliant authentication with JWT, bcrypt, account linking
- **Streamlit UI**: Web-based chat interface with authentication
- **Logging Service**: Centralized log collection
- **Monitoring Service**: Health dashboard + alerts
- **VRAM Orchestrator**: Intelligent memory management with PSI monitoring
- **SGLang Server** (128GB systems): High-performance inference with EAGLE3 speculative decoding
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

> **Note**: This project uses a split docker-compose architecture with separate files for infrastructure and application services. See [DOCKER_ARCHITECTURE.md](DOCKER_ARCHITECTURE.md) for details.

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
ollama pull gpt-oss:20b          # Router + general chat (13GB)
ollama pull rnj-1:8b             # Math + simple code (5.1GB)
ollama pull ministral-3:14b      # Complex code + vision (9.1GB)
ollama pull deepseek-ocr:3b      # OCR/vision analysis (6.7GB)
ollama pull qwen3-embedding:4b   # Text embeddings (2.5GB)
```

**Note**: Models will download to `~/.ollama/models` and can be shared across projects.

#### 2b. Set Up SGLang Eagle3 (Optional - 128GB Systems Only)

For systems with 128GB+ VRAM using the performance profile, you can enable high-performance inference with NVIDIA GPT-OSS 120B + EAGLE3 speculative decoding (1.6-1.8× speedup):

```bash
# Install HuggingFace CLI
uv tool install huggingface-hub

# Download base model (~196GB, pre-quantized MXFP4)
hf download openai/gpt-oss-120b

# Download EAGLE3 draft model (~1.7GB)
hf download lmsys/EAGLE3-gpt-oss-120b-bf16
```

**How it works**:
- Models download to `~/.cache/huggingface/hub/` (~198GB total)
- Model ships **pre-quantized in MXFP4 format** (no runtime quantization)
- Startup: ~4-5 minutes for MoE weight shuffling (every restart)
- VRAM usage: ~80-90GB (model + KV cache + overhead)
- Eagle3 provides 55-70 tok/s vs 35-40 tok/s baseline
- Automatically used for research/reasoning/complex code routes

**Requirements**:
- 128GB VRAM system (NVIDIA Grace Blackwell recommended)
- `VRAM_PROFILE=performance` in `.env`
- ~200GB disk space for models
- SGLang service will start automatically with `docker-compose up`

**Note**: SGLang Eagle3 is completely optional. Conservative profile (16-32GB systems) uses Ollama-only models. Balanced profile (128GB systems) uses Ollama gpt-oss:120b without SGLang.

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
3. `auth-service` (port 8002) - Authentication
4. `admin-service` (port 8003) - Admin API
5. `fastapi-service` (port 8001) - Main API
6. `discord-bot` (port 9997) - Discord connection

**Log Rotation** (Automatic):
All services are configured with log rotation to prevent disk space issues:
- Max log file size: 10MB per file
- Max log files: 3 files per service
- Total max logs per service: ~30MB
- Logs automatically rotate and old files are deleted
- No manual cleanup required

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

#### SGLang Configuration (Optional - 128GB Systems)

```bash
# SGLang server endpoint for high-performance inference
# Used for gpt-oss-120b-eagle3 model (performance profile only)
SGLANG_ENDPOINT=http://sglang-server:30000
```

**When to use**:
- Enable for 128GB+ systems with performance profile
- Provides 1.6-1.8× speedup via EAGLE3 speculative decoding
- Uses gpt-oss-120b-eagle3 for ALL text tasks (simple/complex code, reasoning, research, math)
- SGLang service starts with `docker-compose up` (MoE weight shuffling ~4-5 min every restart, then 82GB usage)

#### Auth Service Configuration

```bash
# JWT secret key for session tokens
# IMPORTANT: Change this in production!
JWT_SECRET_KEY=change-me-in-production-use-a-long-random-string

# JWT token expiration (hours)
JWT_EXPIRATION_HOURS=8

# DynamoDB connection (shared with FastAPI)
DYNAMODB_ENDPOINT=http://dynamodb-local:8000
DYNAMODB_REGION=us-east-1
DYNAMODB_ACCESS_KEY=test
DYNAMODB_SECRET_KEY=test

# Logging service connection
LOGGING_HOST=logging-service
LOGGING_PORT=9999
```

**Features**:
- **SOLID-Compliant Architecture**: Follows all five SOLID principles for maintainability
- **Unified User Model**: Separate User (profile) and AuthMethod (credentials) entities
- **Multiple Auth Providers**: Password-based authentication with extensible provider pattern
- **Account Linking**: Users can link multiple authentication methods (future: Discord, Google, GitHub)
- **JWT Sessions**: Secure session management with bcrypt password hashing
- **DynamoDB Storage**: Uses `users` and `auth_methods` tables

**Endpoints**:
- `POST /login` - Authenticate with username/password
- `POST /register` - Register new user account
- `POST /link-auth-method` - Link additional auth method to existing account
- `GET /health` - Health check

**Setup Admin User**:
```bash
cd auth-service
uv run python setup_admin.py --username admin --password <secure-password> --display "Admin User" --email admin@example.com
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

#### VRAM Orchestrator Configuration

The VRAM orchestrator provides intelligent memory management for unified memory systems (like NVIDIA Grace Blackwell). It prevents out-of-memory (OOM) kills and optimizes model loading/unloading.

```bash
# Enable VRAM orchestration (recommended for production)
VRAM_ENABLE_ORCHESTRATOR=true

# Configuration Profile - Environment-aware model roster and VRAM limits
# "conservative" = 16-32GB systems (5 small Ollama models, 14GB limit)
# "performance" = 128GB systems (SGLang Eagle3 for all text, minimal Ollama, 12GB Ollama limit)
# "balanced" = 128GB systems (full Ollama zoo including gpt-oss:120b, 110GB limit)
VRAM_PROFILE=performance

# Legacy: Conservative mode (force-unload after each request)
# Keep false for performance/balanced profiles, set true for 16GB systems if not using profiles
VRAM_CONSERVATIVE_MODE=false

# PSI-Based Proactive Eviction (prevents earlyoom kills)
# PSI (Pressure Stall Information) is a Linux kernel metric for memory pressure
VRAM_PSI_WARNING_THRESHOLD=10.0   # PSI full_avg10 > 10% - evict LOW priority models
VRAM_PSI_CRITICAL_THRESHOLD=15.0  # PSI full_avg10 > 15% - evict NORMAL priority models

# Circuit Breaker (prevents crash loops)
VRAM_CIRCUIT_BREAKER_ENABLED=true  # Enable circuit breaker pattern
VRAM_CRASH_THRESHOLD=2             # Number of crashes to trigger protection
VRAM_CRASH_WINDOW_SECONDS=300      # Time window for crash tracking (5 minutes)
VRAM_CIRCUIT_BREAKER_BUFFER_GB=20.0  # Extra safety buffer when circuit breaker triggers
```

**How It Works**:
- **Configuration Profiles**: System loads environment-specific settings at startup. Performance profile (128GB) uses SGLang Eagle3 for all text tasks. Balanced profile (128GB) includes full 10-model Ollama zoo. Conservative profile (16-32GB) only includes 5 small models. VRAM limits, model priorities, and router assignments are all profile-aware.
- **PSI Monitoring**: System monitors Linux PSI metrics every 30 seconds. When PSI exceeds thresholds, proactively evicts models before OOM killer strikes.
- **Circuit Breaker**: If a model crashes 2+ times in 5 minutes, the system proactively evicts other models to create a 20GB safety buffer before reloading the problematic model.
- **Priority System**: Models have priorities (CRITICAL > HIGH > NORMAL > LOW). gpt-oss-120b-eagle3 is CRITICAL (performance profile, never evict). Router models are HIGH. User-facing models evict in LRU order.
- **Reconciliation**: Every 30 seconds, the system checks if loaded models match what's actually running. If external OOM kills happened, it auto-cleans the registry.

**Profiles Comparison**:

| Profile | Strategy | Available Models | VRAM Limits | Total VRAM | Best For |
|---------|----------|-----------------|-------------|------------|----------|
| **conservative** | Small Ollama models | 5 models (<20GB each) | Soft: 12GB, Hard: 14GB | 16-32GB | 16-32GB systems, laptops |
| **performance** | SGLang Eagle3 + minimal Ollama | 3 models (84GB Eagle3 + 2 Ollama) | SGLang: 84GB, Ollama Soft: 10GB, Hard: 12GB | 119GB | 128GB+ systems, maximum speed |
| **balanced** | Full Ollama zoo | 10+ models (includes gpt-oss:120b) | Soft: 100GB, Hard: 110GB | 119GB | 128GB+ systems, model variety |

**Conservative Profile Models** (Ollama only):
- gpt-oss:20b (13.0GB) - Router + general chat
- rnj-1:8b (5.1GB) - Math + simple code
- ministral-3:14b (9.1GB) - Complex code + vision
- deepseek-ocr:3b (6.7GB) - OCR/vision
- qwen3-embedding:4b (2.5GB) - Text embeddings

**Performance Profile Models** (SGLang + minimal Ollama):
- gpt-oss-120b-eagle3 (84GB, SGLang) - ALL text tasks (code/reasoning/research/math) with 1.6-1.8× speedup
- ministral-3:14b (9.1GB, Ollama) - Vision tasks
- qwen3-embedding:4b (2.5GB, Ollama) - Text embeddings

**Balanced Profile Models** (Ollama only):
- All conservative models PLUS:
- gpt-oss:120b (76GB) - Complex code/reasoning/research (no EAGLE3)
- devstral-2:123b (74GB) - Expert code generation
- deepseek-r1:70b (42GB) - Deep reasoning
- devstral-small-2:24b (15GB) - Mid-tier code
- nemotron-3-nano:30b (24GB) - General purpose

**When to Tune**:
- **16-32GB Systems**: Use `VRAM_PROFILE=conservative`. Router stays loaded with HIGH priority. Large models (120B, 70B) are not available.
- **128GB+ Systems (Speed Priority)**: Use `VRAM_PROFILE=performance` (default). SGLang Eagle3 handles all text tasks with 1.6-1.8× speedup. Minimal model orchestration needed.
- **128GB+ Systems (Model Variety)**: Use `VRAM_PROFILE=balanced`. Full Ollama model zoo available, orchestrator manages eviction intelligently.
- **Frequent OOM Events**: Lower PSI thresholds (e.g., `VRAM_PSI_WARNING_THRESHOLD=5.0`) for more aggressive eviction, or switch to conservative profile.
- **Stable Systems**: Increase thresholds or disable orchestrator (`VRAM_ENABLE_ORCHESTRATOR=false`) if you have abundant memory and no OOM issues.

**Note**: When orchestrator is disabled, models are loaded on-demand without proactive memory management. This works well for systems with >256GB RAM or when running only a few small models. For production systems with limited memory, keeping orchestrator enabled is strongly recommended.

### Model Configuration

> **Note**: Model rosters and assignments are now **profile-based**. The `VRAM_PROFILE` environment variable determines which models are available and which models are used for each route. This ensures environment-aware configuration (16-32GB vs 128GB systems).

#### Profile-Based Model Assignments

Model assignments are automatically configured based on your active profile:

**Performance Profile** (`VRAM_PROFILE=performance`):
```python
# ALL text routes use gpt-oss-120b-eagle3 (SGLang)
ROUTER_MODEL = "gpt-oss-120b-eagle3"        # Classifies user queries
MATH_MODEL = "gpt-oss-120b-eagle3"          # Math problem solving
SIMPLE_CODER_MODEL = "gpt-oss-120b-eagle3"  # Simple code generation
COMPLEX_CODER_MODEL = "gpt-oss-120b-eagle3" # Complex system design
REASONING_MODEL = "gpt-oss-120b-eagle3"     # Analysis and reasoning
RESEARCH_MODEL = "gpt-oss-120b-eagle3"      # Research with web search

# Specialized tasks use Ollama
VISION_MODEL = "ministral-3:14b"            # Vision/OCR tasks
EMBEDDING_MODEL = "qwen3-embedding:4b"      # Text embeddings
SUMMARIZATION_MODEL = "gpt-oss-120b-eagle3" # Conversation summarization (Eagle3)
POST_PROCESSING_MODEL = "ministral-3:14b"   # Output artifact post-processing
```

**Note**: `gpt-oss-120b-eagle3` is served by SGLang with EAGLE3 speculative decoding. The model is pre-quantized in MXFP4 format for optimal performance on Blackwell GPUs, providing 1.6-1.8× speedup (55-70 tok/s vs 35-40 tok/s). Container startup takes ~4-5 minutes for MoE weight shuffling, then uses 82GB steady-state (40K context).

**Balanced Profile** (`VRAM_PROFILE=balanced`):
```python
ROUTER_MODEL = "gpt-oss:20b"           # Classifies user queries
MATH_MODEL = "gpt-oss:120b"            # Math with full 120B power (Ollama)
SIMPLE_CODER_MODEL = "rnj-1:8b"        # Simple code generation
COMPLEX_CODER_MODEL = "gpt-oss:120b"   # Complex code (Ollama 120B)
REASONING_MODEL = "gpt-oss:120b"       # Analysis and reasoning (Ollama)
RESEARCH_MODEL = "gpt-oss:120b"        # Research with web search

# Specialized tasks
VISION_MODEL = "ministral-3:14b"       # Vision/OCR tasks
EMBEDDING_MODEL = "qwen3-embedding:4b" # Text embeddings
SUMMARIZATION_MODEL = "gpt-oss:20b"    # Conversation summarization
POST_PROCESSING_MODEL = "ministral-3:14b"  # Output artifact post-processing
```

**Note**: Balanced profile uses gpt-oss:120b from Ollama (76GB GGUF, no EAGLE3). Provides full 120B model quality with model variety (10+ models available). Slower than performance profile but more flexible.

**Conservative Profile** (`VRAM_PROFILE=conservative`):
```python
ROUTER_MODEL = "gpt-oss:20b"           # Classifies user queries
MATH_MODEL = "rnj-1:8b"                # Math problem solving
SIMPLE_CODER_MODEL = "rnj-1:8b"        # Simple code generation
COMPLEX_CODER_MODEL = "ministral-3:14b"  # Complex code (best available in 16-32GB)
REASONING_MODEL = "gpt-oss:20b"        # Fallback to router (no 120B models)
RESEARCH_MODEL = "gpt-oss:20b"         # Fallback to router

# Specialized tasks
VISION_MODEL = "ministral-3:14b"       # Vision/OCR tasks
EMBEDDING_MODEL = "qwen3-embedding:4b" # Text embeddings
SUMMARIZATION_MODEL = "gpt-oss:20b"    # Conversation summarization
POST_PROCESSING_MODEL = "ministral-3:14b"  # Output artifact post-processing
```

> **Graceful Degradation**: Conservative profile automatically falls back to the best available model when specialized models are too large. For example, `COMPLEX_CODER_MODEL` uses `ministral-3:14b` instead of the 120B model.

#### Model Capabilities Matrix

| Model | Size | Backend | Tools | Thinking | Vision | Best For | Profiles |
|-------|------|---------|-------|----------|--------|----------|----------|
| gpt-oss:20b | 13GB | Ollama | ✅ | ✅ (level) | ❌ | General chat, routing | All |
| gpt-oss-120b-eagle3 | 84GB | SGLang | ✅ | ❌ | ❌ | ALL text tasks with 1.6-1.8× speedup | Performance |
| gpt-oss:120b | 76GB | Ollama | ✅ | ✅ (level) | ❌ | Complex code/reasoning (no EAGLE3) | Balanced |
| rnj-1:8b | 5.1GB | Ollama | ✅ | ❌ | ❌ | Math, simple code | All |
| ministral-3:14b | 9.1GB | Ollama | ✅ | ❌ | ✅ | Vision + complex code | All |
| deepseek-ocr:3b | 6.7GB | Ollama | ❌ | ❌ | ✅ | OCR, image analysis | All |
| devstral-2:123b | 74GB | Ollama | ✅ | ❌ | ❌ | Expert code generation | Balanced |
| deepseek-r1:70b | 42GB | Ollama | ❌ | ✅ (boolean) | ❌ | Deep reasoning | Balanced |
| qwen3-embedding:4b | 2.5GB | Ollama | ❌ | ❌ | ❌ | Text embeddings | All |

**Note**: Tools and thinking are handled by Strands framework, not directly by Eagle3 model.

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
| SGLang (Optional) | 30000 | 30000 | High-performance inference (128GB systems) |
| DynamoDB | 8000 | 8000 | Local database |
| Logging | 9999 | 9999 | Log collection |
| Logging Health | 9998 | 9998 | Health endpoint |
| Discord Bot Health | 9997 | 9998 | Health endpoint |
#### Volume Mounts

- `./logs` → `/app/logs` - Shared log directory
- `temp-files` - Temporary file storage (Docker volume)
- `~/.cache/huggingface` → `/root/.cache/huggingface` (SGLang only) - HuggingFace model cache

#### Service Dependencies

Services start in this order:
```
Infrastructure (always-on):
logging-service (base)
    ↓
dynamodb-local + auth-service + admin-service
    ↓
web-service (admin dashboard)

Application (can be stopped/started):
sglang-server (optional, 128GB systems)
    ↓
fastapi-service (depends on dynamodb, logging, sglang)
    ↓
discord-bot (depends on fastapi, logging)
```

**Note**: FastAPI waits for SGLang health check when using performance profile. SGLang startup takes ~4-5 minutes for MoE weight shuffling on every container restart.

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

**Research Question** → gpt-oss:20b (conservative) | gpt-oss-120b-eagle3 (performance) | gpt-oss:120b (balanced) with web search
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

> **Architecture Note**: This project uses a split docker-compose architecture:
> - `docker-compose.infra.yml` - Infrastructure services (admin, auth, web, logging, dynamodb) - always-on
> - `docker-compose.app.yml` - Application services (fastapi, discord-bot, sglang) - toggleable
>
> See [DOCKER_ARCHITECTURE.md](DOCKER_ARCHITECTURE.md) for full details.

### Starting Services

```bash
# Recommended: Use the start script (handles profiles and SGLang)
./start.sh

# Manual: Start all services (infrastructure + application)
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up -d --build

# With performance profile (includes SGLang)
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml --profile performance up -d --build

# Start specific service
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up fastapi-service

# Rebuild specific service
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml build --no-cache fastapi-service
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml restart fastapi-service
```

### Stopping Services

```bash
# Recommended: Stop application services only (keeps admin dashboard running)
./stop.sh

# Stop everything (infrastructure + application)
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml down
```

### Viewing Logs

#### Real-time logs

```bash
# All services (infrastructure + application)
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml logs -f

# Only application services
docker compose -f docker-compose.app.yml logs -f

# Specific service
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml logs -f fastapi-service
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml logs -f discord-bot

# Last N lines
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml logs --tail=50 fastapi-service
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

**Main Health Check** (FastAPI): http://localhost:8001/health

The main health endpoint now includes VRAM orchestrator status:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-19T10:45:23Z",
  "services": {
    "dynamodb": true,
    "ollama": true,
    "model_loaded": true
  },
  "vram": {
    "healthy": true,
    "usage_pct": 74.5,
    "available_gb": 32.7,
    "psi_full_avg10": 3.4,
    "loaded_models": 3
  },
  "queue_size": 0,
  "websocket_connections": 5
}
```

**Health Thresholds**:
- **Healthy**: usage < 90% AND PSI some < 50% AND PSI full < 15%
- **Warning**: usage > 80% OR PSI some > 20% OR PSI full > 5%
- **Unhealthy**: Any service down OR usage > 95%

**Other Service Health Endpoints**:
- Logging: http://localhost:9998/health
- Discord Bot: http://localhost:9997/health
- Monitoring: http://localhost:8080/health

#### VRAM Orchestrator API

The VRAM orchestrator exposes monitoring and admin endpoints for production operations.

**Monitoring Endpoints**:

```bash
# Get detailed VRAM status
curl http://localhost:8001/vram/status | jq

# Response includes:
# - Memory usage (total, used, available, model usage)
# - Loaded models (with sizes, priorities, timestamps)
# - PSI metrics (pressure stall information)
# - Circuit breaker statistics
```

```bash
# Get health status (for load balancers)
curl http://localhost:8001/vram/health | jq

# Returns: healthy/degraded/unhealthy
# Healthy = usage < 90% AND PSI < warning threshold
```

```bash
# Get current PSI metrics
curl http://localhost:8001/vram/psi | jq

# Returns PSI metrics:
# - some_avg10: % time some processes stalled (waiting for memory)
# - full_avg10: % time all processes stalled (severe pressure)
```

**Admin Endpoints** (for manual intervention):

```bash
# Force registry reconciliation (sync with backend)
# Use after external OOM kills or manual interventions
curl -X POST http://localhost:8001/vram/admin/reconcile | jq

# Response shows:
# - registry_count: Models in registry
# - backend_count: Models actually loaded in Ollama
# - cleaned_count: Desynced models removed
# - cleaned_models: List of models cleaned up
```

```bash
# Get crash statistics for all models
curl http://localhost:8001/vram/admin/crashes | jq

# Shows models with recent crashes and circuit breaker status
```

```bash
# Clear crash history for a specific model
# Use to reset circuit breaker after fixing model issues
curl -X DELETE http://localhost:8001/vram/admin/crashes/ministral-3:14b | jq
```

```bash
# Manually unload a specific model
curl -X POST http://localhost:8001/vram/unload/ministral-3:14b | jq
```

```bash
# Flush system buffer cache (requires sudo)
# Use before loading very large models (>70GB)
curl -X POST http://localhost:8001/vram/flush-cache | jq
```

**Example: Recovery After OOM Event**

```bash
# 1. Check what's actually loaded
curl http://localhost:8001/vram/status | jq '.loaded_models'

# 2. Force reconciliation to clean up stale entries
curl -X POST http://localhost:8001/vram/admin/reconcile | jq

# 3. Check PSI to understand memory pressure
curl http://localhost:8001/vram/psi | jq

# 4. If PSI is high, manually unload models
curl -X POST http://localhost:8001/vram/unload/ministral-3:14b | jq
```

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
- Tables: users, auth_methods, conversations, webpage_chunks
- Data: In-memory (lost on container restart, can be persisted if needed)
- Unified User Model: Separate User (profile) and AuthMethod (credentials) entities

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
  --table-name conversations \
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
- Check active profile: Model may not be available in conservative profile
- Switch to performance or balanced profile if you have enough RAM: `VRAM_PROFILE=performance` or `VRAM_PROFILE=balanced`

#### Profile Configuration Issues

**Symptom**: "Failed to load configuration profile" or "Models not in roster" errors at startup

**Checks**:
```bash
# Check active profile
docker-compose logs fastapi-service | grep "Loading configuration profile"

# Should see:
# ✅ Loaded 'performance' profile (or 'balanced' or 'conservative')
#    Models: 3 (performance) | 10 (balanced) | 5 (conservative)
#    VRAM limit: varies by profile
```

**Common Issues**:

1. **Invalid profile name**:
   - Check `.env` has `VRAM_PROFILE=conservative`, `VRAM_PROFILE=performance`, or `VRAM_PROFILE=balanced`
   - Typos cause startup failure

2. **Wrong profile for system**:
   - **Symptom**: Frequent OOM kills, models evicting constantly
   - **Check**: `free -h` to see available RAM
   - **Solution**:
     - 16-32GB systems: Use `VRAM_PROFILE=conservative`
     - 128GB+ systems (speed priority): Use `VRAM_PROFILE=performance`
     - 128GB+ systems (model variety): Use `VRAM_PROFILE=balanced`

3. **Model not available in conservative profile**:
   - **Symptom**: Router assigns model that doesn't exist (e.g., 120B model)
   - **Reason**: Conservative profile only has 5 small models
   - **Solution**: Either switch to performance/balanced profile or use graceful degradation (automatic)

**Solutions**:
- Verify profile setting: `echo $VRAM_PROFILE`
- Check logs for profile loading: `docker-compose logs fastapi-service | head -30`
- Match profile to hardware:
  - **16-32GB RAM**: `VRAM_PROFILE=conservative`
  - **128GB+ RAM (max speed)**: `VRAM_PROFILE=performance` (SGLang Eagle3)
  - **128GB+ RAM (model variety)**: `VRAM_PROFILE=balanced` (full Ollama zoo)
  - **256GB+ RAM**: `VRAM_PROFILE=balanced` + disable orchestrator
- Restart after changing profile: `docker-compose restart fastapi-service`

#### Memory Issues (OOM Kills, High PSI, Model Crashes)

**Symptom**: Models crashing, OOM (out-of-memory) kills, "MemoryError" exceptions, or system slowness

The VRAM orchestrator is designed to prevent these issues, but they can still occur under extreme memory pressure.

**Understanding the Symptoms**:

1. **High PSI (Pressure Stall Information)**:
   ```bash
   # Check current PSI
   curl http://localhost:8001/vram/psi | jq

   # PSI meanings:
   # - some_avg10 < 10%: Healthy
   # - some_avg10 10-20%: Warning (system is under pressure)
   # - some_avg10 > 20%: Critical (imminent OOM risk)
   # - full_avg10 > 5%: Severe (all processes stalled)
   ```

2. **Registry Desyncs**:
   - System thinks models are loaded, but they were killed externally
   - Check logs for: `Registry desync detected`
   - Automatic reconciliation runs every 30 seconds

3. **Circuit Breaker Triggers**:
   - Model has crashed 2+ times in 5 minutes
   - System creates 20GB safety buffer before reloading
   - Check logs for: `Circuit breaker triggered`

**Automatic Prevention** (requires `VRAM_ENABLE_ORCHESTRATOR=true`):

The system automatically handles memory pressure:
- **PSI Monitoring**: Proactively evicts LOW priority models when `PSI full_avg10 > 10%`
- **Emergency Eviction**: Evicts NORMAL priority models when `PSI full_avg10 > 15%`
- **Circuit Breaker**: Creates safety buffer for crash-prone models
- **Registry Reconciliation**: Auto-cleans desynced entries every 30s

**Manual Recovery**:

```bash
# 1. Check VRAM orchestrator status
curl http://localhost:8001/vram/status | jq

# Key fields to check:
# - memory.usage_pct: Should be < 90%
# - memory.psi_full_avg10: Should be < 10%
# - loaded_models: List of currently loaded models

# 2. Check for crash loops
curl http://localhost:8001/vram/admin/crashes | jq

# If models have recent crashes, circuit breaker is protecting them

# 3. Force reconciliation (clean up stale entries)
curl -X POST http://localhost:8001/vram/admin/reconcile | jq

# This syncs registry with actual backend state

# 4. Manually unload large models to free space
curl -X POST http://localhost:8001/vram/unload/devstral-2:123b | jq
curl -X POST http://localhost:8001/vram/unload/deepseek-r1:70b | jq

# 5. Check PSI after unloading
curl http://localhost:8001/vram/psi | jq

# 6. If circuit breaker is blocking a model, clear its crash history
curl -X DELETE http://localhost:8001/vram/admin/crashes/devstral-2:123b | jq
```

**Configuration Tuning** (in `.env`):

For systems with limited memory (<128GB), tune these settings:

```bash
# Lower memory limits
VRAM_SOFT_LIMIT_GB=80.0   # Was: 100.0
VRAM_HARD_LIMIT_GB=90.0   # Was: 110.0

# More aggressive PSI thresholds
VRAM_PSI_WARNING_THRESHOLD=5.0   # Was: 10.0 (evict sooner)
VRAM_PSI_CRITICAL_THRESHOLD=10.0 # Was: 15.0 (evict sooner)

# Less aggressive circuit breaker (if needed)
VRAM_CRASH_THRESHOLD=3              # Was: 2 (tolerate more crashes)
VRAM_CIRCUIT_BREAKER_BUFFER_GB=15.0 # Was: 20.0 (smaller buffer)
```

After changing settings:
```bash
docker-compose restart fastapi-service
```

**Prevention Tips**:

1. **Monitor PSI regularly**: Set up alerts when `psi_full_avg10 > 5%`
2. **Use model priorities wisely**: Assign LOW priority to rarely-used models
3. **Avoid loading too many large models**: Each 24B model uses ~15GB
4. **Enable VRAM orchestrator**: Set `VRAM_ENABLE_ORCHESTRATOR=true` (recommended)
5. **Check logs for warnings**: Look for PSI warnings and reconciliation messages

**Logs to Watch**:

```bash
# Watch VRAM orchestrator logs
docker-compose logs -f fastapi-service | grep -E "(VRAM|PSI|Circuit|Reconcil)"

# Key patterns:
# - "⚠️  WARNING PSI" - Memory pressure detected
# - "🚨 CRITICAL PSI" - Emergency eviction triggered
# - "🔄 Circuit breaker triggered" - Crash protection activated
# - "Registry reconciliation: cleaned" - Desyncs detected and fixed
```

**Emergency: System Completely Out of Memory**

```bash
# 1. Restart FastAPI service (clears all loaded models)
docker-compose restart fastapi-service

# 2. Check system memory
free -h

# 3. If Ollama is stuck, restart it on host
sudo systemctl restart ollama
# or
pkill ollama && ollama serve

# 4. Verify orchestrator is healthy
curl http://localhost:8001/vram/health | jq
```

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
│   │   │   ├── model_factory.py # Model factory (VRAM integration)
│   │   │   └── ...
│   │   │
│   │   ├── services/           # Business logic
│   │   │   ├── orchestrator.py # Main coordinator
│   │   │   ├── router_service.py # Intelligent routing
│   │   │   ├── queue_worker.py # Background processor
│   │   │   ├── vram/           # VRAM orchestration system
│   │   │   │   ├── orchestrator.py      # VRAM coordinator
│   │   │   │   ├── model_registry.py    # LRU model tracking
│   │   │   │   ├── unified_memory_monitor.py # PSI + free monitoring
│   │   │   │   ├── eviction_strategies.py    # Priority-weighted LRU
│   │   │   │   ├── backend_managers.py  # Ollama/TensorRT/vLLM
│   │   │   │   ├── crash_tracker.py     # Circuit breaker
│   │   │   │   ├── interfaces.py        # SOLID interfaces
│   │   │   │   └── __init__.py          # Singleton factory
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
│   │   ├── test_vram/          # VRAM orchestration tests (74 tests)
│   │   │   ├── test_orchestrator.py     # Orchestrator + circuit breaker
│   │   │   ├── test_crash_tracker.py    # Circuit breaker logic
│   │   │   ├── test_registry.py         # Model registry
│   │   │   ├── test_eviction.py         # Eviction strategies
│   │   │   └── test_backend_managers.py # Backend delegation
│   │   └── ...
│   └── Dockerfile
│
├── discord-bot/                # Discord client
│   ├── bot/
│   │   ├── main.py             # Bot entry point
│   │   ├── client.py           # Discord client
│   │   └── message_handler.py  # Message processing
│   └── Dockerfile
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
