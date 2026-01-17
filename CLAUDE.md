# CLAUDE.md - Project Context for Claude Code

This file provides context about the TROISE AI architecture for Claude Code assistance.

## Project Structure

```
discord-ollama-agent/
├── troise-ai/              # Main AI service (FastAPI + Strands SDK)
│   ├── app/
│   │   ├── core/           # Core infrastructure
│   │   ├── plugins/        # Agents, skills, tools
│   │   ├── graphs/         # Graph definitions (YAML)
│   │   └── prompts/        # Agent prompts
│   ├── config/             # Configuration files
│   └── tests/              # Test suite
├── discord-bot/            # Discord client
├── admin-dashboard/        # Web admin UI
└── docker-compose.app.yml  # Application services
```

## Architecture: Graphs and Swarms

TROISE AI uses a **graph-based orchestration** system with optional **swarm collaboration**.

### Graphs (Deterministic Workflows)

Graphs define **developer-controlled execution paths** where nodes are agents and edges are transitions.

```
┌───────────┐    ┌─────────────┐    ┌─────────────┐
│  Node A   │───▶│   Node B    │───▶│   Node C    │
│  (agent)  │    │   (agent)   │    │   (agent)   │
└───────────┘    └─────────────┘    └─────────────┘
```

**Key characteristics:**
- **Declarative**: Defined in YAML (`app/graphs/definitions/*.yaml`)
- **Predictable**: Edges have conditions; paths are bounded
- **Stateful**: `GraphState` passes data between nodes
- **Observable**: Stream events show node transitions

**Graph definitions location:** `troise-ai/app/graphs/definitions/`

### Swarms (Emergent Collaboration)

Swarms are **pools of agents** that collaborate autonomously via handoffs. Agents decide when and to whom to transfer work.

```
┌────────────────────────────────────┐
│           SWARM                    │
│  ┌─────────┐    ┌─────────┐       │
│  │ Agent A │←──▶│ Agent B │       │
│  └────┬────┘    └────┬────┘       │
│       │              │            │
│       └──────┬───────┘            │
│              ▼                    │
│        ┌─────────┐                │
│        │ Agent C │                │
│        └─────────┘                │
└────────────────────────────────────┘
```

**Key characteristics:**
- **Autonomous**: Agents handoff based on judgment
- **Exploratory**: Good for research, debugging, review
- **Bounded**: Max handoffs/iterations prevent runaway
- **Nested**: Swarms are graph nodes (`SwarmNode`)

### Graph vs Swarm Decision Matrix

| Scenario | Use Graph | Use Swarm |
|----------|-----------|-----------|
| Sequential pipeline | ✓ | |
| Known validation gates | ✓ | |
| Exploratory research | | ✓ |
| Collaborative code review | | ✓ |
| Fixed output format needed | ✓ | |
| Discovery of unknowns | | ✓ |

## Current Graphs

### GENERAL Graph
Single node for general conversation.
```
general → END
```

### CODE Graph
Development pipeline with quality swarm for review/debug/test.
```
explorer → task_planner → agentic_code → quality_swarm → END
                                              │
                                    ┌─────────┴─────────┐
                                    │  code_reviewer    │
                                    │  debugger         │
                                    │  test_generator   │
                                    └───────────────────┘
```

### RESEARCH Graph
Research with swarm for deep exploration.
```
explorer → research_swarm → citation_formatter → END
                │
      ┌─────────┴─────────┐
      │  deep_research    │
      │  fact_checker     │
      │  synthesizer      │
      └───────────────────┘
```

### BRAINDUMP Graph
Thought capture pipeline (no swarm - deterministic).
```
explorer → braindump → thought_organizer → vault_connector → note_formatter → END
```

## Model Roles and Profiles

Agents use `model_role` to select models from the active profile.

| model_role | Balanced Profile Model |
|------------|------------------------|
| `general` | gpt-oss:120b (76GB) |
| `code` | devstral-small-2:24b (15GB) |
| `research` | magistral:24b (15GB) |
| `braindump` | magistral:24b (15GB) |
| `router` | gpt-oss:20b (13GB) |

**Same model serves multiple agents** - differentiation via system prompts.

## Key Files

| File | Purpose |
|------|---------|
| `app/core/graph_executor.py` | Executes graphs, handles streaming |
| `app/core/graph_nodes.py` | AgentNode, SwarmNode adapters |
| `app/graphs/loader.py` | Loads YAML → Graph objects |
| `app/graphs/conditions.py` | Edge condition functions |
| `app/graphs/definitions/*.yaml` | Graph topology definitions |
| `config/config.yaml` | Universal tools, profiles, etc. |

## SOLID Principles Applied

- **SRP**: SwarmNode only executes swarm; state extraction in subclasses
- **OCP**: Add graphs via YAML; add swarm types via `SPECIALIZED_SWARM_NODES` dict
- **LSP**: SwarmNode implements `IGraphNode` protocol like AgentNode
- **ISP**: Uses existing `NodeResult` interface
- **DIP**: Depends on protocols, not concrete implementations

## Common Tasks

### Add a new agent to a graph
1. Create agent in `app/plugins/agents/<name>/`
2. Add node to graph YAML in `app/graphs/definitions/`
3. Update edges as needed

### Add a new swarm
1. Define agents in YAML node with `type: swarm`
2. Add specialized node class if needed (`SPECIALIZED_SWARM_NODES`)
3. Update conditions in `app/graphs/conditions.py`

### Change universal tools
Edit `config/config.yaml` → `tools.universal_tools`

### Restart after config changes
```bash
docker compose -f docker-compose.app.yml restart troise-ai
```

### Rebuild after code changes
```bash
docker compose -f docker-compose.app.yml up -d --build troise-ai
```
