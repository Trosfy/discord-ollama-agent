# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Development Commands

```bash
# Run all tests
uv run pytest

# Run single test file
uv run pytest tests/core/test_router.py

# Run single test
uv run pytest tests/core/test_router.py::test_route_general_question -v

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check (if configured)
uv run mypy app/

# Run the service locally
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## Architecture Overview

TROISE AI is a personal AI augmentation system built on DGX Spark with 128GB unified memory. It provides intelligent routing of queries to appropriate skills/agents with VRAM-aware model management.

### Request Flow

```
User Message → Preprocessing → Router → Executor → Skill/Agent → Postprocessing → Response
                                           ↓
                                   VRAMOrchestrator
                                           ↓
                                   Ollama/SGLang Backend
```

### Core Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Container | `app/core/container.py` | DI container with singleton/factory registration |
| Router | `app/core/router.py` | LLM-based query classification using Strands Agent |
| Executor | `app/core/executor.py` | Executes skills/agents from routing decisions |
| Registry | `app/core/registry.py` | Plugin discovery and registration |
| VRAMOrchestrator | `app/services/vram_orchestrator.py` | Model lifecycle and VRAM management |
| BackendManager | `app/services/backend_manager.py` | Multi-backend support (Ollama, SGLang, vLLM) |

### Plugin System

- **Skills** (`app/plugins/skills/`): Simple LLM interactions, can be declarative (markdown) or Python
- **Agents** (`app/plugins/agents/`): Tool-using agents built on Strands SDK
- **Tools** (`app/plugins/tools/`): Functions agents can invoke

### Interfaces

Currently implemented interfaces:

| Interface | Use Case | Formatting |
|-----------|----------|------------|
| `discord` | Discord bot chat | Markdown, emoji, 2000 char limit |
| `web` | Web dashboard | Rich markdown, code blocks |

Interface-specific prompts are in `app/prompts/layers/interface_{name}.prompt`. The `PromptComposer` layers these with agent prompts and user personalization.

### Key Patterns

**Protocol-based interfaces** - All service interfaces use Python's Protocol:
```python
class IVRAMOrchestrator(Protocol):
    async def get_model(self, model_id: str, ...) -> Any: ...
```

**Strands Agent pattern** - LLM interactions use Strands SDK:
```python
model = await orchestrator.get_model(model_id=..., temperature=0.1, max_tokens=500)
agent = Agent(model=model, tools=[], system_prompt=PROMPT)
response = await loop.run_in_executor(None, agent, user_input)
```

**Declarative skills** - Skills defined in markdown (`skill.md`) with frontmatter config.

## Directory Structure

```
app/
├── core/           # Framework: container, router, executor, queue, registry
├── services/       # Service layer: vram_orchestrator, backend_manager, brain_service
├── plugins/        # Plugin system: agents/, skills/, tools/
├── preprocessing/  # Input pipeline: extractors, sanitizers
├── postprocessing/ # Output pipeline: artifact handlers
├── prompts/        # Prompt templates and composer
└── models/         # Data models
tests/              # Organized by component (core/, services/, plugins/)
```

## Testing Notes

- Tests use `pytest` with `asyncio_mode = "auto"` - no need for `@pytest.mark.asyncio`
- Mock `IVRAMOrchestrator` for unit tests (see `tests/conftest.py`)
- Integration tests may require running Ollama backend

## Docker & Container Management

The project uses a **split docker-compose architecture**:
- `docker-compose.infra.yml` - Always-on infrastructure (logging, dynamodb, auth, admin, web)
- `docker-compose.app.yml` - Toggleable application services (troise-ai, discord-bot)

```bash
# Start application services
./scripts/container_management/start.sh

# Stop application services (keeps infrastructure running)
./scripts/container_management/stop.sh

# View container logs (follow mode)
docker compose -f docker-compose.app.yml logs -f

# View specific container
docker compose -f docker-compose.app.yml logs -f troise-ai

# Check container status
docker compose -f docker-compose.app.yml ps

# Restart a specific service
docker compose -f docker-compose.app.yml restart troise-ai

# Rebuild and restart (after code changes)
docker compose -f docker-compose.app.yml up -d --build troise-ai
```

## Centralized Logging

All services send logs to `trollama-logging` on port 9999. Logs are written to date-based directories:

```bash
# View today's application logs
tail -f logs/$(date +%Y-%m-%d)/app.log

# View error logs
tail -f logs/$(date +%Y-%m-%d)/error.log

# View debug logs (verbose)
tail -f logs/$(date +%Y-%m-%d)/debug.log

# Search across all logs
grep -r "ERROR" logs/
```

Services use `shared/logging_client.py` to configure logging - imports `setup_logger(service_name)` which sends to centralized service and console.
