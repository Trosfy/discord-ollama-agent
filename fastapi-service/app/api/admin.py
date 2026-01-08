"""Admin endpoints for system management."""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from app.models.requests import GrantTokensRequest
from app.dependencies import get_storage, get_queue
from app.config import settings
import asyncio
import json
import subprocess
import re
from datetime import datetime
from typing import AsyncGenerator, List, Dict


router = APIRouter()


@router.post("/grant-tokens")
async def grant_tokens(
    request: GrantTokensRequest,
    storage=Depends(get_storage)
):
    """
    Grant bonus tokens to a user.

    Args:
        request: GrantTokensRequest with user_id and amount

    Returns:
        Success status

    Raises:
        HTTPException: If user not found
    """
    user = await storage.get_user(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await storage.grant_bonus_tokens(request.user_id, request.amount)
    return {
        "status": "success",
        "user_id": request.user_id,
        "tokens_granted": request.amount
    }


@router.post("/maintenance/soft")
async def enable_soft_maintenance():
    """
    Enable soft maintenance mode (queue still works).

    Note: This requires runtime config modification.
    For MVP, just returns current state.

    Returns:
        Current maintenance mode status
    """
    return {"maintenance_mode": settings.MAINTENANCE_MODE}


@router.post("/maintenance/hard")
async def enable_hard_maintenance():
    """
    Enable hard maintenance mode (reject all requests).

    Note: This requires runtime config modification.
    For MVP, just returns current state.

    Returns:
        Current hard maintenance mode status
    """
    return {"maintenance_mode_hard": settings.MAINTENANCE_MODE_HARD}


@router.get("/queue/stats")
async def get_queue_stats(queue=Depends(get_queue)):
    """
    Get queue statistics.

    Returns:
        Queue statistics dictionary
    """
    return {
        "queue_size": queue.size(),
        "is_full": queue.is_full(),
        "max_size": settings.MAX_QUEUE_SIZE
    }


async def check_service_health() -> dict:
    """Check health status of all services using docker CLI."""
    try:
        services = []

        # Service mapping
        service_map = {
            "trollama-fastapi": "FastAPI Service",
            "trollama-discord": "Discord Bot",
            "ollama": "Ollama",
            "dynamodb-local": "DynamoDB",
            "trollama-monitor": "Monitoring Service"
        }

        for container_name, display_name in service_map.items():
            try:
                # Check if container exists and is running using docker CLI
                result = subprocess.run(
                    ['docker', 'inspect', '--format={{.State.Status}}', container_name],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0:
                    status = result.stdout.strip()
                    services.append({
                        "name": display_name,
                        "status": "healthy" if status == "running" else "unhealthy",
                        "lastCheck": datetime.now().isoformat(),
                        "details": f"Container: {container_name} ({status})"
                    })
                else:
                    services.append({
                        "name": display_name,
                        "status": "unhealthy",
                        "lastCheck": datetime.now().isoformat(),
                        "details": "Container not found"
                    })
            except subprocess.TimeoutExpired:
                services.append({
                    "name": display_name,
                    "status": "unknown",
                    "lastCheck": datetime.now().isoformat(),
                    "details": "Check timeout"
                })
            except Exception as e:
                services.append({
                    "name": display_name,
                    "status": "unknown",
                    "lastCheck": datetime.now().isoformat(),
                    "details": f"Error: {str(e)}"
                })

        return {"services": services}
    except Exception as e:
        return {
            "services": [
                {
                    "name": "System",
                    "status": "unhealthy",
                    "lastCheck": datetime.now().isoformat(),
                    "details": f"Error checking services: {str(e)}"
                }
            ]
        }


async def health_stream_generator() -> AsyncGenerator[str, None]:
    """Generate SSE stream for service health updates."""
    while True:
        try:
            health_data = await check_service_health()
            yield f"data: {json.dumps(health_data)}\n\n"
            await asyncio.sleep(5)  # Update every 5 seconds
        except asyncio.CancelledError:
            break
        except Exception as e:
            error_data = {
                "services": [{
                    "name": "Error",
                    "status": "unhealthy",
                    "details": str(e)
                }]
            }
            yield f"data: {json.dumps(error_data)}\n\n"
            await asyncio.sleep(5)


@router.get("/health/stream")
async def stream_health():
    """
    Stream service health status via Server-Sent Events.

    Returns:
        StreamingResponse with SSE updates every 5 seconds
    """
    return StreamingResponse(
        health_stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )


async def get_vram_stats() -> dict:
    """Get VRAM usage statistics from nvidia-smi."""
    try:
        # Run nvidia-smi command
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.total,memory.used,memory.free', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            check=True
        )

        # Parse output
        output = result.stdout.strip()
        if output:
            total, used, free = map(float, output.split(','))
            total_bytes = int(total * 1024 * 1024)  # Convert MB to bytes
            used_bytes = int(used * 1024 * 1024)
            free_bytes = int(free * 1024 * 1024)
            percentage = (used / total) * 100

            # Get loaded models (placeholder - would need Ollama API integration)
            models = []
            try:
                # Query Ollama for loaded models
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{settings.OLLAMA_BASE_URL}/api/ps") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            models = [
                                {
                                    "name": model.get("name", "unknown"),
                                    "vramUsage": model.get("size", 0)
                                }
                                for model in data.get("models", [])
                            ]
            except Exception:
                pass

            return {
                "total": total_bytes,
                "used": used_bytes,
                "free": free_bytes,
                "percentage": percentage,
                "models": models,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise ValueError("Empty nvidia-smi output")

    except subprocess.CalledProcessError:
        # No GPU or nvidia-smi not available
        return {
            "total": 0,
            "used": 0,
            "free": 0,
            "percentage": 0,
            "models": [],
            "timestamp": datetime.now().isoformat(),
            "error": "nvidia-smi not available or no GPU detected"
        }
    except Exception as e:
        return {
            "total": 0,
            "used": 0,
            "free": 0,
            "percentage": 0,
            "models": [],
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


async def vram_stream_generator() -> AsyncGenerator[str, None]:
    """Generate SSE stream for VRAM usage updates."""
    while True:
        try:
            vram_data = await get_vram_stats()
            yield f"data: {json.dumps(vram_data)}\n\n"
            await asyncio.sleep(2)  # Update every 2 seconds
        except asyncio.CancelledError:
            break
        except Exception as e:
            error_data = {
                "total": 0,
                "used": 0,
                "free": 0,
                "percentage": 0,
                "models": [],
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"
            await asyncio.sleep(2)


@router.get("/vram/stream")
async def stream_vram():
    """
    Stream VRAM usage statistics via Server-Sent Events.

    Returns:
        StreamingResponse with SSE updates every 2 seconds
    """
    return StreamingResponse(
        vram_stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )


@router.get("/models")
async def list_models():
    """
    List all available models from Ollama.

    Returns:
        Dictionary with list of models and their status
    """
    try:
        import aiohttp

        # Get all available models
        async with aiohttp.ClientSession() as session:
            # Get list of all models
            async with session.get(f"{settings.OLLAMA_BASE_URL}/api/tags") as resp:
                if resp.status != 200:
                    raise HTTPException(status_code=502, detail="Failed to fetch models from Ollama")

                all_models_data = await resp.json()
                all_models = all_models_data.get("models", [])

            # Get currently loaded models
            async with session.get(f"{settings.OLLAMA_BASE_URL}/api/ps") as resp:
                loaded_models_data = await resp.json() if resp.status == 200 else {"models": []}
                loaded_model_names = {m.get("name") for m in loaded_models_data.get("models", [])}

        # Combine information
        models = []
        for model in all_models:
            name = model.get("name", "unknown")
            models.append({
                "name": name,
                "size": model.get("size", 0),
                "loaded": name in loaded_model_names,
                "vramUsage": model.get("size", 0) if name in loaded_model_names else None,
                "lastUsed": model.get("modified_at")
            })

        return {"models": models}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


@router.post("/models/{model_name}/load")
async def load_model(model_name: str):
    """
    Load a specific model into VRAM.

    Args:
        model_name: Name of the model to load

    Returns:
        Success status
    """
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            # Generate empty prompt to load model
            async with session.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": model_name,
                    "prompt": "",
                    "keep_alive": "30m"  # Keep loaded for 30 minutes
                }
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise HTTPException(
                        status_code=502,
                        detail=f"Failed to load model: {error_text}"
                    )

        return {
            "status": "success",
            "model": model_name,
            "message": f"Model {model_name} loaded successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load model: {str(e)}")


@router.post("/models/{model_name}/unload")
async def unload_model(model_name: str):
    """
    Unload a specific model from VRAM.

    Args:
        model_name: Name of the model to unload

    Returns:
        Success status
    """
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            # Set keep_alive to 0 to unload immediately
            async with session.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": model_name,
                    "prompt": "",
                    "keep_alive": 0  # Unload immediately
                }
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise HTTPException(
                        status_code=502,
                        detail=f"Failed to unload model: {error_text}"
                    )

        return {
            "status": "success",
            "model": model_name,
            "message": f"Model {model_name} unloaded successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unload model: {str(e)}")


@router.get("/users")
async def list_users(storage=Depends(get_storage)):
    """
    List all users in the system.

    Returns:
        Dictionary with list of users and their stats
    """
    try:
        # This would need a method in storage to list all users
        # For now, return empty list as placeholder
        # In production, you'd need to add a list_users method to storage interface
        users = []

        return {"users": users}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list users: {str(e)}")


@router.post("/users/{user_id}/ban")
async def ban_user(user_id: str, storage=Depends(get_storage)):
    """
    Ban a user from using the system.

    Args:
        user_id: ID of the user to ban

    Returns:
        Success status
    """
    try:
        user = await storage.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update user status to banned
        await storage.update_user(user_id, {"is_banned": True})

        return {
            "status": "success",
            "user_id": user_id,
            "message": f"User {user_id} banned successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ban user: {str(e)}")


@router.post("/users/{user_id}/unban")
async def unban_user(user_id: str, storage=Depends(get_storage)):
    """
    Unban a user.

    Args:
        user_id: ID of the user to unban

    Returns:
        Success status
    """
    try:
        user = await storage.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update user status to unbanned
        await storage.update_user(user_id, {"is_banned": False})

        return {
            "status": "success",
            "user_id": user_id,
            "message": f"User {user_id} unbanned successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unban user: {str(e)}")


@router.get("/settings")
async def get_settings():
    """
    Get current system settings from persistent configuration.

    Returns:
        Dictionary with current settings
    """
    from app.services.config_manager import get_config_manager

    config_manager = get_config_manager()
    config = await config_manager.get_config()

    return {
        "defaultModel": config.get("DEFAULT_MODEL", settings.DEFAULT_MODEL),
        "routerModel": config.get("ROUTER_MODEL", settings.ROUTER_MODEL),
        "maxQueueSize": config.get("MAX_QUEUE_SIZE", settings.MAX_QUEUE_SIZE),
        "streamChunkInterval": config.get("STREAM_CHUNK_INTERVAL", settings.STREAM_CHUNK_INTERVAL),
        "enableStreaming": config.get("ENABLE_STREAMING", settings.ENABLE_STREAMING),
        "vramConservativeMode": config.get("VRAM_CONSERVATIVE_MODE", settings.VRAM_CONSERVATIVE_MODE),
        "maintenanceMode": config.get("MAINTENANCE_MODE", settings.MAINTENANCE_MODE),
        "maintenanceModeHard": config.get("MAINTENANCE_MODE_HARD", settings.MAINTENANCE_MODE_HARD)
    }


@router.put("/settings")
async def update_settings(new_settings: dict):
    """
    Update system settings and persist to configuration file.

    This updates both runtime settings and persists them to disk,
    so they survive service restarts.

    Args:
        new_settings: Dictionary of settings to update

    Returns:
        Success status with updated configuration
    """
    from app.services.config_manager import get_config_manager

    # Map camelCase to UPPER_SNAKE_CASE
    setting_map = {
        "defaultModel": "DEFAULT_MODEL",
        "routerModel": "ROUTER_MODEL",
        "maxQueueSize": "MAX_QUEUE_SIZE",
        "streamChunkInterval": "STREAM_CHUNK_INTERVAL",
        "enableStreaming": "ENABLE_STREAMING",
        "vramConservativeMode": "VRAM_CONSERVATIVE_MODE",
        "maintenanceMode": "MAINTENANCE_MODE",
        "maintenanceModeHard": "MAINTENANCE_MODE_HARD"
    }

    # Convert camelCase to UPPER_SNAKE_CASE
    config_updates = {}
    for camel_key, snake_key in setting_map.items():
        if camel_key in new_settings:
            config_updates[snake_key] = new_settings[camel_key]

    # Update configuration
    config_manager = get_config_manager()
    updated_config = await config_manager.update_config(config_updates)

    return {
        "status": "success",
        "message": "Settings updated and persisted to disk",
        "settings": updated_config
    }


# ============================================================================
# SGLang Control Endpoints
# ============================================================================

# Track SGLang state
_sglang_state = {"status": "unknown", "message": None, "started_at": None}


async def run_sglang_script(script_name: str, timeout: int = 600) -> tuple:
    """
    Run an SGLang control script asynchronously.

    Args:
        script_name: Name of the script to run
        timeout: Maximum execution time in seconds

    Returns:
        Tuple of (success: bool, output: str)
    """
    import os

    scripts_dir = os.environ.get("SCRIPTS_DIR", "/app/scripts/model_management")
    script_path = os.path.join(scripts_dir, script_name)

    if not os.path.exists(script_path):
        return False, f"Script not found: {script_path}"

    try:
        process = await asyncio.create_subprocess_exec(
            "bash",
            script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )

        if process.returncode == 0:
            return True, stdout.decode()
        else:
            return False, stderr.decode() or stdout.decode()
    except asyncio.TimeoutError:
        return False, "Script execution timed out"
    except Exception as e:
        return False, str(e)


async def check_sglang_container_status() -> dict:
    """Check if SGLang container is running via docker."""
    try:
        process = await asyncio.create_subprocess_exec(
            "docker",
            "ps",
            "--filter", "name=sglang",
            "--format", "{{.Status}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)
        output = stdout.decode().strip()

        if output:
            return {"status": "running", "message": output}
        else:
            return {"status": "stopped", "message": "Container not running"}
    except asyncio.TimeoutError:
        return {"status": "unknown", "message": "Check timed out"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/sglang/status")
async def get_sglang_status():
    """
    Get the current status of the SGLang server.

    Returns:
        SGLang status including container state and any startup messages
    """
    container_status = await check_sglang_container_status()

    return {
        "container": container_status,
        "internal_state": _sglang_state,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/sglang/start")
async def start_sglang():
    """
    Start the SGLang server.

    This initiates the SGLang startup process which can take several minutes
    for MoE weight shuffling. Use GET /sglang/status to monitor progress.

    Returns:
        Acknowledgment that startup has been initiated
    """
    global _sglang_state

    # Check if already running
    container_status = await check_sglang_container_status()
    if container_status["status"] == "running":
        raise HTTPException(
            status_code=400,
            detail="SGLang is already running"
        )

    # Check if startup is in progress
    if _sglang_state["status"] == "starting":
        raise HTTPException(
            status_code=400,
            detail="SGLang startup already in progress"
        )

    # Update state
    _sglang_state = {
        "status": "starting",
        "message": "Initiating SGLang startup...",
        "started_at": datetime.now().isoformat()
    }

    # Start in background task
    async def start_task():
        global _sglang_state
        success, message = await run_sglang_script("start_sglang_gpt_oss.sh", timeout=900)

        if success:
            _sglang_state = {
                "status": "running",
                "message": "SGLang started successfully",
                "started_at": _sglang_state.get("started_at")
            }
        else:
            _sglang_state = {
                "status": "error",
                "message": f"Startup failed: {message[:500]}",
                "started_at": _sglang_state.get("started_at")
            }

    # Create background task
    asyncio.create_task(start_task())

    return {
        "status": "accepted",
        "message": "SGLang startup initiated. This may take 5-10 minutes for MoE weight shuffling.",
        "check_status": "/api/admin/sglang/status"
    }


@router.post("/sglang/stop")
async def stop_sglang():
    """
    Stop the SGLang server.

    Returns:
        Status of the stop operation
    """
    global _sglang_state

    # Check if running
    container_status = await check_sglang_container_status()
    if container_status["status"] == "stopped":
        raise HTTPException(
            status_code=400,
            detail="SGLang is not running"
        )

    _sglang_state = {
        "status": "stopping",
        "message": "Stopping SGLang server...",
        "started_at": None
    }

    success, message = await run_sglang_script("stop_sglang.sh", timeout=60)

    if success:
        _sglang_state = {
            "status": "stopped",
            "message": "SGLang stopped successfully",
            "started_at": None
        }
        return {
            "status": "success",
            "message": "SGLang stopped successfully"
        }
    else:
        _sglang_state = {
            "status": "error",
            "message": f"Stop failed: {message[:500]}",
            "started_at": None
        }
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop SGLang: {message[:500]}"
        )


# ============================================================================
# Docker Container Management Endpoints
# ============================================================================

# Whitelist for allowed container prefixes
ALLOWED_CONTAINER_PREFIXES = ["trollama-"]


def validate_container_name(name: str) -> bool:
    """
    Validate container name against whitelist and prevent command injection.

    Args:
        name: Container name to validate

    Returns:
        True if valid

    Raises:
        HTTPException: If validation fails
    """
    # Check whitelist
    if not any(name.startswith(prefix) for prefix in ALLOWED_CONTAINER_PREFIXES):
        raise HTTPException(
            status_code=403,
            detail=f"Container '{name}' not in allowed list (must start with trollama-)"
        )

    # Prevent command injection - only allow alphanumeric, underscore, and hyphen
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        raise HTTPException(
            status_code=400,
            detail="Invalid container name format"
        )

    return True


@router.get("/docker/containers")
async def get_docker_containers() -> Dict[str, List[Dict]]:
    """
    Get list of Trollama containers with their status.

    Returns:
        Dictionary containing list of containers with status information

    Raises:
        HTTPException: If Docker command fails
    """
    try:
        # Use docker ps with custom format for structured output
        result = subprocess.run(
            [
                "docker", "ps", "-a",
                "--filter", "name=trollama",
                "--format", '{{.Names}}|{{.Status}}|{{.State}}|{{.Image}}'
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )

        containers = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            try:
                name, status, state, image = line.split('|')
                containers.append({
                    "name": name,
                    "status": status,
                    "state": state,  # running, exited, paused, restarting
                    "image": image,
                    "healthy": "healthy" in status.lower() or state == "running"
                })
            except ValueError:
                # Skip malformed lines
                continue

        return {"containers": containers}

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Docker command timed out")
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Docker command failed: {e.stderr.decode() if e.stderr else str(e)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Docker error: {str(e)}")


@router.post("/docker/containers/{container_name}/start")
async def start_container(container_name: str) -> Dict[str, str]:
    """
    Start a Docker container.

    Args:
        container_name: Name of the container to start (must be in whitelist)

    Returns:
        Success status with container name

    Raises:
        HTTPException: If validation fails or container cannot be started
    """
    validate_container_name(container_name)

    try:
        result = subprocess.run(
            ["docker", "start", container_name],
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )

        return {
            "status": "success",
            "container": container_name,
            "message": f"Container {container_name} started successfully"
        }

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else e.stdout.decode()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start container: {error_msg}"
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Container start operation timed out"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.post("/docker/containers/{container_name}/stop")
async def stop_container(container_name: str) -> Dict[str, str]:
    """
    Stop a Docker container with graceful shutdown.

    Args:
        container_name: Name of the container to stop (must be in whitelist)

    Returns:
        Success status with container name

    Raises:
        HTTPException: If validation fails or container cannot be stopped
    """
    validate_container_name(container_name)

    try:
        # Stop with 10 second graceful shutdown timeout
        result = subprocess.run(
            ["docker", "stop", container_name, "-t", "10"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )

        return {
            "status": "success",
            "container": container_name,
            "message": f"Container {container_name} stopped successfully"
        }

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else e.stdout.decode()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop container: {error_msg}"
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Container stop operation timed out"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
