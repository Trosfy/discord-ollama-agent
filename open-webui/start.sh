#!/usr/bin/env bash
set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="/home/trosfy/projects/discord-ollama-agent/open-webui/docker-compose.yml"
NETBIRD_IP="100.75.221.114"
OPENWEBUI_PORT="12000"
SEARXNG_PORT="12001"

# Cleanup handler
cleanup() {
  echo -e "\n${YELLOW}Signal received; stopping services...${NC}"
  docker-compose -f "${COMPOSE_FILE}" down
  exit 0
}
trap cleanup INT TERM HUP QUIT

# Ensure Docker CLI and daemon are available
if ! docker info >/dev/null 2>&1; then
  echo -e "${RED}Error: Docker daemon not reachable.${NC}" >&2
  exit 1
fi

# Ensure docker-compose is available
if ! command -v docker-compose >/dev/null 2>&1; then
  echo -e "${RED}Error: docker-compose not found. Please install it.${NC}" >&2
  exit 1
fi

# Check if host Ollama is running
echo "Checking Ollama connectivity..."
if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo -e "${RED}Warning: Host Ollama not detected on port 11434${NC}" >&2
  echo -e "${YELLOW}Make sure Ollama is running before starting Open WebUI${NC}" >&2
  read -p "Continue anyway? (y/N) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

# Generate SearXNG secret if not exists
if [ -z "${SEARXNG_SECRET:-}" ]; then
  export SEARXNG_SECRET=$(openssl rand -hex 32)
  echo -e "${GREEN}Generated SearXNG secret key${NC}"
fi

# Check if trollama-network exists
if ! docker network inspect trollama-network >/dev/null 2>&1; then
  echo -e "${YELLOW}Warning: trollama-network does not exist${NC}"
  echo "Creating trollama-network..."
  docker network create trollama-network
fi

# Start services
echo -e "${GREEN}Starting Open WebUI and SearXNG...${NC}"
docker-compose -f "${COMPOSE_FILE}" up -d

# Wait for services to be healthy
echo "Waiting for services to start..."
sleep 5

# Check service status
echo -e "\n${GREEN}===== Service Status =====${NC}"
docker-compose -f "${COMPOSE_FILE}" ps

# Test SearXNG API
echo -e "\n${GREEN}Testing SearXNG API...${NC}"
if curl -sf "http://localhost:${SEARXNG_PORT}/search?q=test&format=json" >/dev/null 2>&1; then
  echo -e "${GREEN}✅ SearXNG API is responding${NC}"
else
  echo -e "${YELLOW}⚠️  SearXNG may still be starting up${NC}"
fi

# Display access information
echo -e "\n${GREEN}===== Access URLs =====${NC}"
echo ""
echo -e "${GREEN}Open WebUI:${NC}"
echo "   Local:   http://localhost:${OPENWEBUI_PORT}"
echo "   NetBird: http://${NETBIRD_IP}:${OPENWEBUI_PORT}"
echo ""
echo -e "${GREEN}SearXNG:${NC}"
echo "   Local:   http://localhost:${SEARXNG_PORT}"
echo "   NetBird: http://${NETBIRD_IP}:${SEARXNG_PORT}"
echo "   API:     http://localhost:${SEARXNG_PORT}/search?q=test&format=json"
echo ""
echo -e "${GREEN}Ollama:${NC}"
echo "   Connected to host Ollama (your existing models)"
echo ""
echo -e "${GREEN}GPU Access:${NC} Enabled (all NVIDIA GPUs)"
echo ""
echo -e "${GREEN}Anti-WAF Features:${NC}"
echo "   ✅ User-Agent rotation (7 agents)"
echo "   ✅ Custom browser headers"
echo "   ✅ Engine-level delays & retries"
echo "   ✅ Connection pooling (100 connections)"
echo "   ✅ HTTP/2 enabled"
echo ""
echo -e "${GREEN}Active Search Engines:${NC}"
echo "   • Google, Bing, Brave"
echo "   • Wikipedia, GitHub, Wikidata, ArXiv"
echo "   • DuckDuckGo (with aggressive retry)"
echo ""
echo -e "${GREEN}Available Tools (External Functions):${NC}"
echo "   1. Web Search (tools/web_search_tool.py)"
echo "      └─ Fast multi-engine search with anti-WAF protection"
echo "      └─ Default: SearXNG enabled, 5 results, 15s timeout"
echo ""
echo "   2. Iterative Web Research (tools/iterative_websearch_tool.py)"
echo "      └─ Advanced research with full page content analysis"
echo "      └─ Requires: Ollama embedding model (qwen3-embedding:4b)"
echo "      └─ Features: Semantic search, MMR ranking, diverse sources"
echo ""
echo -e "${GREEN}Available Functions (Filters/Middleware):${NC}"
echo "   1. Current Date Context (functions/date_context_filter.py)"
echo "      └─ Auto-injects current date/time into all conversations"
echo "      └─ Configurable timezone (default: UTC)"
echo "      └─ Format: 'Monday, 2025-12-21 03:30:00 UTC'"
echo "      └─ Runs transparently on every request"
echo ""
echo -e "${YELLOW}Installation:${NC}"
echo "   Tools:     Workspace → Tools → Add Tool → Paste code"
echo "   Functions: Workspace → Functions → Add Function → Paste code"
echo "   Location:  open-webui/tools/ and open-webui/functions/"
echo "   Verify:    searxng_url should be http://searxng:8080"
echo ""
echo -e "Press ${YELLOW}Ctrl+C${NC} to stop all services."
echo ""

# Monitor logs
echo -e "${GREEN}===== Service Logs (Ctrl+C to exit) =====${NC}"
docker-compose -f "${COMPOSE_FILE}" logs -f
