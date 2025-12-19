# Local LLM Setup Guide
## Optimized for RTX 5080 16GB + 64GB RAM

---

## 🎯 TL;DR - Which Models to Use

### Essential Setup (Get These)

| Model | Size | Use When | Speed | Why |
|-------|------|----------|-------|-----|
| **gpt-oss:20b** | 14GB | General tasks, browsing, research, daily chat | ⚡⚡⚡ 25-35 tok/s | Fits entirely in VRAM, fastest, web-native |
| **qwen3-coder:30b** | 19GB | All coding work, debugging, refactoring | ⚡⚡⚡ 20-30 tok/s | Best coding model, 256K context, agentic |

### Optional (Add Later If Needed)

| Model | Size | Use When | Speed | Why |
|-------|------|----------|-------|-----|
| **deepseek-r1:32b** | 20GB | Planning, architecture, transparent reasoning | ⚡⚡ 15-25 tok/s | Shows thinking process, good for learning |
| **gpt-oss:120b** | 65GB | Production code review, critical decisions, security | 🐌 5-10 tok/s | Maximum quality when stakes are high |

### Quick Decision Tree

```
┌─ General browsing/chat? ──────────► gpt-oss:20b
│
├─ Writing code? ───────────────────► qwen3-coder:30b
│
├─ Need to see reasoning process? ──► deepseek-r1:32b
│
└─ Production/critical decision? ───► gpt-oss:120b
```

---

## 💻 Your Hardware

**System Specs:**
- CPU: AMD Ryzen 9950X3D (with 3D V-Cache)
- GPU: NVIDIA RTX 5080 16GB VRAM
- RAM: 64GB DDR5-6000 (dual-channel)
- Storage: 2TB PCIe Gen 5 NVMe (T-FORCE TM8FFL, ~15 GB/s)
- Motherboard: ASUS ROG Strix B850-I (with AI Cache Boost)
- WSL2: Ubuntu with Ollama

**Memory Hierarchy (Speed Comparison):**
- VRAM: ~550 GB/s (RTX 5080) - ⚡⚡⚡ Fastest
- System RAM: ~96 GB/s (DDR5-6000) - 6x slower than VRAM
- NVMe SSD: ~15 GB/s (PCIe Gen 5) - 35x slower than VRAM

**Critical:** Never use SSD for model offloading - even PCIe Gen 5 is far too slow for LLM inference. Models must be in VRAM or RAM.

**Memory Allocation:**
- WSL2: 56GB (recommended)
- Windows: 8GB
- Total available for models: 72GB (16GB VRAM + 56GB RAM)

---

## 📊 Model Comparison Table

| Model | Total Size | Active Params | Architecture | Context | VRAM | RAM | Speed | Reasoning |
|-------|-----------|---------------|--------------|---------|------|-----|-------|-----------|
| **gpt-oss:20b** | 14GB | 20B (5.1B active MoE) | MoE | 128K | 100% | 0% | 25-35 tok/s | Optional |
| **qwen3-coder:30b** | 19GB | 30.5B (3.3B active MoE) | MoE | 256K | 84% | 16% | 20-30 tok/s | No |
| **deepseek-r1:32b** | 20GB | 32B | Dense | 128K | 80% | 20% | 15-25 tok/s | Yes (explicit) |
| **gpt-oss:120b** | 65GB | 117B (5.1B active MoE) | MoE | 128K | 25% | 75% | 5-10 tok/s | Configurable |
| **qwen3:30b** | 19GB | 30.5B (3.3B active MoE) | MoE | 40K | 84% | 16% | 20-30 tok/s | Optional |
| **llama3.3:70b** | 42GB | 70B | Dense | 128K | 38% | 62% | 8-15 tok/s | No |
| **deepseek-r1:70b** | 43GB | 70B | Dense | 128K | 37% | 63% | 8-15 tok/s | Yes (explicit) |

---

## 🎯 Detailed Use Cases

### gpt-oss:20b - Your Daily Driver

**Perfect for:**
- Web research and browsing
- General questions and learning
- Content drafting (emails, documents)
- Trip planning, shopping research
- Quick calculations and analysis
- News summaries
- Conversational assistance
- Tool calling and function use

**Why it's optimal:**
- Fits entirely in VRAM (no RAM offload penalty)
- Fastest response times
- Can stay loaded 24/7
- Native web search capability (coming to Ollama)
- Built by OpenAI for reasoning + agentic tasks

**Example usage:**
```bash
ollama run gpt-oss:20b
>>> Research the best budget smartphones under $300
>>> Help me plan a 5-day trip to Tokyo
>>> Summarize the latest AI news
```

---

### qwen3-coder:30b - Coding Specialist

**Perfect for:**
- Writing new code (scripts, modules, apps)
- Debugging and error fixing
- Code refactoring
- Repository-level understanding
- Agentic coding workflows (LangGraph)
- Code review
- Test generation

**Why it's optimal:**
- Purpose-built for coding
- 256K context (2x larger than others)
- Excellent agentic capabilities
- Fast enough for interactive coding
- MoE efficiency (only 3.3B active)

**Example usage:**
```bash
ollama run qwen3-coder:30b
>>> Create a FastAPI REST API with authentication
>>> Debug this race condition in my distributed lock
>>> Refactor this code to use async/await
```

---

### deepseek-r1:32b - The Architect

**Perfect for:**
- System architecture planning
- Algorithm design (when you want to see the thinking)
- Complex debugging
- Learning how to approach problems
- Educational purposes
- LangGraph agent planning phase

**Why it's useful:**
- Shows explicit chain-of-thought reasoning
- Helps you understand the problem-solving process
- Good balance of speed and depth
- Distilled from 671B flagship model

**Example usage:**
```bash
ollama run deepseek-r1:32b
>>> Design a distributed caching strategy for our system
>>> Create an implementation plan for a RAG system
>>> Analyze potential race conditions in this code
```

**Example output:**
```
<think>
Distributed caching... let me think through this systematically.

Key considerations:
- Consistency vs availability (CAP theorem)
- Cache invalidation strategy
- Data distribution approach

For high-read workloads, cache-aside pattern makes sense...
[detailed reasoning visible]
</think>

Recommended architecture:
[implementation plan]
```

---

### gpt-oss:120b - Maximum Quality

**Perfect for:**
- Production code security reviews
- Critical architecture decisions
- Complex algorithm analysis
- Novel problem-solving
- High-stakes decisions
- When 32B wasn't deep enough
- Batch/overnight analysis

**Why it's worth the wait:**
- Deepest reasoning capability
- Catches edge cases smaller models miss
- Configurable reasoning effort (low/medium/high)
- 20-40% better quality than 32B on complex problems

**When to use:**
- Code going to production
- Security-critical reviews
- Architecture with major consequences
- When mistakes are expensive
- You're not an expert in the domain
- After 32B tried but wasn't sufficient

**Example usage:**
```bash
ollama run gpt-oss:120b
>>> Comprehensive security audit of this authentication system
>>> Analyze this distributed consensus algorithm for all failure modes
>>> Design complete fault-tolerant architecture for our platform
```

**Cost/benefit:**
- Takes 2-3 minutes vs 30 seconds
- But catches issues that cost weeks to fix
- ROI: 93,000%+ on critical decisions

---

## 🔄 Multi-Model Workflows

### Pattern 1: Two-Stage Analysis (Smart)

**Use 20B to engineer prompts for 120B:**

```python
# Stage 1: Quick prompt engineering (10 sec)
ollama run gpt-oss:20b
>>> "I need help with my distributed system. Create a detailed 
    prompt for deep analysis covering architecture, scalability, 
    failure modes, and trade-offs."

# Stage 2: Deep analysis with structured prompt (2 min)
ollama run gpt-oss:120b
>>> [Paste structured prompt with your details filled in]
```

**Benefits:**
- Better structured thinking
- More comprehensive coverage
- Better use of 120B's capabilities
- Only adds 10 seconds upfront

---

### Pattern 2: Planning → Implementation (Professional)

**Architect role (deepseek-r1:32b) → Engineer role (qwen3-coder:30b):**

```python
# Step 1: Create detailed plan with transparent reasoning
ollama run deepseek-r1:32b
>>> "Design a complete RAG system for our documentation. 
    Include architecture, components, and implementation plan."

# [Review plan, adjust as needed]

# Step 2: Implement from plan
ollama run qwen3-coder:30b
>>> "Given this plan: [paste], implement the DocumentChunker 
    class with the specified requirements."

# Step 3: Continue implementation
>>> "Now implement the EmbeddingGenerator class"
>>> "Now wire up the retrieval pipeline"
```

**This mirrors how effective dev teams work:**
- Planning: Transparent reasoning, comprehensive thinking
- Implementation: Fast execution, clean code
- Quality: Best of both worlds

---

### Pattern 3: LangGraph Multi-Agent

```python
from langgraph.graph import StateGraph
from langchain_community.llms import Ollama

# Planner: deepseek-r1:32b (transparent reasoning)
planner = Ollama(model="deepseek-r1:32b")

# Coder: qwen3-coder:30b (fast implementation)  
coder = Ollama(model="qwen3-coder:30b")

# Reviewer: qwen3-coder:30b (fast feedback)
reviewer = Ollama(model="qwen3-coder:30b")

workflow = StateGraph()
workflow.add_node("plan", planner_agent)
workflow.add_node("implement", coder_agent)
workflow.add_node("review", reviewer_agent)
# [configure edges and conditional logic]
```

---

## ⚡ Performance Deep Dive

### Memory Hierarchy (The Reality)

| Memory Type | Bandwidth | Latency | Speed vs VRAM |
|-------------|-----------|---------|---------------|
| **RTX 5080 VRAM** | 550 GB/s | <10 ns | 100% |
| **DDR5-6000 RAM** | 96 GB/s | ~100 ns | **17%** |
| **PCIe Gen 5 NVMe** | 15 GB/s | ~100 μs | **2.7%** |

**Key insight:** RAM is 6x slower than VRAM. Even your high-end PCIe Gen 5 SSD is 35x slower than VRAM.

### RAM Offload Impact

**Models entirely in VRAM:**
- gpt-oss:20b (14GB) → 0% RAM → 100% performance ⚡
- Performance: 25-35 tok/s

**Models mostly in VRAM:**
- qwen3-coder:30b (19GB) → 16% RAM → ~80% performance ⚡
- deepseek-r1:32b (20GB) → 20% RAM → ~70% performance ⚡
- Performance: 15-30 tok/s

**Models heavily in RAM:**
- llama3.3:70b (42GB) → 62% RAM → ~35% performance ⚠️
- gpt-oss:120b (65GB) → 75% RAM → ~20% performance ⚠️
- Performance: 5-15 tok/s

**Never use SSD offload:**
- Even PCIe Gen 5 (15 GB/s) → ~1% performance 🐌
- System becomes unusable (disk thrashing)
- 1-2 minutes per token
- Thermal issues from constant disk access
- Just don't - if a model needs SSD, it's too big for your hardware

---

## 💡 The RAM Offload Revelation

### What RAM Offload Actually Enables

**Without RAM offload:**
```
To run gpt-oss:120b:
- Need: 80GB VRAM GPU (NVIDIA H100)
- Cost: $30,000 for GPU alone
- Total system: $40,000+
- Access: Enterprise only
```

**With RAM offload:**
```
To run gpt-oss:120b:
- Need: 16GB VRAM + 64GB RAM
- Cost: $2,500 total system
- Access: Consumer available
- Trade: 5x slower, but WORKS
```

**You're running a $40,000 model on $2,500 hardware.**

### The Perspective Shift

**Don't think:** "RAM offload makes it 5x slower"
**Think:** "RAM offload makes it possible at all"

**The real comparison:**

| Option | Performance | Cost | Accessible? |
|--------|-------------|------|-------------|
| Pure VRAM (H100) | 30 tok/s | $40,000 | ❌ No |
| RAM offload (Your setup) | 5-10 tok/s | $2,500 | ✅ YES |
| No access | 0 tok/s | N/A | ❌ No |

**5 tok/s > 0 tok/s**

**This is democratization of AI.**

---

## 🔧 Optimization Tips

### BIOS Settings

Your ASUS ROG Strix B850-I has **AI Cache Boost** - enable it:

1. Enter BIOS (Del or F2 during boot)
2. Find "AI Cache Boost" (likely in AI Tweaker or AMD Overclocking)
3. Enable it
4. Enable EXPO profile for your DDR5 RAM
5. Consider enabling PBO (Precision Boost Overdrive)

**Expected improvement:**
- 5-15% faster LLM inference with RAM offload
- Better utilization of 3D V-Cache
- Optimized memory pathways for LLM access patterns

### WSL2 Configuration

Edit `.wslconfig` in Windows:

```ini
[wsl2]
memory=56GB          # Leave 8GB for Windows
processors=16        # All cores
swap=0               # Disable swap for better performance
```

Restart WSL2:
```powershell
wsl --shutdown
```

### CPU Governor (Performance Mode)

```bash
# In WSL2
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

---

## 📥 Installation Commands

### Essential Models

```bash
# Daily driver - general tasks
ollama pull gpt-oss:20b          # 14GB download

# Coding specialist
ollama pull qwen3-coder:30b      # 19GB download
```

### Optional Models

```bash
# Planning with transparent reasoning
ollama pull deepseek-r1:32b      # 20GB download

# Maximum quality (critical tasks only)
ollama pull gpt-oss:120b         # 65GB download
```

### Verify Installation

```bash
# List installed models
ollama list

# Test a model
ollama run gpt-oss:20b "Explain async/await in Python"
```

---

## 🚫 Models to AVOID

### Don't Bother With:

❌ **qwen3:30b** - gpt-oss:20b is better for general tasks (faster, longer context, web-native)

❌ **llama3.3:70b** - Too slow due to RAM bottleneck (8-15 tok/s), not specialized for your use case

❌ **deepseek-r1:70b** - Too slow (8-15 tok/s), 32B version gives 80% of quality at 2x speed

❌ **gpt-oss:120b for daily use** - Only use for critical tasks, too slow for interactive work

❌ **Any model >100GB** - Won't fit in your memory budget, would need SSD offload (unusable)

---

## 🎓 Key Learnings

### On Model Selection

1. **Smaller specialized models > larger generalist models** for specific tasks
2. **MoE models** (like gpt-oss, qwen3) are efficient but still need full size in memory
3. **Context length matters** - qwen3-coder's 256K is huge for repository work
4. **"Ecosystem consistency" is marketing** - mix and match best tools for each job

### On Performance

1. **VRAM is king** - Models in VRAM run 5-6x faster than RAM offload
2. **Never use SSD offload** - 100x slower, system-killing
3. **Sweet spot for your hardware: 14-20GB models** (all/mostly in VRAM)
4. **Acceptable range: 20-30GB** (still responsive)
5. **Compromised: 30-50GB** (slower but usable for important tasks)
6. **Painful: 50GB+** (only for critical decisions where quality > speed)

### On RAM Offload

1. **Enables access to models designed for $40k hardware**
2. **Trade speed for capability** - worth it for important tasks
3. **Not a limitation, a democratizing technology**
4. **5 tok/s with full control > cloud API with censorship**

### On Use Cases

1. **Production code = use 120B** - mistakes cost more than 2 minutes
2. **Exploration/learning = use 20B/32B** - speed matters for iteration
3. **Don't trust "good enough"** - you don't know what smaller models missed
4. **For critical work: time cost << mistake cost**

### On Workflow

1. **Two-stage workflows** (20B → 120B) save time on complex queries
2. **Multi-model setups** (planning + implementation) mirror real teams
3. **Can't load all models simultaneously** - switch based on task (takes seconds)
4. **Keep 20B loaded for daily use** - swap in specialists as needed

---

## 🎯 Decision Frameworks

### When to Use Which Model

```
Is it coding-related?
├─ YES → qwen3-coder:30b
└─ NO ↓

Is it going to production?
├─ YES → gpt-oss:120b (security, architecture, critical logic)
└─ NO ↓

Do you need to see the reasoning?
├─ YES → deepseek-r1:32b
└─ NO ↓

Is it general/research/browsing?
└─ gpt-oss:20b
```

### Quality vs Speed Trade-off

```
How critical is this decision?

Low stakes (learning, exploration):
→ Use fastest model (20B)
→ Speed > perfection

Medium stakes (planning, design):
→ Use balanced model (32B)
→ Quality + speed balance

High stakes (production, security, architecture):
→ Use best model (120B)
→ Quality > speed
→ Mistakes cost more than 2 minutes
```

### Interactive vs Batch

```
Are you waiting for the response?

YES (interactive):
├─ Simple task → 20B (instant)
├─ Coding → 30B (fast)
├─ Planning → 32B (good)
└─ Critical → 120B if worth wait

NO (batch/overnight):
└─ Always use 120B
    (max quality, you're not waiting)
```

---

## 🚀 Getting Started

### Day 1: Essential Setup

```bash
# Install Ollama (if not already)
# Windows: Download from ollama.com
# Configure WSL2 memory (56GB)

# Pull essential models
ollama pull gpt-oss:20b
ollama pull qwen3-coder:30b

# Test them
ollama run gpt-oss:20b
>>> Hello! Test query

ollama run qwen3-coder:30b
>>> Write a quicksort in Python
```

### Week 1: Learn Your Models

- Use gpt-oss:20b for all general tasks
- Use qwen3-coder:30b for coding
- Get familiar with speed and quality
- Note where you wish you had more depth

### Week 2+: Add Specialists If Needed

```bash
# If you miss seeing reasoning
ollama pull deepseek-r1:32b

# If you hit critical decisions
ollama pull gpt-oss:120b
```

---

## 🎁 Bonus: GUI Options

### Open WebUI (Recommended)

ChatGPT-like interface for Ollama:

```bash
docker run -d -p 3000:8080 \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --name open-webui \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

Access at: `http://localhost:3000`

Features:
- Clean UI
- Multi-model support
- Conversation history
- Model parameter controls
- File uploads

### VSCode Integration (Continue)

Already set up - configure for new models in `~/.continue/config.json`:

```json
{
  "models": [
    {
      "title": "GPT-OSS 20B",
      "provider": "ollama",
      "model": "gpt-oss:20b"
    },
    {
      "title": "Qwen3 Coder",
      "provider": "ollama", 
      "model": "qwen3-coder:30b"
    }
  ]
}
```

---

## 📊 Expected Memory Usage

### Loading Single Models

| Model | VRAM | System RAM | Available for OS |
|-------|------|------------|------------------|
| gpt-oss:20b | 14GB | 0GB | 50GB |
| qwen3-coder:30b | 16GB | 3GB | 45GB |
| deepseek-r1:32b | 16GB | 4GB | 44GB |
| gpt-oss:120b | 16GB | 49GB | ~3GB |

### Can't Load Simultaneously

```
gpt-oss:20b (14GB) + qwen3-coder:30b (19GB) = 33GB total
> 16GB VRAM available

Solution: Load one at a time, swap as needed
Switching time: ~10 seconds
```

---

## 🎯 Final Recommendations

### Absolute Minimum Setup

**Just need these two:**
1. gpt-oss:20b (general)
2. qwen3-coder:30b (coding)

**Total storage:** 33GB
**Use case coverage:** 90%+

### Recommended Setup

**Add planning capability:**
1. gpt-oss:20b (general)
2. qwen3-coder:30b (coding)
3. deepseek-r1:32b (planning)

**Total storage:** 53GB
**Use case coverage:** 95%+

### Professional Setup

**Add maximum quality:**
1. gpt-oss:20b (daily driver)
2. qwen3-coder:30b (coding)
3. deepseek-r1:32b (planning)
4. gpt-oss:120b (critical decisions)

**Total storage:** 118GB
**Use case coverage:** 100%

---

## 🔄 Workflow Summary

### Typical Day

```
Morning: General research
→ gpt-oss:20b (loaded all day)

Midday: Coding session
→ qwen3-coder:30b (load when needed)

Afternoon: Architecture planning
→ deepseek-r1:32b (shows thinking process)

Evening: Security review before deploy
→ gpt-oss:120b (critical task, worth the wait)
```

### Complex Project

```
Phase 1: Planning (Day 1)
→ deepseek-r1:32b creates comprehensive plan
→ Review and refine

Phase 2: Implementation (Days 2-5)
→ qwen3-coder:30b implements from plan
→ Fast iteration
→ Quick debugging

Phase 3: Pre-Production Review (Day 6)
→ gpt-oss:120b comprehensive security audit
→ gpt-oss:120b architecture review
→ Fix issues found

Phase 4: Launch
→ Confidence from thorough review
```

---

## 📚 Additional Resources

### Documentation
- Ollama: https://github.com/ollama/ollama
- gpt-oss: https://github.com/openai/gpt-oss
- Qwen: https://github.com/QwenLM/Qwen
- DeepSeek: https://github.com/deepseek-ai/DeepSeek-R1

### Tools Integration
- LangGraph: Multi-agent workflows
- LangChain: RAG and chains
- Open WebUI: GUI interface
- Continue: VSCode integration

---

## ✅ Checklist

### Initial Setup
- [ ] Configure WSL2 memory (56GB)
- [ ] Enable AI Cache Boost in BIOS
- [ ] Enable EXPO profile for RAM
- [ ] Install Ollama
- [ ] Pull gpt-oss:20b
- [ ] Pull qwen3-coder:30b
- [ ] Test both models
- [ ] (Optional) Install Open WebUI

### Optional Setup
- [ ] Pull deepseek-r1:32b
- [ ] Pull gpt-oss:120b
- [ ] Configure Continue extension
- [ ] Set up LangGraph workflows

### Ongoing
- [ ] Use 20B for daily general tasks
- [ ] Use 30B for coding
- [ ] Use 120B for critical decisions
- [ ] Monitor performance
- [ ] Adjust as needed

---

## 🎓 Remember

**Key Principles:**
1. **Faster isn't always better** - quality matters for critical work
2. **RAM offload enables accessibility** - not a limitation
3. **Mix and match models** - no "ecosystem" lock-in
4. **Speed vs quality trade-off** - choose based on stakes
5. **Your $2.5k setup runs $40k models** - that's incredible

**Most Important:**
- Use the right tool for each job
- Don't compromise on production code
- Speed matters for iteration
- Quality matters for decisions
- You have access to SOTA AI at home

---

**Created:** Based on comprehensive discussion about local LLM setup  
**Hardware:** AMD 9950X3D, RTX 5080 16GB, 64GB DDR5-6000, 2TB PCIe Gen 5 NVMe  
**Last Updated:** December 2025

---

## 📖 Glossary

**SOTA** = State-Of-The-Art (most advanced/best technology currently available)  
**MoE** = Mixture of Experts (sparse model architecture, only activates subset of parameters per token)  
**VRAM** = Video RAM (GPU memory, fastest for LLM inference)  
**Offload** = Moving model data from faster memory (VRAM) to slower memory (RAM/SSD)  
**Tokens/sec** = Speed metric for LLM inference (how many words/tokens generated per second)  
**Context window** = Maximum length of text the model can process at once (measured in tokens)  
**Quantization** = Compression technique to reduce model size (Q4, Q8, etc.)  
**Dense model** = All parameters active for every token (vs sparse MoE)  
**Tool calling** = Model's ability to use external functions/APIs  
**Chain-of-thought** = Explicit reasoning process shown in output (e.g., `<think>` blocks)