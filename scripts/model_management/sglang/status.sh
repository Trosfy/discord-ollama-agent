#!/bin/bash

echo "================================================"
echo "SGLang Status"
echo "================================================"

# Check container status
if docker ps --filter "name=trollama-sglang" --format "{{.Names}}" | grep -q "trollama-sglang"; then
    echo "Status: Running"

    # Get health status
    HEALTH=$(docker inspect trollama-sglang --format='{{.State.Health.Status}}' 2>/dev/null || echo "none")
    echo "Health: $HEALTH"

    # Get memory usage
    echo ""
    docker stats trollama-sglang --no-stream --format "table {{.Container}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}"

    echo ""
    echo "Endpoint: http://localhost:30000"
    echo "Latest logs:"
    docker logs trollama-sglang --tail 5
else
    echo "Status: Not running"
fi

echo "================================================"
