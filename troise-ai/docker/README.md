# TROISE AI - Web Tools Docker Setup

## Services

| Service | Port | Purpose |
|---------|------|---------|
| SearXNG | 8080 | Web search aggregator (Google, Bing, Brave, DDG) |
| Browserless | 3000 | Headless Chrome for JS-rendered page fetching |

## Quick Start

```bash
cd docker

# Generate SearXNG secret key
sed -i "s/change-me-in-production-use-openssl-rand-hex-32/$(openssl rand -hex 32)/" searxng/settings.yml

# Start services
docker compose up -d

# Check status
docker compose ps
```

## API Usage

### SearXNG Search
```bash
curl "http://localhost:8080/search?q=python+tutorial&format=json"
```

### Browserless Fetch
```bash
# Get page content (with JS rendering)
curl -X POST "http://localhost:3000/content" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

# Get page as PDF
curl -X POST "http://localhost:3000/pdf" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}' > page.pdf

# Screenshot
curl -X POST "http://localhost:3000/screenshot" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}' > screenshot.png
```

## Python Integration

```python
import aiohttp

# Search
async with aiohttp.ClientSession() as session:
    async with session.get(
        "http://localhost:8080/search",
        params={"q": "query", "format": "json"}
    ) as resp:
        results = await resp.json()

# Fetch with JS rendering
async with aiohttp.ClientSession() as session:
    async with session.post(
        "http://localhost:3000/content",
        json={"url": "https://example.com"}
    ) as resp:
        html = await resp.text()
```

## Memory Usage

- SearXNG: ~100-200MB
- Browserless: ~500MB-2GB (depends on concurrent sessions)

## Troubleshooting

```bash
# View logs
docker compose logs -f searxng
docker compose logs -f browserless

# Restart services
docker compose restart

# Full reset
docker compose down
docker compose up -d
```
