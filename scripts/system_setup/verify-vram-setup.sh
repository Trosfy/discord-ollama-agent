#!/bin/bash
# Verify VRAM Orchestrator System Configuration
# Run without sudo: bash verify-vram-setup.sh

echo "=========================================="
echo "VRAM System Configuration Verification"
echo "=========================================="
echo ""

# Check system info
echo "🖥️  System Information:"
echo "   Hostname: $(hostname)"
echo "   Kernel: $(uname -r)"
echo "   Architecture: $(uname -m)"
echo ""

# Check GPU
echo "🎮 GPU Information:"
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null || echo "   ⚠️  nvidia-smi failed (expected on unified memory)"
echo ""

# Check memory
echo "💾 Memory Status:"
free -h | head -2
echo ""

# Check PSI
echo "📊 PSI (Pressure Stall Information):"
if [ -f /proc/pressure/memory ]; then
    cat /proc/pressure/memory
else
    echo "   ❌ PSI not available"
fi
echo ""

# Check earlyoom
echo "🛡️  earlyoom Status:"
if command -v earlyoom &> /dev/null; then
    echo "   ✅ Installed: $(earlyoom -v 2>&1 | head -1)"
    systemctl is-active --quiet earlyoom && echo "   ✅ Service: Running" || echo "   ⚠️  Service: Not running"
else
    echo "   ❌ Not installed"
fi
echo ""

# Check kernel parameters
echo "⚙️  Kernel Parameters:"
if [ -f /etc/sysctl.d/99-llm-vram.conf ]; then
    echo "   ✅ Configuration file exists"
    echo "   Current values:"
    sysctl vm.swappiness vm.vfs_cache_pressure vm.overcommit_memory kernel.numa_balancing 2>/dev/null | sed 's/^/      /'
else
    echo "   ❌ Configuration file not found"
fi
echo ""

# Check Ollama
echo "🦙 Ollama Configuration:"
if systemctl list-unit-files | grep -q ollama.service; then
    if [ -f /etc/systemd/system/ollama.service.d/vram-override.conf ]; then
        echo "   ✅ VRAM configuration exists"
        echo "   Settings:"
        grep "Environment=" /etc/systemd/system/ollama.service.d/vram-override.conf | sed 's/^/      /'
    else
        echo "   ⚠️  VRAM configuration not found"
    fi
    systemctl is-active --quiet ollama && echo "   ✅ Service: Running" || echo "   ⚠️  Service: Not running"
else
    echo "   ⚠️  Ollama service not found"
fi
echo ""

# Check sudo permissions
echo "🔐 Sudo Permissions (cache flushing):"
if [ -f /etc/sudoers.d/vram-cache ]; then
    echo "   ✅ Configured"
    cat /etc/sudoers.d/vram-cache | sed 's/^/      /'
else
    echo "   ❌ Not configured"
fi
echo ""

# Check if FastAPI is running
echo "🚀 FastAPI Service:"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✅ Service responding"
    echo "   Health check:"
    curl -s http://localhost:8000/health | python3 -m json.tool | head -20 | sed 's/^/      /'
else
    echo "   ⚠️  Service not responding on localhost:8000"
fi
echo ""

# Test VRAM endpoints (if FastAPI is running)
if curl -s http://localhost:8000/vram/status > /dev/null 2>&1; then
    echo "🧠 VRAM Orchestrator Status:"
    curl -s http://localhost:8000/vram/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"   Loaded models: {len(data['loaded_models'])}\")
print(f\"   Memory usage: {data['memory']['model_usage_gb']:.1f}GB / {data['memory']['hard_limit_gb']:.0f}GB ({data['memory']['usage_pct']:.1f}%)\")
print(f\"   Available: {data['memory']['available_gb']:.1f}GB\")
print(f\"   PSI some: {data['memory']['psi_some_avg10']:.2f}%\")
print(f\"   PSI full: {data['memory']['psi_full_avg10']:.2f}%\")
" 2>/dev/null || echo "   ⚠️  Could not parse VRAM status"
else
    echo "🧠 VRAM Orchestrator:"
    echo "   ⚠️  Endpoints not available (FastAPI not running)"
fi
echo ""

echo "=========================================="
echo "📋 Setup Status Summary"
echo "=========================================="

# Count what's configured
configured=0
total=6

[ -f /etc/default/earlyoom ] && ((configured++))
[ -f /etc/sysctl.d/99-llm-vram.conf ] && ((configured++))
[ -f /etc/systemd/journald.conf.d/99-log-retention.conf ] && ((configured++))
[ -f /etc/systemd/system/ollama.service.d/vram-override.conf ] && ((configured++)) || true
[ -f /etc/sudoers.d/vram-cache ] && ((configured++))
command -v earlyoom &> /dev/null && ((configured++))

echo "Configured: $configured/$total components"
echo ""

if [ $configured -eq $total ]; then
    echo "✅ All system components configured!"
    echo "   Ready for production VRAM orchestration"
elif [ $configured -ge 3 ]; then
    echo "⚠️  Most components configured"
    echo "   Run: sudo bash setup-vram-system.sh"
else
    echo "❌ System configuration incomplete"
    echo "   Run: sudo bash setup-vram-system.sh"
fi
