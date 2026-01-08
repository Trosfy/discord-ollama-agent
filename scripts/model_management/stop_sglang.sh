#!/bin/bash
set -e

# Accept optional PROJECT_ROOT as first argument (for container invocation)
# If not provided, calculate from script location (for host invocation)
if [ -n "$1" ]; then
    PROJECT_ROOT="$1"
    echo "Using provided PROJECT_ROOT: $PROJECT_ROOT"
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
    echo "Calculated PROJECT_ROOT: $PROJECT_ROOT"
fi

echo "================================================"
echo "Stopping SGLang Eagle3"
echo "================================================"

cd "$PROJECT_ROOT"

# Check if container exists
if ! docker ps -a --filter "name=trollama-sglang" --format "{{.Names}}" | grep -q "trollama-sglang"; then
    echo "ℹ️  SGLang container not found"
    exit 0
fi

# Stop container
echo "Stopping SGLang container..."
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml --profile performance stop sglang-server

echo "✅ SGLang stopped"
echo "================================================"
