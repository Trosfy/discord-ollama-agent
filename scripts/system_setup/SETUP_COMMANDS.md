# VRAM Orchestrator Setup Commands

Quick reference for setting up the VRAM orchestrator on DGX Spark.

## 🚀 Quick Setup (All-in-One)

```bash
cd /home/trosfy/projects/discord-ollama-agent

# 1. Run the automated setup script (requires sudo)
sudo bash setup-vram-system.sh

# 2. Verify the configuration
bash verify-vram-setup.sh

# 3. Restart Ollama to apply new settings
sudo systemctl restart ollama

# 4. Start your FastAPI service
cd fastapi-service
python -m app.main
```

## 📋 Step-by-Step Manual Setup

If you prefer to run commands individually:

### 1. Configure systemd journal log retention (24/7 operation)
```bash
# Create journal configuration directory
sudo mkdir -p /etc/systemd/journald.conf.d

# Configure log limits
sudo tee /etc/systemd/journald.conf.d/99-log-retention.conf << 'EOF'
[Journal]
# Limit journal disk usage for 24/7 operation
SystemMaxUse=1G
SystemKeepFree=2G
SystemMaxFileSize=100M
MaxRetentionSec=1month
Compress=yes
EOF

# Restart journald to apply
sudo systemctl restart systemd-journald

# Verify disk usage
sudo journalctl --disk-usage
```

### 2. Install earlyoom
```bash
sudo apt update
sudo apt install -y earlyoom

# Configure
sudo tee /etc/default/earlyoom << 'EOF'
EARLYOOM_ARGS="-m 10 -s 90 -r 60"
EOF

sudo systemctl enable earlyoom
sudo systemctl restart earlyoom
sudo systemctl status earlyoom
```

### 3. Configure Kernel Tuning
```bash
sudo tee /etc/sysctl.d/99-llm-vram.conf << 'EOF'
vm.swappiness = 10
vm.vfs_cache_pressure = 50
vm.overcommit_memory = 0
kernel.numa_balancing = 0
EOF

sudo sysctl -p /etc/sysctl.d/99-llm-vram.conf
```

### 4. Configure Ollama
```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d

sudo tee /etc/systemd/system/ollama.service.d/vram-override.conf << 'EOF'
[Service]
Environment="OLLAMA_MAX_LOADED_MODELS=3"
Environment="OLLAMA_NUM_PARALLEL=4"
Environment="OLLAMA_KEEP_ALIVE=10m"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"
EOF

sudo systemctl daemon-reload
sudo systemctl restart ollama
```

### 5. Grant Sudo for Cache Flushing
```bash
# Replace 'trosfy' with your username
sudo tee /etc/sudoers.d/vram-cache << 'EOF'
trosfy ALL=(ALL) NOPASSWD: /bin/sh -c sync; echo 3 > /proc/sys/vm/drop_caches
EOF

sudo chmod 0440 /etc/sudoers.d/vram-cache
```

## 📊 Log Management (24/7 Operation)

Your system has three layers of log management:

### Application Logs
- **Managed by**: `monitoring-service` container
- **Retention**: 2 days (configurable via `LOG_RETENTION_DAYS`)
- **Cleanup**: Automatic every 6 hours
- **Location**: `./logs/` (date-organized directories)

### Docker Container Logs
- **Managed by**: Docker json-file driver
- **Retention**: 3 files × 10MB per container = 30MB max
- **Cleanup**: Automatic rotation by Docker
- **View with**: `docker logs <container-name>`

### Host System Logs (ollama, earlyoom)
- **Managed by**: systemd journal
- **Retention**: 1 month or 1GB max
- **Cleanup**: Automatic by journald
- **View with**: `sudo journalctl -u <service-name>`

### Check Log Disk Usage
```bash
# Application logs
du -sh logs/

# Docker container logs
docker ps -q | xargs docker inspect --format='{{.LogPath}}' | xargs du -sh

# System journal logs
sudo journalctl --disk-usage

# Clean up old journal logs manually if needed
sudo journalctl --vacuum-time=7d
sudo journalctl --vacuum-size=500M
```

## 🔍 Verification Commands

### Check System Status
```bash
# Run full verification
bash verify-vram-setup.sh

# Check individual components
systemctl status earlyoom
systemctl status ollama
sysctl vm.swappiness vm.vfs_cache_pressure
cat /proc/pressure/memory
free -h

# Check journal log configuration
sudo journalctl --disk-usage
cat /etc/systemd/journald.conf.d/99-log-retention.conf
```

### Check VRAM Orchestrator
```bash
# Health check
curl http://localhost:8000/health | python3 -m json.tool

# VRAM status
curl http://localhost:8000/vram/status | python3 -m json.tool

# PSI metrics
curl http://localhost:8000/vram/psi | python3 -m json.tool

# Test cache flush
curl -X POST http://localhost:8000/vram/flush-cache
```

### Monitor Logs
```bash
# Watch VRAM orchestrator logs
tail -f fastapi-service/logs/fastapi.log | grep VRAM

# Watch earlyoom logs
sudo journalctl -u earlyoom -f

# Watch for memory pressure
watch -n 2 'cat /proc/pressure/memory'
```

## 🧪 Test VRAM Orchestration

### Test with Ollama Models
```bash
# Check what's loaded
ollama ps

# Load a model (triggers orchestration)
ollama run gpt-oss:20b "test"

# Check VRAM status
curl http://localhost:8000/vram/status | python3 -m json.tool

# Load another model (should trigger eviction if needed)
ollama run magistral:24b "test"

# Verify eviction happened
curl http://localhost:8000/vram/status | python3 -m json.tool
```

### Manual Model Management
```bash
# Manually unload a model
curl -X POST http://localhost:8000/vram/unload/gpt-oss:20b

# Flush buffer cache
curl -X POST http://localhost:8000/vram/flush-cache

# Check PSI
curl http://localhost:8000/vram/psi
```

## 🧹 Troubleshooting

### earlyoom not killing processes
```bash
# Check configuration
cat /etc/default/earlyoom
systemctl status earlyoom

# Restart with verbose logging
sudo systemctl restart earlyoom
sudo journalctl -u earlyoom -f
```

### Cache flush permission denied
```bash
# Verify sudo configuration
sudo cat /etc/sudoers.d/vram-cache

# Test manually
sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'
```

### Ollama not respecting VRAM limits
```bash
# Check Ollama environment
systemctl show ollama | grep Environment

# Restart Ollama
sudo systemctl restart ollama

# Verify loaded models
ollama ps

# Check memory usage
curl http://localhost:8000/vram/status
```

### PSI not available
```bash
# Check if PSI is enabled in kernel
cat /proc/pressure/memory

# If not available, kernel needs CONFIG_PSI=y
# (should be enabled by default on modern kernels)
```

## 🔄 Rollback Commands

If you need to undo the configuration:

```bash
# Remove earlyoom
sudo systemctl stop earlyoom
sudo systemctl disable earlyoom
sudo apt remove earlyoom

# Remove kernel tuning
sudo rm /etc/sysctl.d/99-llm-vram.conf
sudo sysctl -p

# Remove Ollama configuration
sudo rm /etc/systemd/system/ollama.service.d/vram-override.conf
sudo systemctl daemon-reload
sudo systemctl restart ollama

# Remove sudo permissions
sudo rm /etc/sudoers.d/vram-cache
```

## 📊 Expected Results

After setup, you should see:
- ✅ earlyoom running and monitoring
- ✅ PSI metrics showing low values (< 20%)
- ✅ Kernel parameters tuned for LLM workloads
- ✅ Ollama configured for multi-model hosting
- ✅ VRAM orchestrator endpoints responding
- ✅ Background monitoring logging every 30s

## 🆘 Support

If issues persist:
1. Check logs: `tail -f fastapi-service/logs/fastapi.log`
2. Run tests: `cd fastapi-service && uv run pytest tests/test_vram/ -v`
3. Review implementation: [VRAM_ORCHESTRATOR_IMPLEMENTATION.md](VRAM_ORCHESTRATOR_IMPLEMENTATION.md)
