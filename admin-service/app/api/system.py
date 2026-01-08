"""System control API endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, List
import logging
import subprocess
import asyncio
import os
import re
from pathlib import Path

from app.services.system_service import SystemService
from app.services.container_action_service import ContainerActionService
from app.middleware.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/system", tags=["system"])

# Initialize container action service
container_action_service = ContainerActionService()


# Request Models
class MaintenanceModeRequest(BaseModel):
    """Request to set maintenance mode."""
    enabled: bool = Field(..., description="True to enable, False to disable")
    mode: str = Field("soft", description="Maintenance mode type: 'soft' or 'hard'")


# Dependency for SystemService
def get_system_service() -> SystemService:
    """Get system service instance."""
    return SystemService()


@router.get("/queue/stats")
async def get_queue_stats(
    admin_auth: Dict = Depends(require_admin),
    service: SystemService = Depends(get_system_service)
):
    """
    Get current queue statistics.

    Returns queue size, max capacity, and whether queue is full.

    Requires admin authentication.

    Returns:
        dict: Queue statistics
    """
    try:
        stats = await service.get_queue_stats()
        return stats

    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue/purge")
async def purge_queue(
    admin_auth: Dict = Depends(require_admin),
    service: SystemService = Depends(get_system_service)
):
    """
    Emergency purge of the request queue.

    This is a destructive operation that clears all pending requests.
    Use only in emergency situations.

    Requires admin authentication.

    Returns:
        dict: Result with number of requests purged
    """
    try:
        admin_user = admin_auth.get("user_id", "unknown")

        result = await service.purge_queue(admin_user=admin_user)
        return result

    except Exception as e:
        logger.error(f"Failed to purge queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/maintenance")
async def set_maintenance_mode(
    request: MaintenanceModeRequest,
    admin_auth: Dict = Depends(require_admin),
    service: SystemService = Depends(get_system_service)
):
    """
    Enable or disable maintenance mode.

    Maintenance modes:
    - **soft**: Queue still processes requests, but new connections may be limited
    - **hard**: Reject all new requests except admin operations

    Requires admin authentication.

    Args:
        request: Maintenance mode configuration

    Returns:
        dict: Result with current maintenance status
    """
    try:
        admin_user = admin_auth.get("user_id", "unknown")

        result = await service.set_maintenance_mode(
            enabled=request.enabled,
            mode=request.mode,
            admin_user=admin_user
        )

        return result

    except ValueError as e:
        logger.warning(f"Invalid maintenance mode request: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to set maintenance mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_system_health(
    admin_auth: Dict = Depends(require_admin),
    service: SystemService = Depends(get_system_service)
):
    """
    Get health status for all services.

    Checks:
    - fastapi-service
    - DynamoDB
    - Ollama
    - VRAM orchestrator

    Returns overall health status and details for each service.

    Requires admin authentication.

    Returns:
        dict: Health status for all services
    """
    try:
        health = await service.get_all_health_checks()
        return health

    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
async def get_docker_containers(
    admin_auth: Dict = Depends(require_admin)
) -> Dict[str, List[Dict]]:
    """
    Get list of Trollama containers with their status.

    Shows all containers defined in docker-compose.app.yml, whether running or not.

    Requires admin authentication.

    Returns:
        Dictionary containing list of containers with status information

    Raises:
        HTTPException: If Docker command fails
    """
    try:
        # Get expected containers from docker-compose.app.yml
        compose_file = Path(__file__).parent.parent.parent.parent / "docker-compose.app.yml"
        expected_containers = set()

        if compose_file.exists():
            try:
                import yaml
                with open(compose_file, 'r') as f:
                    compose_config = yaml.safe_load(f)
                    if compose_config and 'services' in compose_config:
                        for service_name, service_config in compose_config['services'].items():
                            if isinstance(service_config, dict) and 'container_name' in service_config:
                                container_name = service_config['container_name']
                                # Include trollama containers except streamlit
                                if container_name.startswith('trollama-') and container_name != 'trollama-streamlit':
                                    expected_containers.add(container_name)
            except Exception as e:
                logger.warning(f"Failed to parse docker-compose.app.yml: {e}")

        # Fallback: if no containers found in compose file, use defaults
        if not expected_containers:
            expected_containers = {
                "trollama-sglang",
                "trollama-fastapi",
                "trollama-discord-bot"
            }

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

        # Build dict of actual container states
        actual_containers = {}
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            try:
                name, status, state, image = line.split('|')
                actual_containers[name] = {
                    "name": name,
                    "status": status,
                    "state": state,  # running, exited, paused, restarting
                    "image": image,
                    "healthy": "healthy" in status.lower() or state == "running"
                }
            except ValueError:
                # Skip malformed lines
                continue

        # Merge expected containers with actual states
        containers = []
        for container_name in sorted(expected_containers):
            if container_name in actual_containers:
                # Container exists, use actual state
                containers.append(actual_containers[container_name])
            else:
                # Container doesn't exist, show as stopped/missing
                containers.append({
                    "name": container_name,
                    "status": "Not created",
                    "state": "exited",
                    "image": "N/A",
                    "healthy": False
                })

        # Get memory usage for running containers
        # Only fetch stats for running containers to avoid overhead
        running_containers = [c["name"] for c in containers if c["state"] == "running"]

        memory_stats = {}
        if running_containers:
            try:
                stats_result = subprocess.run(
                    [
                        "docker", "stats", "--no-stream",
                        "--format", '{{.Name}}|{{.MemUsage}}|{{.MemPerc}}'
                    ] + running_containers,
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                for line in stats_result.stdout.strip().split('\n'):
                    if not line:
                        continue
                    try:
                        name, mem_usage, mem_perc = line.split('|')
                        memory_stats[name] = {
                            "usage": mem_usage.strip(),  # e.g., "1.2GiB / 15.5GiB"
                            "percentage": mem_perc.strip()  # e.g., "7.74%"
                        }
                    except ValueError:
                        continue
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                # If stats fail, just skip memory info
                pass

        # Add memory stats to containers
        for container in containers:
            if container["name"] in memory_stats:
                container["memory"] = memory_stats[container["name"]]
            else:
                container["memory"] = None

        return {"containers": containers}

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Docker command timed out")
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Docker command failed: {e.stderr if e.stderr else str(e)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Docker error: {str(e)}")


@router.post("/docker/containers/{container_name}/start")
async def start_container(
    container_name: str,
    admin_auth: Dict = Depends(require_admin)
) -> Dict[str, str]:
    """
    Start a Docker container.

    Uses custom scripts if defined in container_actions.yaml,
    otherwise falls back to default docker start command.

    Requires admin authentication.

    Args:
        container_name: Name of the container to start (must be in whitelist)

    Returns:
        Success status with container name and method used

    Raises:
        HTTPException: If validation fails or container cannot be started
    """
    validate_container_name(container_name)
    admin_user = admin_auth.get("user_id", "unknown")

    try:
        result = await container_action_service.start_container(container_name)

        if result["status"] == "error":
            logger.error(f"Failed to start container {container_name}: {result['message']}")
            raise HTTPException(
                status_code=500,
                detail=result["message"]
            )

        logger.info(f"Container {container_name} started by admin {admin_user} via {result['method']}")

        return {
            "status": "success",
            "container": container_name,
            "message": result["message"],
            "method": result["method"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error starting {container_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.post("/docker/containers/{container_name}/stop")
async def stop_container(
    container_name: str,
    admin_auth: Dict = Depends(require_admin)
) -> Dict[str, str]:
    """
    Stop a Docker container with graceful shutdown.

    Uses custom scripts if defined in container_actions.yaml,
    otherwise falls back to default docker stop command.

    Requires admin authentication.

    Args:
        container_name: Name of the container to stop (must be in whitelist)

    Returns:
        Success status with container name and method used

    Raises:
        HTTPException: If validation fails or container cannot be stopped
    """
    validate_container_name(container_name)
    admin_user = admin_auth.get("user_id", "unknown")

    try:
        result = await container_action_service.stop_container(container_name)

        if result["status"] == "error":
            logger.error(f"Failed to stop container {container_name}: {result['message']}")
            raise HTTPException(
                status_code=500,
                detail=result["message"]
            )

        logger.info(f"Container {container_name} stopped by admin {admin_user} via {result['method']}")

        return {
            "status": "success",
            "container": container_name,
            "message": result["message"],
            "method": result["method"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error stopping {container_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


# ============================================================================
# Master Start/Stop All Endpoints
# ============================================================================

@router.post("/docker/start-all")
async def start_all_containers(
    admin_auth: Dict = Depends(require_admin)
) -> Dict[str, str]:
    """
    Start all Trollama services using master startup script.

    Uses scripts/container_management/start.sh which handles:
    - Loading VRAM_PROFILE from .env
    - Starting SGLang first (if performance profile)
    - Starting all dependent services
    - Health monitoring

    Requires admin authentication.

    Returns:
        Success status with message

    Raises:
        HTTPException: If startup fails
    """
    admin_user = admin_auth.get("user_id", "unknown")

    # SSH configuration (same as ContainerActionService)
    ssh_host = os.getenv("SSH_HOST", "host.docker.internal")
    ssh_user = os.getenv("SSH_USER", "trosfy")
    ssh_key_path = os.getenv("SSH_KEY_PATH", "/home/app/.ssh/id_ed25519")
    host_project_root = os.getenv("HOST_PROJECT_ROOT", "/home/trosfy/projects/discord-ollama-agent")

    try:
        logger.info(f"Starting all containers via master script (admin: {admin_user})")

        # Build SSH command with TTY allocation
        ssh_cmd = [
            "ssh",
            "-t", "-t",  # Force TTY allocation
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10",
            "-o", "LogLevel=ERROR",
            "-i", ssh_key_path,
            f"{ssh_user}@{ssh_host}",
            f"{host_project_root}/scripts/container_management/start.sh"
        ]

        proc = await asyncio.create_subprocess_exec(
            *ssh_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=900  # 15 minutes for full startup including SGLang
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.error("Master startup timed out after 15 minutes")
            raise HTTPException(
                status_code=504,
                detail="Startup operation timed out after 15 minutes"
            )

        stdout_str = stdout.decode() if stdout else ""
        stderr_str = stderr.decode() if stderr else ""

        if proc.returncode == 0:
            logger.info(f"All containers started successfully by admin {admin_user}")
            return {
                "status": "success",
                "message": "All Trollama services started successfully",
                "output": stdout_str
            }
        else:
            error_msg = stderr_str or stdout_str or f"Exit code {proc.returncode}"
            logger.error(f"Master startup failed: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Startup failed: {error_msg}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during master startup: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.post("/docker/stop-all")
async def stop_all_containers(
    admin_auth: Dict = Depends(require_admin)
) -> Dict[str, str]:
    """
    Stop all Trollama application services using master shutdown script.

    IMPORTANT: Infrastructure services remain running.

    Services stopped:
    - FastAPI service (main LLM API)
    - Discord bot
    - SGLang (if running)

    Services NOT stopped (infrastructure):
    - Admin service (this API)
    - Auth service (authentication)
    - Web service (admin dashboard UI)
    - Logging service (centralized logs)
    - DynamoDB (database)

    This ensures you can always use the admin dashboard and API.

    Requires admin authentication.

    Returns:
        Success status with message
    """
    admin_user = admin_auth.get("user_id", "unknown")

    # SSH configuration (same as ContainerActionService)
    ssh_host = os.getenv("SSH_HOST", "host.docker.internal")
    ssh_user = os.getenv("SSH_USER", "trosfy")
    ssh_key_path = os.getenv("SSH_KEY_PATH", "/home/app/.ssh/id_ed25519")
    host_project_root = os.getenv("HOST_PROJECT_ROOT", "/home/trosfy/projects/discord-ollama-agent")

    try:
        logger.info(f"Stopping application services by admin {admin_user}")

        # Build SSH command with TTY allocation
        ssh_cmd = [
            "ssh",
            "-t", "-t",  # Force TTY allocation
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10",
            "-o", "LogLevel=ERROR",
            "-i", ssh_key_path,
            f"{ssh_user}@{ssh_host}",
            f"{host_project_root}/scripts/container_management/stop.sh"
        ]

        proc = await asyncio.create_subprocess_exec(
            *ssh_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=300  # 5 minutes for graceful shutdown
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.error("Shutdown timed out after 5 minutes")
            raise HTTPException(
                status_code=504,
                detail="Shutdown operation timed out after 5 minutes"
            )

        stdout_str = stdout.decode() if stdout else ""
        stderr_str = stderr.decode() if stderr else ""

        if proc.returncode == 0:
            logger.info(f"Application services stopped successfully by admin {admin_user}")
            return {
                "status": "success",
                "message": "Application services stopped successfully",
                "note": "Infrastructure services (admin, auth, web, logging, dynamodb) remain running",
                "output": stdout_str
            }
        else:
            error_msg = stderr_str or stdout_str or f"Exit code {proc.returncode}"
            logger.error(f"Shutdown failed: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Shutdown failed: {error_msg}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop services: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop services: {str(e)}")
