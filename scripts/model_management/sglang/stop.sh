#!/bin/bash
set -e

# Get the directory where this script is located
SGLANG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Accept optional PROJECT_ROOT as first argument (for container invocation)
# If not provided, calculate from script location (for host invocation)
if [ -n "$1" ]; then
    PROJECT_ROOT="$1"
    echo "Using provided PROJECT_ROOT: $PROJECT_ROOT"
else
    PROJECT_ROOT="$(cd "$SGLANG_DIR/../../.." && pwd)"
    echo "Calculated PROJECT_ROOT: $PROJECT_ROOT"
fi

echo "================================================"
echo "Stopping SGLang Eagle3"
echo "================================================"

# Check if container exists
if ! docker ps -a --filter "name=trollama-sglang" --format "{{.Names}}" | grep -q "trollama-sglang"; then
    echo "SGLang container not found"
    exit 0
fi

# Stop container
echo "Stopping SGLang container..."
docker compose -f "$SGLANG_DIR/docker-compose.yml" stop sglang-server

echo "SGLang stopped"
echo "================================================"
