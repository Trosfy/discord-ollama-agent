#!/bin/bash
# Trollama Startup Script
# Starts application services (TROISE AI, Discord bot)
#
# SGLang is managed separately via: ./scripts/model_management/sglang/

set -e

# Get project root directory (two levels up from this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Change to project root for docker-compose commands
cd "$PROJECT_ROOT"

# Load environment variables
if [ -f .env ]; then
    # Strip inline comments and export variables
    export $(grep -v '^#' .env | sed 's/#.*$//' | xargs)
fi

echo "=================================================="
echo "Starting Trollama Agent"
echo "=================================================="
echo ""

echo "Starting application services..."
docker compose -f docker-compose.app.yml up -d

echo ""
echo "=================================================="
echo "Trollama Agent Started"
echo "=================================================="
echo ""
echo "Services:"
echo "  TROISE AI:     http://localhost:8001"
echo "  Discord Bot:   Running"
echo ""
echo "Commands:"
echo "  View logs:     docker compose -f docker-compose.app.yml logs -f"
echo "  Stop apps:     ./scripts/container_management/stop.sh"
echo "  Check status:  docker compose -f docker-compose.app.yml ps"
echo ""
echo "SGLang (if needed):"
echo "  Start:   ./scripts/model_management/sglang/start.sh"
echo "  Stop:    ./scripts/model_management/sglang/stop.sh"
echo "  Status:  ./scripts/model_management/sglang/status.sh"
echo ""
