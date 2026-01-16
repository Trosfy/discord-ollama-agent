# Troise-AI: Personal AI Augmentation System

> A self-hosted personal AI assistant built on DGX Spark, designed for braindumping, agentic coding, and serving as a second brain.

## Vision

Troise-AI is a personal AI augmentation system that transforms how you capture ideas, write code, and manage knowledge. Unlike generic AI assistants, it's deeply integrated with your workflows, remembers your decisions, questions your assumptions, and grows with you.

**Core Capabilities:**
- 💬 **General Helper** - Chat about anything, discuss ideas, get answers, ad-hoc requests
- 🧠 **Braindumps & Ideation** - Capture raw thoughts via voice or text, get questioned back, refine into actionable insights
- 💻 **Structured Coding** - Spec-first, checkpoint-based agentic coding with local models
- 📚 **Second Brain** - Everything stored in Obsidian, searchable, interconnected
- 🎨 **Create Anything** - Images, documents (docx, xlsx, pdf), diagrams, presentations
- 🎯 **Smart Routing** - Natural language requests routed to 60+ specialized skills

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            INTERFACES                                    │
├─────────────────┬─────────────────┬──────────────────┬──────────────────┤
│   Web App       │   Troise-Vibe     │   Discord        │   Obsidian       │
│   (Phone/PC)    │   CLI           │   (Trollama)     │   (Storage)      │
│                 │                 │                  │                  │
│ • Voice memos   │ • Agentic code  │ • Community bot  │ • Brain storage  │
│ • Chat          │ • Checkpoints   │ • Existing infra │ • Sync everywhere│
│ • Quick capture │ • Local models  │                  │                  │
└────────┬────────┴────────┬────────┴────────┬─────────┴────────┬─────────┘
         │                 │                 │                  │
         └─────────────────┴────────┬────────┴──────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      FASTAPI ORCHESTRATION LAYER                        │
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐  │
│  │ Skill       │  │ Brain       │  │ Obsidian    │  │ File          │  │
│  │ Router      │  │ Search/Fetch│  │ Service     │  │ Generators    │  │
│  │ (60+ skills)│  │             │  │             │  │               │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────────┘  │
│                                                                         │
│  Existing Infrastructure: VRAM Orchestrator, PSI Monitoring,            │
│  Circuit Breaker, DynamoDB Storage, WebSocket Streaming                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      DGX SPARK (128GB Unified Memory)                   │
│                                                                         │
│  gpt-oss:20b     devstral:123b    magistral:24b    whisper-large-v3    │
│  (router/general) (complex code)  (reasoning)      (transcription)     │
│                                                                         │
│  rnj-1:8b        flux:schnell     deepseek-r1:70b  qwen3-vl:8b         │
│  (fast tasks)    (images)         (deep reasoning) (vision/OCR)        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           STORAGE LAYER                                 │
│                                                                         │
│  Obsidian Vault          DynamoDB Local           Generated Files       │
│  (Knowledge/Brain)       (Conversations)          (docx, xlsx, etc.)   │
│  - Synced everywhere     - Session history        - Temporary outputs   │
│  - Markdown + links      - User preferences       - Downloadable        │
└─────────────────────────────────────────────────────────────────────────┘
```

## Design Principles

Based on [Daniel Miessler's Kai system](https://youtu.be/Le0DLrn7ta0), adapted for local-first deployment:

| # | Principle | Implementation |
|---|-----------|----------------|
| 1 | **Prompting Still Matters** | Clear, tested prompts in each skill |
| 2 | **Scaffolding > Model** | 60+ skills with explicit routing beats latest model |
| 3 | **Code Before Prompts** | Deterministic code where possible (80/20 rule) |
| 4 | **Specs, Tests, Evals** | Fight "vibe coding" with structure |
| 5 | **Unix Philosophy** | Skills call other skills, composable pipelines |
| 6 | **Engineering Principles** | TDD, spec-driven development |
| 7 | **CLI-First** | AI loves `--help` documentation |
| 8 | **High-Level Flow** | Goal → Code → CLI → Prompts → Skills |
| 9 | **Self-Updating** | System monitors sources and improves itself |
| 10 | **Custom Skill Routing** | Explicit routing tables, not just vibes |
| 11 | **Structured History** | Learnings, decisions, sessions - all searchable |
| 12 | **Interactive Refinement** | AI questions back, challenges assumptions |

## Key Workflows

### 0. General Helper (Default)

The baseline experience - just chat naturally. The system intelligently routes to any of the 60+ skills when needed, including **composing multiple skills** for complex requests.

```
You: "What's the difference between async and threading in Python?"
AI: [Answers directly, no skill needed]

You: "Generate a logo for my startup"
AI: [Invokes create/image → returns generated image]

You: "Research competitors and create a comparison spreadsheet"
AI: [Chains: research/deep-research → analyze/compare → documents/xlsx]

You: "What did I decide about auth? Then help me implement it"
AI: [Chains: recall/what-decided → presents context → starts build/code workflow]
```

**Multi-skill composition patterns:**
- **Sequential**: Research → Analyze → Create diagram
- **Parallel**: Generate image + Write blog post (simultaneously)
- **Conditional**: Check notes → If found, implement; else create spec

**Routing logic:**
- Simple questions → Direct answer (no skill invoked)
- Single task → Route to appropriate skill
- Complex request → Compose multiple skills
- "I've been thinking..." → Braindump workflow
- Code tasks → Coding workflow (with checkpoints if complex)

### 1. Braindump & Ideation

```
Voice/Text Input
      │
      ▼
┌─────────────────┐
│ 1. CAPTURE      │ Transcribe, extract core ideas
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. QUESTION     │◄────────────┐
│                 │             │
│ • Clarify       │             │
│ • Challenge     │             │
│ • Expand        │             │
│ • Connect       │             │
└────────┬────────┘             │
         │                      │
         ▼                      │
┌─────────────────┐             │
│ 3. RESPOND      │─────────────┘ (loop until refined)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. SYNTHESIZE   │
│                 │
│ • Summary       │
│ • Key insights  │
│ • Open questions│
│ • Action items  │
│ • Brain map     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5. CONNECT      │ brain_search() for related notes
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 6. ROUTE        │ Research? Spec? Red-team? Save?
└─────────────────┘
```

### 2. Agentic Coding (with Checkpoints)

```
"Add authentication to the API"
      │
      ▼
┌─────────────────┐
│ brain_search()  │ Find relevant past decisions, learnings
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Generate Spec   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ✋ CHECKPOINT   │ "Here's the spec. Approve?"
└────────┬────────┘
         │ (approved)
         ▼
┌─────────────────┐
│ Generate Plan   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ✋ CHECKPOINT   │ "Here's the plan. Approve?"
└────────┬────────┘
         │ (approved)
         ▼
┌─────────────────┐
│ Execute Steps   │
│                 │
│ For each major  │
│ step: checkpoint│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Run Tests       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Save Decision   │ Log to Obsidian for future reference
└─────────────────┘
```

### 3. Second Brain (Brain Search/Fetch)

```
brain_search("what did I decide about model routing?")
      │
      ▼
┌─────────────────────────────────────────────────────┐
│ Returns short index entries:                        │
│                                                     │
│ • [2024-12-15] 6-route system for Trollama         │
│ • [2025-01-02] PSI-based VRAM eviction             │
│ • [2025-01-05] Considered Mistral for local coding │
└─────────────────────────────────────────────────────┘
      │
      ▼
brain_fetch("2025-01-02-psi-eviction")
      │
      ▼
┌─────────────────────────────────────────────────────┐
│ Full note with context, reasoning, alternatives     │
└─────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- NVIDIA DGX Spark (or similar high-VRAM system)
- Existing Trollama infrastructure (FastAPI, DynamoDB, VRAM orchestrator)
- Obsidian with sync configured
- Python 3.11+

### Installation

```bash
# Clone the repository
git clone https://github.com/trosfy/troise-ai.git
cd troise-ai

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your paths and settings

# Initialize Obsidian vault structure
python scripts/init_vault.py --path /path/to/obsidian/vault

# Start the service
docker-compose up -d
```

### First Commands

```bash
# Voice braindump (from web interface)
# Record → Transcribe → Question loop → Save to Obsidian

# Quick text capture
troise capture "I've been thinking about multi-agent workflows..."

# Brain search
troise brain search "model routing"

# Start agentic coding session
troise-vibe "Add user authentication to the Flask app"

# Generate a document
troise create docx --template report --topic "Q4 Infrastructure Review"
```

## Project Structure

```
troise-ai/
├── README.md
├── TECHNICAL_DESIGN.md
├── docker-compose.yml
├── pyproject.toml
│
├── fastapi-service/
│   ├── app/
│   │   ├── main.py
│   │   ├── config/
│   │   │   └── profiles/          # VRAM profiles (existing)
│   │   ├── api/
│   │   │   ├── websocket.py       # Existing
│   │   │   ├── voice.py           # NEW: Voice capture endpoints
│   │   │   ├── brain.py           # NEW: Brain search/fetch
│   │   │   └── skills.py          # NEW: Skill invocation
│   │   ├── services/
│   │   │   ├── vram/              # Existing VRAM orchestrator
│   │   │   ├── obsidian_service.py    # NEW
│   │   │   ├── brain_service.py       # NEW
│   │   │   ├── transcription_service.py # NEW
│   │   │   └── skill_router.py        # NEW
│   │   └── skills/                # NEW: 60+ skill definitions
│   │       ├── capture/
│   │       ├── think/
│   │       ├── build/
│   │       └── ...
│   └── tests/
│
├── troise-vibe/                     # Forked Mistral Vibe CLI
│   ├── cli.py
│   ├── workflow.py                # Checkpoint logic
│   └── brain_integration.py       # Context from Obsidian
│
├── obsidian-vault/                # Template structure
│   ├── 00-inbox/
│   ├── 10-ideas/
│   ├── 20-projects/
│   ├── 30-knowledge/
│   ├── 40-decisions/
│   └── _index/
│
└── scripts/
    ├── init_vault.py
    └── upgrade_check.py           # Self-update checker
```

## Documentation

- [Technical Design](./TECHNICAL_DESIGN.md) - Detailed architecture and implementation
- [Skills Reference](./docs/SKILLS.md) - Complete skill taxonomy
- [Obsidian Structure](./docs/OBSIDIAN.md) - Vault organization and templates
- [API Reference](./docs/API.md) - Endpoint documentation

## Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Obsidian vault structure + templates
- [ ] ObsidianService in FastAPI
- [ ] brain_search / brain_fetch endpoints
- [ ] Basic web capture interface

### Phase 2: Braindump Workflow (Week 2-3)
- [ ] Voice transcription (Whisper on DGX)
- [ ] Interactive questioning loop
- [ ] Synthesis + brain map generation
- [ ] Skill routing from braindump

### Phase 3: Agentic Coding (Week 3-4)
- [ ] Fork Mistral Vibe → troise-vibe
- [ ] Checkpoint system (spec, plan, major steps)
- [ ] Brain context integration
- [ ] Decision logging to Obsidian

### Phase 4: Scale Skills (Ongoing)
- [ ] Document generators (docx, xlsx, pdf, csv)
- [ ] Research skills (deep research, comparison)
- [ ] Communication skills (email, blog, social)
- [ ] Self-upgrade skill

## License

MIT

## Acknowledgments

- Daniel Miessler's [Kai system](https://youtu.be/Le0DLrn7ta0) for the design philosophy
- Anthropic's Claude Code for skill/workflow patterns
- Mistral's Vibe CLI for agentic coding foundation