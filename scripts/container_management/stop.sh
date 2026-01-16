#!/bin/bash
# Trollama Shutdown Script
# Gracefully stops application services using docker-compose.app.yml
# IMPORTANT: Does NOT stop infrastructure services (admin, auth, web, logging, dynamodb)
#
# SGLang is managed separately via: ./scripts/model_management/sglang/stop.sh

set -e

# Get project root directory (two levels up from this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Change to project root for docker-compose commands
cd "$PROJECT_ROOT"

echo "=================================================="
echo "Stopping Trollama Application Services"
echo "=================================================="
echo ""

# Stop all application services (troise-ai, discord-bot)
echo "Stopping application services..."
docker compose -f docker-compose.app.yml down

echo ""
echo "=================================================="
echo "Application Services Stopped"
echo "=================================================="
echo ""
echo "Infrastructure services remain running:"
echo "  - Admin service (API for dashboard)"
echo "  - Auth service (authentication)"
echo "  - Web service (admin dashboard UI)"
echo "  - Logging service (centralized logs)"
echo "  - DynamoDB (database)"
echo ""
echo "To stop SGLang (if running):"
echo "  ./scripts/model_management/sglang/stop.sh"
echo ""
