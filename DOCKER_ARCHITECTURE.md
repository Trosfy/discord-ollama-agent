# Docker Compose Architecture

Trollama uses a **split docker-compose architecture** that separates infrastructure services (always-on) from application services (toggleable via admin dashboard).

## Architecture Overview

### Infrastructure Services (`docker-compose.infra.yml`)
Always-on core services that the admin dashboard depends on. **Never stopped** by master toggle.

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| **logging-service** | `trollama-logging` | 9999, 9998 | Centralized logging for all services |
| **dynamodb-local** | `trollama-dynamodb` | 8000 | Database for auth, conversations, metadata |
| **auth-service** | `trollama-auth` | 8002 | JWT authentication and user management |
| **admin-service** | `trollama-admin` | 8003 | Admin API backend (system metrics, container management) |
| **web-service** | `trollama-web` | 8502 | Admin dashboard UI (Next.js) |

### Application Services (`docker-compose.app.yml`)
Toggleable services that can be started/stopped via admin dashboard master toggle.

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| **fastapi-service** | `trollama-fastapi` | 8001 | Main LLM API and orchestrator |
| **discord-bot** | `trollama-discord-bot` | 9997 | Discord bot client |
| **sglang-server** | `trollama-sglang` | 30000 | High-performance LLM backend (performance profile only) |

---

## Usage

### Starting Everything

```bash
# Recommended: Use the start script (handles SGLang, profiles, etc.)
./start.sh

# Manual: Start both infrastructure and application services
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up -d

# With performance profile (includes SGLang)
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml --profile performance up -d
```

### Stopping Application Services

```bash
# Recommended: Use the stop script (keeps infrastructure running)
./stop.sh

# Manual: Stop only application services
docker compose -f docker-compose.app.yml down
```

**Result**: Infrastructure (admin, auth, web, logging, dynamodb) continues running. Only fastapi, discord-bot, and sglang are stopped.

### Stopping Everything

```bash
# Stop all services (infrastructure + application)
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml down
```

### Viewing Logs

```bash
# View all logs (infrastructure + application)
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml logs -f

# View only application logs
docker compose -f docker-compose.app.yml logs -f

# View specific service
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml logs -f trollama-fastapi
```

### Checking Status

```bash
# Check all running containers
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml ps

# Check only application services
docker compose -f docker-compose.app.yml ps
```

---

## Admin Dashboard Master Toggle

The admin dashboard (http://localhost:8502/admin) has a **Master Control** toggle in the Docker Containers card.

- **Toggle ON**: Starts all application services (fastapi, discord-bot, sglang if performance profile)
- **Toggle OFF**: Stops all application services (infrastructure remains running)

**Behind the scenes:**
- Master toggle calls `/admin/system/docker/start-all` or `/admin/system/docker/stop-all`
- Stop-all runs `./stop.sh` which uses `docker compose -f docker-compose.app.yml down`
- Start-all runs `./start.sh` which starts both compose files

---

## Why Split Compose Files?

### Problem with Monolithic Compose
Previously, a single `docker-compose.yml` contained all services. This caused issues:
- Master toggle could accidentally stop admin/auth services mid-request
- No clear separation between infrastructure and application
- Easy to accidentally stop critical services

### Solution: Split Architecture
1. **Infrastructure isolation**: Admin dashboard cannot stop itself
2. **Clear boundaries**: Obvious which services are critical vs toggleable
3. **Safer operations**: Master toggle only affects application services
4. **Better control**: Can stop/start apps without affecting dashboard

---

## Dependencies

### Cross-File Dependencies
Some infrastructure services depend on application services (e.g., web-service uses fastapi for chat):

```yaml
# docker-compose.infra.yml
web-service:
  depends_on:
    fastapi-service:  # Application service
      condition: service_healthy
```

**How it works:**
- **Startup**: Both files are used together, dependencies resolve correctly
- **Shutdown**: Only app services stop, but infra services **continue running**
- **Graceful degradation**: Web dashboard shows fastapi as "unhealthy" when stopped

### Dependency Graph

```
Infrastructure (always-on):
  logging-service (no deps)
  dynamodb-local (no deps)
  auth-service → dynamodb, logging
  admin-service → dynamodb, auth, logging
  web-service → auth

Application (toggleable):
  fastapi-service → dynamodb, logging
  discord-bot → fastapi, logging
  sglang-server (no deps, performance profile only)
```

---

## Custom Container Scripts

Some containers require custom start/stop scripts instead of default `docker start/stop`:

### Configuration: `admin-service/app/config/container_actions.yaml`

```yaml
containers:
  trollama-sglang:
    start_script: "./scripts/model_management/sglang/start.sh"
    stop_script: "./scripts/model_management/sglang/stop.sh"
    description: "SGLang model server with MoE weight shuffling and earlyoom management"
    timeout: 720  # 12 minutes for model loading
```

### SGLang Custom Startup
SGLang requires complex startup (see [scripts/model_management/sglang/start.sh](scripts/model_management/sglang/start.sh)):
1. Enable swap for MoE weight shuffling (~50GB RAM needed)
2. Disable earlyoom during startup (prevent OOM kills)
3. Flush buffer cache to maximize available memory
4. Start container and monitor health (5-7 min for model loading)
5. Re-enable earlyoom after model is loaded
6. Disable swap to prevent thermal issues (model is in GPU memory)

---

## Troubleshooting

### Issue: "Service not found"
```
Error: service "trollama-fastapi" is not defined in the Compose file
```
**Fix**: Use both compose files when managing services:
```bash
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml <command>
```

### Issue: Infrastructure won't start
**Check**: Ensure application services aren't blocking ports
```bash
# Stop all first
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml down

# Start infrastructure only
docker compose -f docker-compose.infra.yml up -d

# Then start application
docker compose -f docker-compose.app.yml up -d
```

### Issue: Admin dashboard shows "fastapi unhealthy" but it's running
**Check**:
1. Is fastapi container actually running? `docker ps | grep trollama-fastapi`
2. Check fastapi health: `curl http://localhost:8001/health`
3. Check admin service can reach it: `docker exec trollama-admin curl http://trollama-fastapi:8000/health`

### Issue: Master toggle doesn't work
**Check**:
1. Is admin service running? `docker ps | grep trollama-admin`
2. Check admin service logs: `docker logs trollama-admin`
3. Verify stop.sh is executable: `chmod +x stop.sh start.sh`
4. Check container action config: `cat admin-service/app/config/container_actions.yaml`

---

## Migration from Monolithic Compose

If you're upgrading from the old single `docker-compose.yml`:

### Step 1: Backup
```bash
# Backup old compose file
cp docker-compose.yml docker-compose.yml.backup
```

### Step 2: Stop All Services
```bash
docker compose down
```

### Step 3: Use New Split Files
The old `docker-compose.yml` is no longer used. Use the new split files:
- `docker-compose.infra.yml`
- `docker-compose.app.yml`

### Step 4: Start Everything
```bash
./start.sh
```

### Step 5: Verify
```bash
# Check all services are running
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml ps

# Check admin dashboard
open http://localhost:8502/admin
```

---

## Best Practices

1. **Always use start.sh/stop.sh scripts** - They handle profiles, SGLang, and compose files correctly
2. **Don't manually stop infrastructure** - Use admin dashboard or compose files correctly
3. **Check logs when debugging** - Use compose file flags to view specific service logs
4. **Test master toggle** - Verify infrastructure stays up when stopping applications
5. **Monitor health checks** - Admin dashboard shows real-time service health

---

## See Also

- [README.md](README.md) - Main project documentation
- [TECHNICAL.md](TECHNICAL.md) - Technical architecture details
- [admin-service/app/config/container_actions.yaml](admin-service/app/config/container_actions.yaml) - Container script mapping
- [scripts/model_management/](scripts/model_management/) - SGLang startup scripts
