#!/bin/bash
# Run router service tests
# This script ensures proper test environment without polluting production containers

set -e

echo "🧪 Running Router Service Tests..."
echo ""

# Check if containers are running
if ! docker-compose ps | grep -q "ollama-fastapi.*Up"; then
    echo "⚠️  FastAPI service not running. Starting dependencies..."
    docker-compose up -d dynamodb-local logging-service
    sleep 5
fi

# Run tests using docker-compose test configuration
docker-compose -f docker-compose.yml -f docker-compose.test.yml run --rm fastapi-service-test

echo ""
echo "✅ Tests complete!"
