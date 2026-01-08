#!/bin/bash
# Trollama Startup Script
# Automatically starts the correct services based on VRAM_PROFILE

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

VRAM_PROFILE=${VRAM_PROFILE:-conservative}

echo "=================================================="
echo "🚀 Starting Trollama Agent"
echo "=================================================="
echo ""
echo "VRAM Profile: $VRAM_PROFILE"
echo ""

# Check if sglang image is needed
if [ "$VRAM_PROFILE" = "performance" ]; then
    echo "⚠️  Performance profile requires SGLang backend"
    echo ""

    # Check if image exists
    if ! docker images | grep -q "lmsysorg/sglang.*spark"; then
        echo "📦 SGLang image not found. Pulling image..."
        echo "   (This is a large download and may take several minutes)"
        echo ""
        docker pull lmsysorg/sglang:spark
        echo ""
        echo "✅ Image pulled successfully"
        echo ""
    else
        echo "✅ SGLang image already exists"
        echo ""
    fi

    echo "🔧 Starting services with SGLang backend..."
    echo ""

    # Check if SGLang is already running
    if docker ps --filter "name=trollama-sglang" --format "{{.Names}}" | grep -q "trollama-sglang"; then
        HEALTH=$(docker inspect trollama-sglang --format='{{.State.Health.Status}}' 2>/dev/null || echo "none")
        echo "ℹ️  SGLang container already running (health: $HEALTH)"
        echo "   Skipping SGLang startup. To restart, use: ./scripts/model_management/stop_sglang.sh && ./scripts/model_management/start_sglang.sh"
        echo ""
    else
        # Start SGLang FIRST (other services depend on it)
        echo "Starting SGLang backend (this must be ready before other services)..."
        ./scripts/model_management/start_sglang.sh

        if [ $? -ne 0 ]; then
            echo "❌ SGLang startup failed"
            exit 1
        fi
        echo ""
    fi

    # Now start dependent services (FastAPI, Discord bot, etc.)
    echo "Starting dependent services (FastAPI, Discord bot, etc.)..."
    docker compose -f docker-compose.app.yml --profile performance up -d
    echo "✅ All services started"

elif [ "$VRAM_PROFILE" = "conservative" ] || [ "$VRAM_PROFILE" = "balanced" ]; then
    echo "🔧 Starting services with Ollama backend (no SGLang needed)..."
    docker compose -f docker-compose.app.yml up -d

else
    echo "❌ Unknown VRAM_PROFILE: $VRAM_PROFILE"
    echo "   Valid options: conservative, performance, balanced"
    exit 1
fi

echo ""
echo "=================================================="
echo "✅ Trollama Agent Started"
echo "=================================================="
echo ""
echo "Services:"
echo "  • FastAPI Service:  http://localhost:8001"
echo "  • Discord Bot:      Running"

if [ "$VRAM_PROFILE" = "performance" ]; then
    echo "  • SGLang Backend:   http://localhost:30000"
fi

echo ""
echo "Commands:"
echo "  • View app logs:         docker compose -f docker-compose.app.yml logs -f"
echo "  • Stop apps:             ./scripts/container_management/stop.sh"
echo "  • Check status:          docker compose -f docker-compose.app.yml ps"
if [ "$VRAM_PROFILE" = "performance" ]; then
    echo "  • SGLang status:         ./scripts/model_management/status_sglang.sh"
fi
echo ""
