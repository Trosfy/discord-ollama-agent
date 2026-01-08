# Documentation Maintainer Guide

This guide helps maintainers keep documentation synchronized with code changes. Use this as a reference when adding new features, modifying systems, or making architectural changes.

## Table of Contents

- [Quick Reference: What to Update](#quick-reference-what-to-update)
- [Documentation Structure](#documentation-structure)
- [Update Patterns by Change Type](#update-patterns-by-change-type)
- [Writing Guidelines](#writing-guidelines)
- [Review Checklist](#review-checklist)

---

## Quick Reference: What to Update

Use this table to quickly identify which documentation files need updates based on your change type:

| Change Type | README.md | TECHNICAL.md | Other Files |
|-------------|-----------|--------------|-------------|
| **New route added** | ✅ Features, Quick Start examples | ✅ Routing section, Component Reference | config.py comments |
| **New model added** | ✅ Configuration → Model Configuration | ✅ Architecture diagram, Model capabilities | MODEL-TOOL-SUPPORT.md |
| **New service added** | ✅ Architecture diagram, Configuration | ✅ Architecture, Component Reference, Infrastructure | docker-compose.yml comments |
| **New API endpoint** | ✅ API Reference (if user-facing) | ✅ API Reference (detailed) | OpenAPI/Swagger auto-generated |
| **New environment variable** | ✅ Configuration Reference | ✅ Infrastructure section | .env.example |
| **Configuration change** | ✅ Configuration Reference | ✅ Component config details | config.py comments |
| **Deployment change** | ✅ Quick Start, Deployment section | ✅ Docker Architecture | docker-compose.yml |
| **New dependency** | ✅ Prerequisites | ✅ Technology Stack | requirements.txt, Dockerfile |
| **Bug fix** | ❌ (unless user-facing behavior) | ❌ (unless architectural) | - |
| **Performance improvement** | ❌ (unless significant) | ⚠️ (if architectural change) | - |
| **Security fix** | ⚠️ (update troubleshooting if relevant) | ⚠️ (update if pattern changed) | - |

**Legend**: ✅ Always update | ⚠️ Update if relevant | ❌ Usually no update needed

---

## Documentation Structure

### File Purposes

#### README.md (Non-Technical User Guide)
**Audience**: End users, deployers, Discord admins, new developers
**Purpose**: Get the system running quickly
**Tone**: Friendly, clear, assumes no prior knowledge
**Length**: ~1000 lines

**Sections**:
1. What it is (elevator pitch)
2. Key features (user-facing)
3. Architecture (high-level overview)
4. Quick Start (step-by-step setup)
5. **Configuration Reference** (most important for users)
6. Using the Bot (commands, features, examples)
7. Deployment & Operations (logs, health checks, maintenance)
8. Troubleshooting (common issues with solutions)
9. Development (project structure, tests, contributing)

#### TECHNICAL.md (Comprehensive Technical Documentation)
**Audience**: Developers, contributors, technical reviewers
**Purpose**: Deep understanding of architecture and implementations
**Tone**: Professional, detailed, assumes engineering background
**Length**: ~3000 lines

**Sections**:
1. Architecture Overview (diagrams, tech stack, patterns)
2. **Unique/Niche Implementations** (what makes system special)
3. End-to-End Flows (request pipelines, decision flows)
4. Component Reference (services, interfaces, implementations)
5. Infrastructure & DevOps (monitoring, logging, Docker)
6. Database & Storage (schemas, persistence)
7. API Reference (detailed endpoint docs)
8. LLM Expert Analysis & Rating (objective assessment)

#### Other Documentation Files

- **MODEL-TOOL-SUPPORT.md**: Model capabilities matrix
- **archive/docs/README.md**: Explanation of archived content
- **.env.example**: Environment variable template with comments
- **fastapi-service/tests/TESTING.md**: Testing guide
- **scripts/README.md**: Utility scripts documentation
- **docker-compose.yml**: Inline comments for each service

---

## Update Patterns by Change Type

### 1. Adding a New Route

**Example**: Adding a new `IMAGE_GENERATION` route that uses DALL-E style models.

#### README.md Updates

**Section: Key Features → Intelligent Routing**
```markdown
- **Intelligent Routing** - Automatically classifies queries and routes to specialized models:
  - Math problems → rnj-1:8b
  - Simple code → rnj-1:8b
  - Complex code → deepcoder:14b
  - Reasoning → magistral:24b
  - Research → magistral:24b
  + Image generation → flux:8b (NEW)  # Add this line
  - General chat → gpt-oss:20b
```

**Section: Configuration Reference → Model Configuration**
```markdown
**Required models per route**:
- ROUTER_MODEL: gpt-oss:20b (classification)
- MATH_MODEL: rnj-1:8b
...
+ IMAGE_GENERATION_MODEL: flux:8b  # Add this line
```

**Section: Using the Bot → Features in Action**
```markdown
# Add new example
**Image Generation** → flux:8b
```
You: @Bot create an image of a sunset over mountains

Bot: *Generating image...*
[Image displayed]
```
```

#### TECHNICAL.md Updates

**Section: Architecture Overview → REQUEST ROUTING**
```markdown
│  │ REQUEST ROUTING (6 Routes):  # Change to 7 Routes
│  │  • MATH: Math problems (rnj-1:8b)
│  │  • SIMPLE_CODE: Quick code tasks (rnj-1:8b)
│  │  • COMPLEX_CODE: System design (deepcoder:14b)
│  │  • REASONING: Analysis (magistral:24b + tools)
│  │  • RESEARCH: Deep research (magistral:24b + tools)
+ │  │  • IMAGE_GENERATION: Image creation (flux:8b)  # Add this
│  │  • SELF_HANDLE: General Q&A (gpt-oss:20b + tools)
```

**Section: Unique Implementations → LLM-Based Intelligent Routing**
```python
class Route(Enum):
    MATH = "MATH"
    SIMPLE_CODE = "SIMPLE_CODE"
    COMPLEX_CODE = "COMPLEX_CODE"
    REASONING = "REASONING"
    RESEARCH = "RESEARCH"
+   IMAGE_GENERATION = "IMAGE_GENERATION"  # Add this
    SELF_HANDLE = "SELF_HANDLE"
```

**Section: Component Reference → Services → RouterService**

Add description of new route classification logic.

#### Other Files

- `fastapi-service/app/config.py`: Add `IMAGE_GENERATION_MODEL` setting
- `fastapi-service/app/routing/route.py`: Add route enum value
- `fastapi-service/app/prompts/routes/image_generation.prompt`: Create new prompt file
- Update inline comments in route definitions

---

### 2. Adding a New Model

**Example**: Adding `llama3.3:70b` as an alternative reasoning model.

#### README.md Updates

**Section: Configuration Reference → Model Configuration**
```markdown
#### Model Capabilities Matrix

| Model | Size | Tools | Thinking | Vision | Best For |
|-------|------|-------|----------|--------|----------|
| gpt-oss:20b | 14GB | ✅ | ✅ (level) | ❌ | General chat, routing |
+ | llama3.3:70b | 42GB | ✅ | ❌ | ❌ | Deep reasoning, analysis |  # Add row
| rnj-1:8b | 5GB | ✅ | ❌ | ❌ | Math, simple code |
...
```

**Section: Quick Start → Set Up Ollama Models**
```bash
ollama pull gpt-oss:20b          # Router + general chat (14GB)
+ ollama pull llama3.3:70b         # Alternative reasoning model (42GB)  # Add if recommended
ollama pull rnj-1:8b             # Math + simple code (5GB)
```

#### TECHNICAL.md Updates

**Section: Technology Stack → Ollama Models**

Update the model list in the architecture diagram.

**Section: Component Reference → Model Capabilities**

Add detailed capabilities:
```markdown
**llama3.3:70b**:
- Size: 42GB (requires RAM offload)
- Supports tools: ✅
- Supports thinking: ❌
- Context window: 128K
- Best for: Deep analysis requiring large context
- Performance: 8-15 tok/s (with RAM offload)
```

#### Other Files

**MODEL-TOOL-SUPPORT.md**:
```markdown
| Model | Tools Supported | Route | Notes |
|-------|----------------|-------|-------|
+ | llama3.3:70b | ✅ Yes | REASONING | Large context, good for analysis |
```

**fastapi-service/app/config.py**:
```python
_AVAILABLE_MODELS = [
    ModelCapabilities(
        name="gpt-oss:20b",
        supports_tools=True,
        ...
    ),
+   ModelCapabilities(
+       name="llama3.3:70b",
+       supports_tools=True,
+       supports_thinking=False,
+       context_window=128000
+   ),
    ...
]
```

---

### 3. Adding a New Service

**Example**: Adding a `cache-service` for LLM response caching.

#### README.md Updates

**Section: Architecture**
```
Supporting Services:
- Logging Service: Centralized log collection
- Monitoring Service: Health dashboard + alerts
+ - Cache Service: LLM response caching  # Add this
```

**Section: Configuration Reference → Environment Variables**
```markdown
#### Cache Configuration  # Add new section

```bash
# Enable response caching
CACHE_ENABLED=true

# Cache TTL (seconds)
CACHE_TTL=3600

# Redis connection
REDIS_HOST=cache-service
REDIS_PORT=6379
```
```

**Section: Deployment & Operations → Starting Services**
```markdown
**Services will start in order**:
1. `logging-service` (port 9999) - Centralized logging
2. `dynamodb-local` (port 8000) - Local database
+ 3. `cache-service` (port 6379) - Redis cache  # Add this
3. `auth-service` (port 8002) - Authentication
4. `admin-service` (port 8003) - Admin API
5. `fastapi-service` (port 8001) - Main API
6. `discord-bot` (port 9997) - Discord connection
```

**Section: Troubleshooting → Common Issues**

Add new troubleshooting section for cache-related issues.

#### TECHNICAL.md Updates

**Section: Architecture Overview → System Architecture Diagram**

Add cache-service box to ASCII diagram.

**Section: Infrastructure & DevOps → Docker Architecture**

Add service to dependency chain:
```
logging-service (base)
    ↓
dynamodb-local (base)
    ↓
+ cache-service (depends on logging)
    ↓
fastapi-service (depends on dynamodb, logging, cache)
    ↓
discord-bot (depends on fastapi, logging)
```

**Section: Component Reference → Services**

Add new section:
```markdown
#### CacheService
**File**: `cache-service/cache.py`

**Purpose**: LLM response caching to reduce latency and cost.

**Features**:
- Semantic similarity matching for queries
- TTL-based expiration
- Redis backend with persistence
- Hit rate metrics

**Key Methods**:
```python
async def get_cached_response(query: str) -> Optional[str]:
    """Get cached response for similar query."""

async def cache_response(query: str, response: str, ttl: int):
    """Cache response with TTL."""
```
```

#### Other Files

**docker-compose.yml**:
```yaml
cache-service:
  image: redis:7-alpine
  container_name: trollama-cache
  ports:
    - "6379:6379"
  volumes:
    - cache-data:/data
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 30s
    timeout: 5s
    retries: 3
```

**.env.example**:
```bash
# Cache Service
CACHE_ENABLED=true
REDIS_HOST=cache-service
REDIS_PORT=6379
CACHE_TTL=3600
```

---

### 4. Adding a New API Endpoint

**Example**: Adding `POST /api/admin/analytics` for system analytics.

#### README.md Updates

**Section: API Endpoints → Admin API** (if user-facing)
```markdown
### Admin API
- `POST /api/admin/grant-tokens` - Grant bonus tokens
- `POST /api/admin/maintenance/soft` - Enable soft maintenance
- `POST /api/admin/maintenance/hard` - Enable hard maintenance
+ - `POST /api/admin/analytics` - Generate system analytics report  # Add this
- `GET /api/admin/queue/stats` - Get queue statistics
```

#### TECHNICAL.md Updates

**Section: API Reference → REST Endpoints → Admin API**
```markdown
**Admin API**:
- `POST /api/admin/grant-tokens` - Grant bonus tokens
- `POST /api/admin/maintenance/soft` - Soft maintenance
- `POST /api/admin/maintenance/hard` - Hard maintenance
+ - `POST /api/admin/analytics` - Generate analytics  # Add detailed docs
- `GET /api/admin/queue/stats` - Queue stats
```

Add detailed documentation:
```markdown
#### POST /api/admin/analytics

Generates system analytics report for specified time period.

**Request**:
```json
{
    "start_date": "2025-12-01",
    "end_date": "2025-12-13",
    "include_users": true,
    "include_routes": true
}
```

**Response**:
```json
{
    "period": {
        "start": "2025-12-01",
        "end": "2025-12-13"
    },
    "total_requests": 15234,
    "route_distribution": {
        "MATH": 2341,
        "SIMPLE_CODE": 5432,
        ...
    },
    "top_users": [...],
    "token_usage": {...}
}
```

**Use Case**: Generate monthly reports for usage analysis.
```

#### Other Files

**OpenAPI/Swagger**: Auto-generated from FastAPI decorators (ensure proper docstrings)

---

### 5. Adding a New Environment Variable

**Example**: Adding `ENABLE_RATE_LIMITING` flag.

#### README.md Updates

**Section: Configuration Reference → Environment Variables**
```markdown
#### Queue Settings

```bash
# Maximum number of queued requests
MAX_QUEUE_SIZE=50

+ # Enable per-user rate limiting
+ ENABLE_RATE_LIMITING=true
+
+ # Max requests per user per minute
+ RATE_LIMIT_PER_MINUTE=10

# Maximum retry attempts for failed requests
MAX_RETRIES=3
```
```

#### TECHNICAL.md Updates

**Section: Component Reference → QueueWorker**

Update to mention rate limiting if it affects the component.

**Section: Infrastructure & DevOps → Configuration**

Add to configuration table or list.

#### Other Files

**.env.example**:
```bash
# Queue Settings
MAX_QUEUE_SIZE=50
+ ENABLE_RATE_LIMITING=true
+ RATE_LIMIT_PER_MINUTE=10
MAX_RETRIES=3
```

**fastapi-service/app/config.py**:
```python
class Settings(BaseSettings):
    # Queue Settings
    MAX_QUEUE_SIZE: int = 50
+   ENABLE_RATE_LIMITING: bool = True
+   RATE_LIMIT_PER_MINUTE: int = 10
    MAX_RETRIES: int = 3
```

Add inline comment explaining the setting.

---

### 6. Changing Deployment/Infrastructure

**Example**: Adding Kubernetes deployment option.

#### README.md Updates

**Section: Prerequisites**
```markdown
### Prerequisites

1. **Docker & Docker Compose** - For running all services
+ 2. **Or Kubernetes** - For production deployment (optional)
3. **Ollama** - Running on host machine with models pulled
```

**Section: Quick Start**

Add new subsection:
```markdown
#### Alternative: Kubernetes Deployment

For production environments, Kubernetes deployment is recommended:

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/

# Check pod status
kubectl get pods -n trollama

# View logs
kubectl logs -f deployment/fastapi-service -n trollama
```

See [k8s/README.md](k8s/README.md) for detailed Kubernetes setup.
```

#### TECHNICAL.md Updates

**Section: Infrastructure & DevOps → Docker Architecture**

Add new section:
```markdown
### Kubernetes Architecture (Alternative Deployment)

For production environments, the system can be deployed on Kubernetes:

**Benefits**:
- Auto-scaling based on load
- Zero-downtime deployments
- Better resource management
- Built-in health checks and restart policies

**Manifests**:
- `k8s/fastapi-deployment.yaml` - FastAPI service
- `k8s/discord-bot-deployment.yaml` - Discord bot
- `k8s/monitoring-deployment.yaml` - Monitoring service
- `k8s/ingress.yaml` - Ingress configuration

**Services**:
- ClusterIP for internal services (DynamoDB, logging)
- LoadBalancer for FastAPI (external access)
- NodePort for monitoring dashboard

See [k8s/README.md](k8s/README.md) for detailed deployment guide.
```

#### Other Files

Create new `k8s/README.md` with Kubernetes-specific documentation.

---

## Writing Guidelines

### General Principles

1. **User-First**: README.md prioritizes user needs (setup, configuration, troubleshooting)
2. **Developer-Second**: TECHNICAL.md provides deep technical insights
3. **Keep Both Synchronized**: Changes should update both files when relevant
4. **Examples Over Explanation**: Show, don't just tell
5. **Maintenance-Aware**: Document why, not just what (helps future maintainers)

### README.md Writing Style

**Good Example**:
```markdown
#### Ollama Connection Failures

**Symptom**: Errors like "Failed to connect to Ollama"

**Checks**:
1. Ollama is running on host:
   ```bash
   curl http://localhost:11434/api/tags
   ```

2. Models are pulled:
   ```bash
   ollama list
   ```

**Solutions**:
- Start Ollama: `ollama serve`
- Pull missing models: `ollama pull gpt-oss:20b`
```

**Bad Example**:
```markdown
#### Ollama Issues

The system might fail to connect to Ollama. Check if Ollama is running and models are available.
```

**Why bad**: No concrete steps, no commands to run, no solutions.

### TECHNICAL.md Writing Style

**Good Example**:
```markdown
#### LLM-as-Classifier Pattern

**Implementation**:
```python
model = OllamaModel(model_name="gpt-oss:20b", temperature=0.1)
agent = Agent(model=model)
response = agent(classification_prompt + user_message)
route = extract_route_name(response)
```

**Why innovative**:
- Semantic understanding beats keyword matching
- Deterministic with temp=0.1 (consistent routing)
- Handles nuanced queries gracefully

**Industry adoption**: Emerging pattern, expect to see more.
```

**Bad Example**:
```markdown
The system uses LLMs for routing. It's better than keywords.
```

**Why bad**: No code example, no explanation of innovation, no context.

### Code Examples

**Good**:
```python
# From router.py:61-112
async def classify_route(self, user_message: str) -> str:
    """Classify user message into a route using LLM."""
    model = OllamaModel(
        model_name=self.router_model,
        temperature=0.1  # Deterministic classification
    )
    # ... rest of implementation
```

**Bad**:
```python
def classify_route(user_message):
    # Uses LLM to classify
    return route
```

**Why bad**: No file reference, no context, no inline comments explaining why.

### File Path References

**Always use**:
- Absolute paths from repo root
- Clickable markdown links when possible
- Line numbers for specific code: `router.py:61-112`

**Examples**:
```markdown
**File**: [fastapi-service/app/routing/router.py](fastapi-service/app/routing/router.py)

See lines 61-112 in [router.py](fastapi-service/app/routing/router.py#L61-L112)
```

### Architecture Diagrams

**ASCII diagrams should**:
- Use box drawing characters for clarity
- Show data flow direction (arrows: ↓, →, ←)
- Label connections (e.g., "WebSocket", "HTTP")
- Include service names and ports
- Fit in 80-100 character width

**Update diagrams when**:
- New service added
- Service ports change
- Data flow changes
- Dependencies change

---

## Review Checklist

Use this checklist before committing documentation changes:

### Pre-Commit Checklist

#### Content Accuracy
- [ ] All code examples are tested and work
- [ ] File paths are correct and files exist
- [ ] Environment variables match `.env.example`
- [ ] Configuration values match `config.py` defaults
- [ ] API endpoints match actual implementation
- [ ] Model names match available models in config

#### Completeness
- [ ] README.md updated if user-facing change
- [ ] TECHNICAL.md updated if architectural change
- [ ] Configuration reference updated if new env var
- [ ] .env.example updated with new variables
- [ ] docker-compose.yml has inline comments
- [ ] Relevant specialized docs updated (MODEL-TOOL-SUPPORT.md, etc.)

#### Style & Formatting
- [ ] Consistent markdown formatting (headers, lists, code blocks)
- [ ] Code blocks have language tags (```python, ```bash)
- [ ] Links are in markdown format: `[text](url)`
- [ ] Examples follow "Good Example" patterns above
- [ ] ASCII diagrams are aligned and clear
- [ ] No broken internal links

#### Organization
- [ ] New sections added in logical locations
- [ ] Table of contents updated if structure changed
- [ ] Similar information consolidated (not duplicated)
- [ ] Cross-references between docs are accurate

### Quarterly Review Checklist

Review documentation quarterly or after major releases:

- [ ] Verify all quick start steps still work
- [ ] Update model recommendations if new models available
- [ ] Check troubleshooting section has current issues
- [ ] Verify all file paths still exist
- [ ] Update screenshots if UI changed
- [ ] Review and update "outdated" warnings
- [ ] Move outdated content to archive/
- [ ] Update LLM expert rating if major changes

---

## Documentation Patterns

### Pattern: Adding a New Feature

**Steps**:
1. Identify feature type (route, service, endpoint, etc.)
2. Update README.md:
   - Add to "Key Features" if user-facing
   - Add configuration if needed
   - Add usage example
   - Add to troubleshooting if common issues expected
3. Update TECHNICAL.md:
   - Add to architecture diagram if new component
   - Document implementation details
   - Add to component reference
   - Update relevant flows if behavior changes
4. Update specialized docs (MODEL-TOOL-SUPPORT.md, etc.)
5. Update .env.example if new variables
6. Add inline comments in code

### Pattern: Deprecating a Feature

**Steps**:
1. Add deprecation warning to README.md:
   ```markdown
   > **⚠️ DEPRECATED**: This feature will be removed in v2.0. Use [alternative] instead.
   ```
2. Add deprecation note to TECHNICAL.md
3. Update examples to show new approach
4. Keep old documentation until removal
5. When removed:
   - Move to archive/docs/ with explanation
   - Remove from main docs
   - Update archive/docs/README.md

### Pattern: Major Architecture Change

**Steps**:
1. Update architecture diagrams in both README.md and TECHNICAL.md
2. Add migration guide section if breaking change
3. Update all affected component references
4. Review and update all end-to-end flows
5. Update technology stack if new dependencies
6. Update LLM expert analysis if architectural improvement
7. Consider creating a separate MIGRATION.md guide

---

## Tips for Maintainers

### Keep Documentation Close to Code

- Update docs in same PR as code changes
- Reviewers should check for documentation updates
- Use CI/CD to validate documentation (broken links, etc.)

### Use Templates

Create templates for common documentation patterns:
- New route template
- New service template
- New endpoint template
- Troubleshooting entry template

### Document Why, Not Just What

**Good**: "Uses temp=0.1 for deterministic routing (consistent results for similar queries)"
**Bad**: "Uses temp=0.1"

### Keep Examples Realistic

Use real examples from the system, not hypothetical ones.

### Version Important Changes

For major documentation updates:
```markdown
<!-- Last updated: 2025-12-13 | Added cache-service documentation -->
```

### Get Feedback

Ask users if documentation helped them:
- Add GitHub Discussions for doc questions
- Track common confusion points
- Update docs based on real user issues

---

## Common Pitfalls

### ❌ Don't Do This

1. **Updating code without updating docs**
   - Result: Confused users, outdated information

2. **Copy-pasting without adapting**
   - Result: Inconsistent style, duplicate information

3. **Over-documenting implementation details in README.md**
   - Result: Overwhelming for users, belongs in TECHNICAL.md

4. **Under-documenting unique features in TECHNICAL.md**
   - Result: Missing the point - showcase innovations!

5. **Using vague language**
   - Bad: "The system is fast"
   - Good: "Achieves 25-35 tokens/sec with gpt-oss:20b"

6. **Broken examples**
   - Always test code snippets before committing

7. **Forgetting .env.example**
   - New env vars must be documented with comments

### ✅ Do This Instead

1. **Update docs in same PR as code**
2. **Use consistent examples throughout**
3. **Keep README.md practical, TECHNICAL.md detailed**
4. **Highlight what makes your system unique**
5. **Use specific metrics and measurements**
6. **Test all code snippets and commands**
7. **Sync .env.example with config.py**

---

## Questions to Ask Yourself

Before committing documentation changes, ask:

1. **Can a new user deploy the system using only README.md?**
2. **Can a developer understand the architecture from TECHNICAL.md?**
3. **Are all new configuration options documented with examples?**
4. **Do code examples actually work?**
5. **Are file paths accurate?**
6. **Is the change significant enough to update LLM expert analysis?**
7. **Would I understand this documentation if I were new to the project?**

If any answer is "no" or "maybe", revise before committing.

---

## Getting Help

If you're unsure about documentation changes:

1. Check existing documentation patterns in README.md and TECHNICAL.md
2. Look at git history for how similar changes were documented
3. Ask in team discussions or PR reviews
4. Test documentation with a colleague unfamiliar with the change

---

**Remember**: Documentation is code. Treat it with the same rigor as your implementation. Good documentation is the difference between a useful system and an abandoned one.

**Last Updated**: 2025-12-13
