# Container Actions Configuration Guide

## Overview

The admin service now supports **custom start/stop scripts** for Docker containers via a configuration-driven approach. This eliminates hardcoding and makes it easy to add complex startup sequences for specific containers.

## Architecture

### Components

1. **Configuration File**: `admin-service/app/config/container_actions.yaml`
   - Maps container names to custom scripts
   - Containers not listed use default `docker start/stop`

2. **Service**: `admin-service/app/services/container_action_service.py`
   - Loads YAML config at startup
   - Executes custom scripts OR falls back to docker commands
   - Handles timeout, error logging, and script execution

3. **API Integration**: `admin-service/app/api/system.py`
   - Start/stop endpoints now use `ContainerActionService`
   - Returns method used (`script` or `docker`) in response

4. **Frontend**: Slider toggles in admin dashboard
   - Each container has a slider toggle
   - Calls admin API to start/stop containers

## How It Works

### Request Flow

```
User toggles slider in dashboard
    ↓
Frontend calls POST /admin/system/docker/containers/{name}/start
    ↓
system.py validates container name
    ↓
ContainerActionService checks config:
    - If custom script defined → runs script with timeout
    - If not in config → runs `docker start {name}`
    ↓
Returns result with status, message, and method
```

### Example: SGLang Container

**Problem**: SGLang needs complex startup:
- Enable swap for MoE weight shuffling
- Disable earlyoom during startup
- Flush buffer cache
- Monitor health (waits ~5 minutes for model loading)
- Re-enable earlyoom after completion
- Disable swap after completion

**Solution**: Custom script in `container_actions.yaml`:

```yaml
containers:
  trollama-sglang:
    start_script: "./scripts/model_management/sglang/start.sh"
    stop_script: "./scripts/model_management/sglang/stop.sh"
    timeout: 720  # 12 minutes for model loading
```

### Example: Other Containers

All other containers (fastapi, discord-bot, dynamodb, etc.) automatically use default `docker start/stop` since they're not in the config.

## Adding Custom Scripts for New Containers

### Step 1: Create Scripts

Create your custom start/stop scripts in `scripts/<service>/`:

```bash
mkdir -p scripts/my_service
touch scripts/my_service/start.sh
touch scripts/my_service/stop.sh
chmod +x scripts/my_service/*.sh
```

### Step 2: Add to Config

Edit `admin-service/app/config/container_actions.yaml`:

```yaml
containers:
  trollama-my-service:
    start_script: "./scripts/my_service/start.sh"
    stop_script: "./scripts/my_service/stop.sh"
    description: "My custom service with special startup"
    timeout: 300  # 5 minutes
```

### Step 3: Restart Admin Service

```bash
docker restart trollama-admin
```

### Step 4: Test

```bash
# Via API
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8003/admin/system/docker/containers/trollama-my-service/start

# Via dashboard
# Navigate to admin dashboard and toggle the slider
```

## Configuration Schema

```yaml
containers:
  <container-name>:
    start_script: <path>        # Relative from project root
    stop_script: <path>         # Relative from project root
    status_script: <path>       # Optional, for health checks
    description: <text>         # Human-readable description
    timeout: <seconds>          # Script timeout (default: 300 for start, 60 for stop)
```

## Script Requirements

### Script Location
- Place scripts in `scripts/` directory
- Use relative paths from project root in config
- Scripts must be executable (`chmod +x`)

### Script Behavior
- **Exit Code 0**: Success
- **Exit Code Non-Zero**: Failure (logged as error)
- **stdout**: Captured and logged
- **stderr**: Captured and returned in error messages
- **Timeout**: Script killed if exceeds configured timeout

### Script Environment
- Working directory: Project root
- No environment variables passed by default
- Must handle all dependencies (sudo, docker, etc.)

## Master Start/Stop Scripts

You can also create master scripts that orchestrate multiple containers:

### Example: `start.sh`

```bash
#!/bin/bash
# Master startup script

echo "Starting core services..."
docker compose up -d trollama-dynamodb trollama-logging

echo "Starting application services..."
docker compose up -d trollama-fastapi trollama-discord-bot

echo "Starting SGLang (this will take ~5 minutes)..."
./scripts/model_management/sglang/start.sh

echo "Starting UI services..."
docker compose up -d trollama-streamlit trollama-open-webui

echo "All services started!"
```

### Integration with Admin API

To expose master scripts via API, add a new endpoint:

```python
@router.post("/docker/start-all")
async def start_all_services(admin_auth: Dict = Depends(require_admin)):
    """Start all services using master script."""
    result = subprocess.run(
        ["./start.sh"],
        cwd=str(Path(__file__).parent.parent.parent.parent),
        capture_output=True,
        text=True,
        timeout=900  # 15 minutes
    )
    
    if result.returncode == 0:
        return {"status": "success", "message": "All services started"}
    else:
        raise HTTPException(status_code=500, detail=result.stderr)
```

## Benefits

✅ **No Hardcoding**: All container-specific logic in config file
✅ **DRY Principle**: Single service handles all containers
✅ **Extensible**: Add new containers without modifying code
✅ **Backward Compatible**: Containers without custom scripts use docker commands
✅ **Complex Startup Support**: Scripts can do anything (swap, caching, health monitoring)
✅ **Master Scripts**: Can orchestrate multiple containers in sequence
✅ **Error Handling**: Timeout, logging, and error propagation built-in
✅ **Audit Trail**: Logs which admin user performed action and method used

## Troubleshooting

### Script Not Found

**Error**: `Script not found: ./scripts/my_service/start.sh`

**Fix**:
1. Check file exists: `ls scripts/my_service/start.sh`
2. Check path is relative from project root
3. Ensure script is executable: `chmod +x scripts/my_service/start.sh`

### Script Timeout

**Error**: `Script timeout after 300 seconds`

**Fix**: Increase timeout in config:

```yaml
containers:
  trollama-my-service:
    timeout: 600  # 10 minutes
```

### Permission Denied

**Error**: `Permission denied`

**Fix**:
1. Make script executable: `chmod +x scripts/my_service/start.sh`
2. If script needs sudo, ensure admin service has sudo access
3. Consider using docker group permissions instead of sudo

### Container Not in Whitelist

**Error**: `Container 'my-container' not in allowed list (must start with trollama-)`

**Fix**: Ensure container name starts with `trollama-` prefix:

```yaml
containers:
  trollama-my-service:  # ✓ Correct
    ...

  my-service:  # ✗ Wrong - missing prefix
    ...
```

## Security Considerations

1. **Whitelist Validation**: Only containers with `trollama-` prefix allowed
2. **Command Injection Prevention**: Container names validated with regex `^[a-zA-Z0-9_-]+$`
3. **Script Path Validation**: Scripts must be in project directory tree
4. **Timeout Protection**: Scripts killed after timeout to prevent hanging
5. **Admin Auth Required**: All endpoints require admin JWT token
6. **Audit Logging**: All actions logged with admin user ID

## Testing

### Unit Test Example

```python
import pytest
from app.services.container_action_service import ContainerActionService

@pytest.mark.asyncio
async def test_start_sglang_uses_custom_script():
    service = ContainerActionService()
    result = await service.start_container("trollama-sglang")
    
    assert result["status"] == "success"
    assert result["method"] == "script"
    assert "sglang" in result["message"].lower()

@pytest.mark.asyncio
async def test_start_fastapi_uses_docker():
    service = ContainerActionService()
    result = await service.start_container("trollama-fastapi")
    
    assert result["status"] == "success"
    assert result["method"] == "docker"
```

### Integration Test

```bash
# Start SGLang via API
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8003/admin/system/docker/containers/trollama-sglang/start

# Check response includes method used
# Expected: {"status": "success", "method": "script", ...}

# Verify container is running
docker ps | grep trollama-sglang

# Check admin service logs
docker logs trollama-admin | tail -20
```

## Files Modified

### Backend
- ✅ `admin-service/app/services/container_action_service.py` (NEW)
- ✅ `admin-service/app/config/container_actions.yaml` (NEW)
- ✅ `admin-service/app/api/system.py` (UPDATED)
- ✅ `admin-service/pyproject.toml` (UPDATED - added PyYAML)

### Frontend
- ✅ `web-service/src/presentation/components/admin/dashboard/DashboardDockerContainers.tsx` (UPDATED - added sliders)
- ✅ `web-service/src/presentation/components/admin/dashboard/DashboardModelsQuick.tsx` (UPDATED - added sliders)
- ✅ `web-service/src/presentation/hooks/useModelManagement.ts` (NEW)
- ✅ `web-service/src/presentation/hooks/useDockerContainers.ts` (UPDATED - added auth headers)

## Next Steps

1. ✅ Configuration system implemented
2. ✅ SGLang custom scripts configured
3. ⏳ Add master start/stop script endpoint (optional)
4. ⏳ Add status_script support for health checks (optional)
5. ⏳ Add unit tests for ContainerActionService (optional)
6. ⏳ Add UI feedback for script vs docker method (optional)
