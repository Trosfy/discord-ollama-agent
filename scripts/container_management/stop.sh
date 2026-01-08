#!/bin/bash
# Trollama Shutdown Script
# Gracefully stops application services using docker-compose.app.yml
# IMPORTANT: Does NOT stop infrastructure services (admin, auth, web, logging, dynamodb)

set -e

# Get project root directory (two levels up from this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Change to project root for docker-compose commands
cd "$PROJECT_ROOT"

echo "=================================================="
echo "🛑 Stopping Trollama Application Services"
echo "=================================================="
echo ""

# Load environment variables to determine if SGLang is in use
if [ -f .env ]; then
    export $(grep -v '^#' .env | sed 's/#.*$//' | xargs)
fi

VRAM_PROFILE=${VRAM_PROFILE:-conservative}

echo "VRAM Profile: $VRAM_PROFILE"
echo ""

# Step 1: Stop SGLang with custom script first (if performance profile and running)
if [ "$VRAM_PROFILE" = "performance" ]; then
    if docker ps --filter "name=trollama-sglang" --format "{{.Names}}" | grep -q "trollama-sglang"; then
        echo "Stopping SGLang backend..."
        ./scripts/model_management/stop_sglang.sh
        echo ""
    else
        echo "ℹ️  SGLang container not running, skipping"
        echo ""
    fi
fi

# Step 2: Stop all application services (fastapi, discord-bot)
echo "Stopping application services..."
docker compose -f docker-compose.app.yml down

echo ""
echo "=================================================="
echo "✅ Application Services Stopped"
echo "=================================================="
echo ""
echo "ℹ️  Infrastructure services remain running:"
echo "   - Admin service (API for dashboard)"
echo "   - Auth service (authentication)"
echo "   - Web service (admin dashboard UI)"
echo "   - Logging service (centralized logs)"
echo "   - DynamoDB (database)"
echo ""
