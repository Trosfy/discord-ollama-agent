# Open WebUI Tools Installation Guide

This directory contains two web search tools for Open WebUI that integrate with the local SearXNG instance.

## Available Tools

### 1. Web Search Tool (`web_search_tool.py`)
**Best for:** Quick web searches, fact checking, current information

**Features:**
- Simple single-parameter interface: `run(query: str)`
- Multi-engine support: SearXNG (primary), DuckDuckGo, Google
- Automatic fallback if primary engine fails
- Fast results (~2-5 seconds)
- No dependencies beyond beautifulsoup4 and requests

**Use Cases:**
- "Search for Python 3.12 new features"
- "What's the weather in Bangkok?"
- "Latest news about quantum computing"

### 2. Iterative Web Research Tool (`iterative_websearch_tool.py`)
**Best for:** In-depth research, academic queries, comprehensive analysis

**Features:**
- Fetches and analyzes full web page content
- Semantic search using embeddings
- MMR (Maximal Marginal Relevance) ranking for diverse sources
- Returns most relevant chunks from multiple pages
- Requires Ollama embedding model (e.g., qwen3-embedding:4b)

**Use Cases:**
- "Research the impact of climate change on coral reefs"
- "Analyze recent developments in quantum computing"
- "Compare different approaches to machine learning interpretability"

## Installation

### Step 1: Access Open WebUI

Navigate to: http://localhost:12000 (or http://100.75.221.114:12000 via NetBird)

### Step 2: Navigate to Tools

1. Click **Workspace** in the left sidebar
2. Select **Tools**
3. Click **Add Tool** button (top right)

### Step 3: Install Web Search Tool

1. Copy the entire content of `web_search_tool.py`
2. Paste it into the tool editor
3. Click **Save**
4. **Enable** the tool (toggle switch should turn green)
5. Verify "Available to all users" is checked

### Step 4: Install Iterative Research Tool (Optional)

**Prerequisites:**
```bash
# Pull embedding model in Ollama
ollama pull qwen3-embedding:4b
# or
ollama pull nomic-embed-text
```

Then:
1. Copy the entire content of `iterative_websearch_tool.py`
2. Paste it into the tool editor
3. Click **Save**
4. **Enable** the tool
5. Verify "Available to all users" is checked

### Step 5: Verify Installation

Create a new chat and type:
```
/tools
```

You should see your installed tools listed.

## Configuration

### Web Search Tool Settings

Access tool settings: Workspace → Tools → Web Search → ⚙️ (gear icon)

**Key Settings:**

```python
searxng_url: "http://searxng:8080"    # Local SearXNG instance
enable_searxng: True                   # Use SearXNG (recommended)
enable_duckduckgo: False               # Disable (gets blocked)
enable_google: False                   # Disable (gets blocked)
default_max_results: 5                 # Results per query
enable_fallback: True                  # Auto-fallback on failure
```

**Note:** Keep SearXNG enabled and direct scraping (DDG, Google) disabled to avoid bot detection.

### Iterative Research Tool Settings

Access: Workspace → Tools → Iterative Web Research → ⚙️

**Key Settings:**

```python
searxng_url: "http://searxng:8080"    # Local instance
use_searxng: True                      # Use SearXNG
embedding_api_url: "http://host.docker.internal:11434/api/embeddings"
embedding_model_name: "qwen3-embedding:4b"
max_results: 8                         # Pages to fetch
top_k: 5                              # Top chunks to return
```

## Usage Examples

### Simple Search

**User:** "Search for latest Python releases"

**Tool Call:** `web_search(query="latest Python releases")`

**Expected Output:**
```
🔍 **SearXNG Search Results:**

1. **Python Releases for Python 3.12**
   The latest version of Python 3.12 series...
   🔗 https://www.python.org/downloads/

2. **What's New in Python 3.12**
   Python 3.12 brings performance improvements...
   🔗 https://docs.python.org/3.12/whatsnew/
```

### In-Depth Research

**User:** "Research quantum computing applications in cryptography"

**Tool Call:** `iterative_websearch(query="quantum computing cryptography applications")`

**Expected Output:**
```
📚 **Research Results (5 sources):**

1. [source.com] Quantum computing poses both threats and opportunities for cryptography...
   Relevance: 0.87

2. [university.edu] Post-quantum cryptography algorithms are being developed...
   Relevance: 0.82

...
```

## Testing Tools

### Test Web Search Tool

Create a new chat and try:
```
Use the web search tool to find information about "machine learning"
```

or directly invoke:
```
web_search("machine learning")
```

### Test Iterative Research Tool

```
Use the iterative research tool to analyze "climate change impact on oceans"
```

### Verify SearXNG Connection

In a chat:
```
Search for "test query"
```

Check Open WebUI logs:
```bash
docker logs open-webui -f | grep -i "search\|searxng"
```

You should see:
```
🔍 Searching SearXNG for: test query
```

## Troubleshooting

### Tool Not Being Called

**Problem:** Model doesn't recognize or call the tool

**Solutions:**
1. Verify tool is **enabled** (green toggle)
2. Check "Available to all users" is checked
3. Use explicit language: "Use the web search tool to..."
4. Try reloading Open WebUI page
5. Check model supports function calling (gpt-oss:120b does)

### SearXNG Connection Error

**Error:** `SearXNG search error: Connection refused`

**Solutions:**
1. Verify SearXNG is running:
   ```bash
   docker ps | grep searxng
   ```

2. Test from Open WebUI container:
   ```bash
   docker exec open-webui curl http://searxng:8080/search?q=test&format=json
   ```

3. Check docker network:
   ```bash
   docker network inspect trollama-network
   ```

4. Verify URL in Valves: `http://searxng:8080` (NOT localhost)

### Embedding Model Error (Iterative Tool)

**Error:** `Embedding model not found`

**Solutions:**
1. Pull embedding model:
   ```bash
   ollama pull qwen3-embedding:4b
   ```

2. Verify Ollama access from container:
   ```bash
   docker exec open-webui curl http://host.docker.internal:11434/api/tags
   ```

3. Check embedding_model_name matches pulled model

### No Results Returned

**Problem:** Tool executes but returns no results

**Solutions:**
1. Check SearXNG logs:
   ```bash
   docker logs searxng -f
   ```

2. Test SearXNG directly:
   ```
   http://localhost:12001/search?q=test&format=json
   ```

3. Verify search engines enabled in SearXNG settings:
   ```bash
   cat searxng/settings.yml | grep -A 5 "engines:"
   ```

### Model Hallucinates Results

**Problem:** Model generates fake search results instead of using tool

**Solutions:**
1. Verify tool is being called:
   - Check Open WebUI logs for tool execution
   - Look for "🔍 Searching SearXNG" message

2. Use explicit prompt:
   "Use the web_search tool (do not hallucinate) to find information about X"

3. Check if SearXNG actually returned results (not error message)

## Advanced Configuration

### Custom Search Engines

Edit `searxng/settings.yml` to add/remove engines:

```yaml
engines:
  - name: github
    engine: github
    disabled: false

  - name: arxiv
    engine: arxiv
    disabled: false
    categories: science
```

Restart SearXNG:
```bash
docker-compose restart searxng
```

### Rate Limiting

For heavy usage, adjust in tool Valves:

```python
request_timeout: 30          # Increase timeout
retry_attempts: 3            # More retries
requests_per_second: 1.0     # Slower rate (iterative tool)
```

### Embedding Model Selection

For iterative research tool, alternative models:

```python
# Faster, less accurate
embedding_model_name: "nomic-embed-text"

# Slower, more accurate
embedding_model_name: "mxbai-embed-large"

# Recommended (good balance)
embedding_model_name: "qwen3-embedding:4b"
```

## Performance Optimization

### Web Search Tool
- **Response Time:** ~2-5 seconds
- **Memory:** Minimal (~100MB)
- **Best For:** Quick queries, real-time info

### Iterative Research Tool
- **Response Time:** ~15-30 seconds (depends on pages)
- **Memory:** ~500MB-1GB (for embeddings)
- **Best For:** Comprehensive research, analysis

**Tips:**
1. Use web_search for quick facts
2. Use iterative_research for in-depth analysis
3. Reduce `max_results` in iterative tool for faster responses
4. Increase `top_k` for more comprehensive results

## Tool Comparison

| Feature | Web Search | Iterative Research |
|---------|-----------|-------------------|
| Speed | Fast (2-5s) | Slow (15-30s) |
| Depth | Surface-level | In-depth |
| Sources | 5-10 results | Full page content |
| Accuracy | Good | Better |
| Memory | Low | High |
| Requires | SearXNG | SearXNG + Ollama embeddings |
| Use Case | Quick facts | Research, analysis |

## Updating Tools

1. Edit tool file in this directory
2. Copy updated content
3. In Open WebUI: Workspace → Tools → Select tool → Edit
4. Paste new content → Save

## Best Practices

1. **Always enable SearXNG** - avoids bot detection
2. **Disable direct scraping** (DuckDuckGo, Google) - gets blocked
3. **Use specific queries** - better results
4. **Choose appropriate tool** - simple vs. research
5. **Monitor logs** - helps debugging
6. **Keep Ollama running** - required for embeddings

## Support

**Issues:**
- [Web Search Not Working](../TOOL_FIX_GUIDE.md)
- [Open WebUI Setup](../README.md)
- [SearXNG Configuration](https://docs.searxng.org/)

**Logs:**
```bash
# Open WebUI logs
docker logs open-webui -f

# SearXNG logs
docker logs searxng -f

# Combined
docker-compose logs -f
```

## Next Steps

1. ✅ Install tools
2. ✅ Configure SearXNG connection
3. ✅ Test with simple query
4. 🔄 Experiment with different models
5. 🔄 Fine-tune Valves settings for your needs

Happy searching! 🔍
