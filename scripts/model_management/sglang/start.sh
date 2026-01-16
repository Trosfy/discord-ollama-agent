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
echo "Starting SGLang Eagle3 (gpt-oss-120b)"
echo "================================================"

# Enable swap and disable earlyoom during startup
echo "[1/5] Enabling swap for MoE weight shuffling..."
# Use absolute paths for system commands (ensures compatibility when invoked via SSH from container)
SWAPON_CMD=$(command -v swapon || echo "/usr/sbin/swapon")
sudo "$SWAPON_CMD" -a
SWAP_SIZE=$(free -h | awk '/Swap:/ {print $2}')
echo "Swap enabled: $SWAP_SIZE available"

echo "[2/5] Disabling earlyoom during MoE shuffling..."
SYSTEMCTL_CMD=$(command -v systemctl || echo "/usr/bin/systemctl")
sudo "$SYSTEMCTL_CMD" stop earlyoom
echo "Earlyoom disabled"

# Flush buffer cache to maximize available memory for model loading
echo "[3/5] Flushing buffer cache..."
sync
sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'
sleep 2
FREE_MEM=$(free -g | awk '/^Mem:/ {print $7}')
echo "Buffer cache flushed - Available memory: ${FREE_MEM}GB"

# Start SGLang container
echo "[4/5] Starting SGLang container..."
docker compose -f "$SGLANG_DIR/docker-compose.yml" up -d sglang-server
echo "SGLang container started"

# Monitor startup (wait for MoE shuffling to complete - ~5 minutes)
echo "[5/5] Monitoring startup (MoE weight shuffling ~5 minutes)..."
echo "This is silent - no logs during shuffling phase"

START_TIME=$(date +%s)
TIMEOUT=720  # 12 minutes timeout

while true; do
    ELAPSED=$(($(date +%s) - START_TIME))

    # Check if container is still running
    if ! docker ps --filter "name=trollama-sglang" --format "{{.Names}}" | grep -q "trollama-sglang"; then
        echo "Container died during startup"
        exit 1
    fi

    # Check container health
    HEALTH=$(docker inspect trollama-sglang --format='{{.State.Health.Status}}' 2>/dev/null || echo "none")

    if [ "$HEALTH" = "healthy" ]; then
        echo "SGLang is healthy and ready!"
        break
    fi

    # Show progress every 30 seconds
    if [ $((ELAPSED % 30)) -eq 0 ]; then
        MEM=$(docker stats trollama-sglang --no-stream --format "{{.MemUsage}}" | cut -d'/' -f1)
        echo "  [$ELAPSED s] Memory: $MEM | Status: $HEALTH"
    fi

    # Timeout check
    if [ $ELAPSED -ge $TIMEOUT ]; then
        echo "Startup timeout after 10 minutes - may still be initializing"
        break
    fi

    sleep 5
done

# Re-enable earlyoom after startup completes
echo ""
echo "Re-enabling earlyoom..."
sudo "$SYSTEMCTL_CMD" start earlyoom
echo "Earlyoom re-enabled"

# Disable swap to prevent thermal issues (model is already in GPU memory)
echo ""
echo "Disabling swap to prevent thermal issues..."
SWAP_USED=$(free -h | awk '/Swap:/ {print $3}')
echo "  Current swap usage: $SWAP_USED (will be moved back to RAM)"
SWAPOFF_CMD=$(command -v swapoff || echo "/usr/sbin/swapoff")
sudo "$SWAPOFF_CMD" -a
echo "Swap disabled - model is in GPU memory and won't be affected"
echo "  Note: This prevents thermal issues from swap I/O (see DGX Spark forum)"

echo ""
echo "================================================"
echo "SGLang startup complete!"
echo "Endpoint: http://localhost:30000"
echo "Model: gpt-oss-120b-eagle3 (84GB in GPU memory)"
echo "================================================"
