# Open WebUI + SearXNG Setup

This directory contains the complete Open WebUI and SearXNG setup for the discord-ollama-agent project.

## Architecture

```
┌──────────────────────────────────────────────────┐
│         open-webui/docker-compose.yml            │
│                                                  │
│  ┌─────────────────┐     ┌──────────────────┐  │
│  │   Open WebUI    │────▶│     SearXNG      │  │
│  │  (host: 12000)  │     │  (host: 12001)   │  │
│  │  (int: 8080)    │     │  (int: 8080)     │  │
│  └─────────────────┘     └──────────────────┘  │
│           │                        │            │
└───────────┼────────────────────────┼────────────┘
            │                        │
            └────────────┬───────────┘
                         │
                  trollama-network (external)
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    fastapi-service  discord-bot   monitoring-service
```

## Directory Structure

```
open-webui/
├── docker-compose.yml       # Service definitions
├── start.sh                 # Launch script with GPU support
├── searxng/
│   └── settings.yml        # SearXNG configuration
├── tools/
│   ├── web_search_tool.py           # Simple web search
│   ├── iterative_websearch_tool.py  # Advanced research
│   └── README.md                    # Tool installation guide
└── README.md (this file)
```

## Quick Start

### 1. Prerequisites

- Docker and docker-compose installed
- NVIDIA GPU with drivers (for GPU access)
- Ollama running on host at port 11434
- `trollama-network` docker network (auto-created if missing)

### 2. Configure Firewall

Allow SearXNG port through UFW:

```bash
sudo ufw allow from 100.64.0.0/10 to any port 12001 proto tcp comment 'SearXNG'
```

### 3. Start Services

From the `open-webui/` directory:

```bash
./start.sh
```

This will:
- Check Ollama connectivity
- Generate SearXNG secret key
- Start both Open WebUI and SearXNG
- Display access URLs
- Show live logs

### 4. Access Services

**Open WebUI:**
- Local: http://localhost:12000
- NetBird: http://100.75.221.114:12000

**SearXNG:**
- Local: http://localhost:12001
- NetBird: http://100.75.221.114:12001
- API Test: http://localhost:12001/search?q=test&format=json

## Features

### Open WebUI
- Connected to host Ollama (your existing models)
- Full GPU access (all NVIDIA GPUs)
- Persistent data in `open-webui-data` volume
- Integrated with SearXNG for web search tools

### SearXNG
- Multiple search engines: Google, Bing, DuckDuckGo, Brave, Qwant
- JSON API for programmatic access
- No rate limiting (local use)
- Category support: general, news, science, IT
- Optimized for tool use (autocomplete disabled, metrics disabled)

## Installing Tools in Open WebUI

See [`tools/README.md`](tools/README.md) for detailed instructions on:
- Installing web search tools
- Configuring tool settings
- Testing tool functionality
- Troubleshooting

## Configuration

### SearXNG Settings

Edit `searxng/settings.yml` to customize:
- Search engines (enable/disable)
- Rate limiting
- Safe search level
- Language preferences
- Categories

After changes:
```bash
docker-compose restart searxng
```

### Open WebUI Settings

Environment variables in `docker-compose.yml`:
- `OLLAMA_BASE_URL`: Ollama endpoint (default: host.docker.internal:11434)

## Management Commands

**Start services:**
```bash
./start.sh
# or
docker-compose up -d
```

**Stop services:**
```bash
docker-compose down
```

**View logs:**
```bash
docker-compose logs -f
# or specific service
docker-compose logs -f open-webui
docker-compose logs -f searxng
```

**Restart services:**
```bash
docker-compose restart
```

**Update images:**
```bash
docker-compose pull
docker-compose up -d
```

## Data Persistence

### Open WebUI Data
Location: `open-webui-data` Docker volume

**Backup:**
```bash
docker run --rm -v open-webui-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/open-webui-backup.tar.gz -C /data .
```

**Restore:**
```bash
docker run --rm -v open-webui-data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/open-webui-backup.tar.gz -C /data
```

### SearXNG Configuration
Location: `./searxng/settings.yml` (bind mount)

Configuration changes persist automatically.

## Troubleshooting

### Services won't start

**Check Ollama:**
```bash
curl http://localhost:11434/api/tags
```

**Check network:**
```bash
docker network inspect trollama-network
```

**View logs:**
```bash
docker-compose logs
```

### SearXNG not accessible from tools

**Verify container names:**
```bash
docker ps | grep -E "open-webui|searxng"
```

**Test SearXNG API:**
```bash
docker exec open-webui curl http://searxng:8080/search?q=test&format=json
```

### Open WebUI can't connect to Ollama

**Check host.docker.internal:**
```bash
docker exec open-webui ping -c 1 host.docker.internal
docker exec open-webui curl http://host.docker.internal:11434/api/tags
```

### GPU not accessible

**Check NVIDIA runtime:**
```bash
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

**Verify compose GPU config:**
```bash
docker inspect open-webui | grep -A 10 DeviceRequests
```

## Network Details

### Ports
- **12000**: Open WebUI (host → container 8080)
- **12001**: SearXNG (host → container 8080)

### Networks
- **trollama-network**: Shared external network
  - Allows communication with fastapi-service, discord-bot, etc.
  - Created by main docker-compose.yml

### Firewall Rules
```bash
# View current rules
sudo ufw status

# Allow Open WebUI (NetBird network only)
sudo ufw allow from 100.64.0.0/10 to any port 12000 proto tcp comment 'OpenWebUI'

# Allow SearXNG (NetBird network only)
sudo ufw allow from 100.64.0.0/10 to any port 12001 proto tcp comment 'SearXNG'
```

## Security Notes

1. **SearXNG Secret**: Auto-generated on first run, stored in env var
2. **Network Isolation**: Services only accessible via NetBird VPN (100.64.0.0/10)
3. **Rate Limiting**: Disabled for local use (can be enabled in settings.yml)
4. **GPU Access**: Limited to open-webui container only

## Updating

### Update Open WebUI
```bash
docker-compose pull open-webui
docker-compose up -d open-webui
```

### Update SearXNG
```bash
docker-compose pull searxng
docker-compose up -d searxng
```

### Update Tools
1. Edit tool files in `tools/`
2. In Open WebUI: Workspace → Tools → Edit tool → Paste updated code

## Performance Tips

1. **SearXNG Response Time**:
   - First query: ~2-5s (cold start)
   - Subsequent: ~0.5-2s

2. **Open WebUI with Large Models**:
   - Uses all available GPUs
   - Memory managed by Ollama
   - See [claude-dgx-spark-research.md](../claude-dgx-spark-research.md) for DGX Spark specifics

3. **Tool Execution Time**:
   - Simple search: ~2-5s
   - Iterative research: ~10-30s (depends on page count)

## Support

For issues:
1. Check logs: `docker-compose logs`
2. Verify connectivity: test URLs above
3. Review tool configuration in Open WebUI
4. See [TOOL_FIX_GUIDE.md](../TOOL_FIX_GUIDE.md) for tool-specific issues

## Related Documentation

- [Tool Installation Guide](tools/README.md)
- [DGX Spark Research](../claude-dgx-spark-research.md)
- [Tool Fix Guide](../TOOL_FIX_GUIDE.md)
- [Main Project README](../README.md)
