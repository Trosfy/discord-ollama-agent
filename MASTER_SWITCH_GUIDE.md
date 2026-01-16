# Master Switch Feature Guide

## Overview

The admin dashboard now has a **Master Control** toggle that can start/stop all Trollama services with a single switch.

## UI Location

**Admin Dashboard → Docker Containers Card**

```
┌─────────────────────────────────┐
│ Docker Containers               │
├─────────────────────────────────┤
│ Master Control         [====●]  │  ← Master switch (larger)
│ ─────────────────────────────── │
│ fastapi                [===●]   │  ← Individual containers
│ discord-bot            [●===]   │
│ dynamodb               [===●]   │
│ sglang                 [●===]   │
│ ...                             │
└─────────────────────────────────┘
```

## How It Works

### Master Switch State
- **ON (right/tan)**: Majority of containers are running (> 50%)
- **OFF (left/gray)**: Majority of containers are stopped (≤ 50%)

### Toggling ON (Start All)
1. User toggles master switch to ON
2. Frontend calls `POST /admin/system/docker/start-all`
3. Backend runs `./start.sh` which:
   - Loads VRAM_PROFILE from .env
   - Starts SGLang first (if performance profile) using custom script
   - Starts all other services via docker compose
   - Waits for health checks
4. Toast notification: "Starting all services (this may take several minutes)..."
5. Containers refresh after 2 seconds

### Toggling OFF (Stop All)
1. User toggles master switch to OFF
2. Frontend calls `POST /admin/system/docker/stop-all`
3. Backend runs `./stop.sh` which:
   - Stops application services first
   - Stops SGLang last with custom script (if running)
   - Graceful shutdown with proper cleanup
4. Toast notification: "Stopped all services"
5. Containers refresh after 2 seconds

## API Endpoints

### Start All
```bash
POST /admin/system/docker/start-all
Authorization: Bearer <token>

Response:
{
  "status": "success",
  "message": "All Trollama services started successfully",
  "output": "... startup script output ..."
}
```

**Timeout**: 15 minutes (allows for SGLang model loading)

### Stop All
```bash
POST /admin/system/docker/stop-all
Authorization: Bearer <token>

Response:
{
  "status": "success",
  "message": "All Trollama services stopped successfully",
  "output": "... shutdown script output ..."
}
```

**Timeout**: 5 minutes

## Master Scripts

### start.sh
- Starts application services via `docker compose -f docker-compose.app.yml up -d`
- SGLang is managed separately via `./scripts/model_management/sglang/start.sh`

### stop.sh
- Stops application services via `docker compose -f docker-compose.app.yml down`
- SGLang is managed separately via `./scripts/model_management/sglang/stop.sh`

## Visual Design

### Master Switch
- **Larger**: 48px wide × 12px high (vs 40px × 8px for individual toggles)
- **Bold Label**: "Master Control" (font-semibold)
- **Visual Separator**: Border below to separate from individual containers
- **Loading State**: Shows "Processing..." text when toggling
- **Disabled State**: Grayed out and unclickable during operation

### Individual Switches
- Same design as before
- Smaller than master switch for visual hierarchy
- Can still be toggled independently

## User Experience

### Starting All Services
1. User toggles master switch ON
2. Switch immediately shows loading state (disabled, "Processing..." text)
3. Toast appears: "Starting all services (this may take several minutes)..."
4. Backend runs for 5-10 minutes (SGLang startup is slow)
5. Container list refreshes automatically
6. Master switch re-enables

### Expected Timing
- **Stop All**: ~30 seconds (quick graceful shutdown)
- **Start All (Conservative)**: ~30 seconds (simple docker compose)
- **Start All (Performance)**: ~5-10 minutes (SGLang needs to load models)

### Error Handling
- If start/stop fails, shows error toast
- Master switch returns to previous state
- Individual container controls still work
- Check admin service logs for details: `docker logs trollama-admin`

## Implementation Details

### Frontend Components

**DashboardDockerContainers.tsx**:
- Master toggle at top
- Calculates `isMasterOn = runningCount > containers.length / 2`
- Separate loading state for master operations
- Refreshes container list after 2 seconds

**useDockerMaster.ts** (NEW):
- `startAll()`: Calls start-all endpoint
- `stopAll()`: Calls stop-all endpoint
- Uses JWT token for authentication

### Backend Endpoints

**admin-service/app/api/system.py**:
- `POST /admin/system/docker/start-all` (lines 361-419)
- `POST /admin/system/docker/stop-all` (lines 422-479)
- Both require admin authentication
- Run scripts from project root with subprocess
- Long timeouts to handle SGLang startup

### Scripts

**start.sh** (existing):
- Profile-aware startup
- SGLang-first startup for performance
- Health monitoring

**stop.sh** (new):
- Reverse order shutdown
- SGLang custom stop script
- Graceful cleanup

## Benefits

✅ **One-Click Operations**: Start/stop all services with single toggle
✅ **Profile-Aware**: Uses correct startup sequence based on VRAM_PROFILE
✅ **Graceful Shutdown**: Proper cleanup in reverse order
✅ **Visual Feedback**: Loading states, toast notifications
✅ **Error Recovery**: Individual controls still work if master fails
✅ **Audit Trail**: All operations logged with admin user ID

## Testing

### Test Master Start
```bash
# Via API
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8003/admin/system/docker/start-all

# Expected: Services start in correct order, SGLang loads models
docker compose ps  # All services should be running
```

### Test Master Stop
```bash
# Via API
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8003/admin/system/docker/stop-all

# Expected: All services stop gracefully
docker compose ps  # Should show no running services
```

### Test UI
1. Navigate to admin dashboard
2. Toggle master switch ON
3. Wait for services to start (5-10 minutes for performance profile)
4. Verify all individual toggles show ON
5. Toggle master switch OFF
6. Verify all services stop

## Troubleshooting

### Master Switch Doesn't Change State

**Check**:
1. Are you authenticated? (JWT token valid)
2. Check browser console for errors
3. Check admin service logs: `docker logs trollama-admin`

**Common Issues**:
- Token expired: Re-login via auth service
- Admin service down: `docker restart trollama-admin`
- Permissions: Ensure scripts are executable

### Start-All Times Out

**Cause**: SGLang startup takes > 15 minutes

**Fix**:
1. Increase timeout in [system.py:393](admin-service/app/api/system.py#L393)
2. Or start SGLang manually first: `./scripts/model_management/sglang/start.sh`
3. Then toggle master ON for other services

### Master Switch Shows Wrong State

**Cause**: Container list not refreshed

**Fix**:
1. Wait 2 seconds for auto-refresh
2. Or manually refresh page
3. Check individual container states match expectation

### Stop-All Leaves Containers Running

**Check**:
1. Is stop.sh executable? `chmod +x stop.sh`
2. Check logs: `docker logs trollama-admin`
3. Manually verify: `docker compose ps`

**Fix**: Run stop script manually:
```bash
./stop.sh
docker compose down  # Force stop if needed
```

## Files Modified

### Backend
- ✅ [admin-service/app/api/system.py](admin-service/app/api/system.py) - Added start-all/stop-all endpoints
- ✅ [stop.sh](stop.sh) - New master shutdown script

### Frontend
- ✅ [web-service/src/presentation/components/admin/dashboard/DashboardDockerContainers.tsx](web-service/src/presentation/components/admin/dashboard/DashboardDockerContainers.tsx) - Added master toggle UI
- ✅ [web-service/src/presentation/hooks/useDockerMaster.ts](web-service/src/presentation/hooks/useDockerMaster.ts) - New hook for master operations

## Security

- ✅ Admin authentication required
- ✅ Scripts run from project root (no path traversal)
- ✅ Timeout protection (15 min start, 5 min stop)
- ✅ Audit logging with admin user ID
- ✅ Individual controls still available if master fails

## Future Enhancements

- ⏳ Add "Restart All" button
- ⏳ Show detailed progress during startup (websocket updates)
- ⏳ Add confirmation dialog for master operations
- ⏳ Add estimated time remaining
- ⏳ Add ability to exclude specific containers from master control
