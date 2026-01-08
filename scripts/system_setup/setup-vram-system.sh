#!/bin/bash
# VRAM Orchestrator System Setup for DGX Spark
# Run with: sudo bash setup-vram-system.sh

set -e  # Exit on error

echo "=========================================="
echo "VRAM Orchestrator System Setup"
echo "DGX Spark (Grace Blackwell) Configuration"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root: sudo bash setup-vram-system.sh"
    exit 1
fi

echo "✅ Running as root"
echo ""

# 1. Install earlyoom
echo "📦 [1/5] Installing earlyoom..."
if command -v earlyoom &> /dev/null; then
    echo "✅ earlyoom already installed ($(earlyoom -v))"
else
    apt update -qq
    apt install -y earlyoom
    echo "✅ earlyoom installed"
fi

# Configure earlyoom
echo "⚙️  Configuring earlyoom (act when <10% memory available)..."
cat > /etc/default/earlyoom << 'EOF'
# earlyoom configuration for DGX Spark
# Act when memory drops below 10%, prefer to kill processes using >90% memory
EARLYOOM_ARGS="-m 10 -s 90 -r 60"
EOF

systemctl enable earlyoom
systemctl restart earlyoom
echo "✅ earlyoom configured and started"
echo ""

# 2. Configure kernel tuning
echo "⚙️  [2/5] Configuring kernel parameters..."
cat > /etc/sysctl.d/99-llm-vram.conf << 'EOF'
# Kernel tuning for LLM workloads on DGX Spark
# Optimized for large memory usage and unified memory architecture

# Minimize swapping (prefer to keep data in RAM)
vm.swappiness = 10

# Reduce cache pressure (don't evict cached data too aggressively)
vm.vfs_cache_pressure = 50

# Conservative memory overcommit (don't allow unrealistic allocations)
vm.overcommit_memory = 0

# Disable automatic NUMA balancing (Grace-Blackwell has specific NUMA behavior)
kernel.numa_balancing = 0
EOF

sysctl -p /etc/sysctl.d/99-llm-vram.conf
echo "✅ Kernel parameters configured"
echo ""

# 3. Configure Ollama (if service exists)
echo "⚙️  [3/5] Configuring Ollama environment..."
if systemctl list-unit-files | grep -q ollama.service; then
    mkdir -p /etc/systemd/system/ollama.service.d

    cat > /etc/systemd/system/ollama.service.d/vram-override.conf << 'EOF'
[Service]
# VRAM orchestration settings for multi-model hosting
Environment="OLLAMA_MAX_LOADED_MODELS=3"
Environment="OLLAMA_NUM_PARALLEL=4"
Environment="OLLAMA_KEEP_ALIVE=10m"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"
EOF

    systemctl daemon-reload
    echo "✅ Ollama environment configured (restart Ollama to apply: sudo systemctl restart ollama)"
else
    echo "⚠️  Ollama service not found - skipping Ollama configuration"
fi
echo ""

# 4. Configure systemd journal (log retention)
echo "⚙️  [4/6] Configuring systemd journal log retention..."
if [ -f /etc/systemd/journald.conf ]; then
    # Backup original config
    cp /etc/systemd/journald.conf /etc/systemd/journald.conf.backup

    # Configure journal limits
    cat > /etc/systemd/journald.conf.d/99-log-retention.conf << 'EOF'
[Journal]
# Limit journal disk usage for 24/7 operation
SystemMaxUse=1G
SystemKeepFree=2G
SystemMaxFileSize=100M
MaxRetentionSec=1month
Compress=yes
EOF

    mkdir -p /etc/systemd/journald.conf.d
    systemctl restart systemd-journald
    echo "✅ Systemd journal configured (1GB max, 1 month retention)"
else
    echo "⚠️  journald.conf not found - skipping journal configuration"
fi
echo ""

# 5. Grant sudo permissions for cache flushing
echo "⚙️  [5/6] Granting sudo permissions for cache flushing..."
# Determine the user running the FastAPI service
FASTAPI_USER="${SUDO_USER:-$USER}"
if [ "$FASTAPI_USER" = "root" ]; then
    echo "⚠️  Cannot determine FastAPI user. Please manually configure sudo for your service user."
    echo "    Add this line to /etc/sudoers.d/vram-cache:"
    echo "    your-user ALL=(ALL) NOPASSWD: /bin/sh -c sync; echo 3 > /proc/sys/vm/drop_caches"
else
    cat > /etc/sudoers.d/vram-cache << EOF
# Allow FastAPI service to flush buffer cache for VRAM orchestrator
$FASTAPI_USER ALL=(ALL) NOPASSWD: /bin/sh -c sync; echo 3 > /proc/sys/vm/drop_caches
EOF
    chmod 0440 /etc/sudoers.d/vram-cache
    echo "✅ Cache flushing permissions granted to user: $FASTAPI_USER"
fi
echo ""

# 6. Verify configuration
echo "🔍 [6/6] Verifying configuration..."
echo ""

echo "earlyoom status:"
systemctl status earlyoom --no-pager | grep -E "(Active|Main PID)" || true
echo ""

echo "Kernel parameters:"
sysctl vm.swappiness vm.vfs_cache_pressure vm.overcommit_memory kernel.numa_balancing
echo ""

echo "PSI support:"
if [ -f /proc/pressure/memory ]; then
    echo "✅ PSI enabled"
    cat /proc/pressure/memory
else
    echo "❌ PSI not available (kernel might not support it)"
fi
echo ""

echo "Systemd journal configuration:"
if [ -f /etc/systemd/journald.conf.d/99-log-retention.conf ]; then
    echo "✅ Journal log retention configured"
    journalctl --disk-usage
else
    echo "⚠️  Journal log retention not configured"
fi
echo ""

echo "Current memory status:"
free -h
echo ""

echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Restart Ollama if configured: sudo systemctl restart ollama"
echo "2. Start your FastAPI service with VRAM orchestrator"
echo "3. Monitor logs: tail -f logs/fastapi.log | grep VRAM"
echo "4. Check VRAM status: curl http://localhost:8000/vram/status"
echo ""
echo "System is now optimized for VRAM orchestration on DGX Spark!"
