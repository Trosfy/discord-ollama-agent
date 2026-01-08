"""Internal API endpoints for service-to-service communication."""
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict
import logging_client

from app.config import settings
from app.dependencies import get_orchestrator

logger = logging_client.setup_logger('fastapi-internal')

router = APIRouter()


# Request/Response Models
class LoadModelRequest(BaseModel):
    """Request to load a model."""
    model_id: str
    temperature: float = 0.7
    additional_args: Optional[Dict] = None


class UnloadModelRequest(BaseModel):
    """Request to unload a model."""
    model_id: str
    crashed: bool = False


class EvictRequest(BaseModel):
    """Request to emergency evict models."""
    priority: str = "NORMAL"  # ModelPriority enum value


# Middleware to verify internal API key
async def verify_internal_api_key(x_internal_api_key: Optional[str] = Header(None)):
    """
    Verify internal API key for service-to-service communication.

    Args:
        x_internal_api_key: API key from X-Internal-API-Key header

    Raises:
        HTTPException: If API key is missing or invalid
    """
    expected_key = settings.INTERNAL_API_KEY
    if not expected_key:
        logger.error("INTERNAL_API_KEY not configured")
        raise HTTPException(
            status_code=500,
            detail="Internal API key not configured"
        )

    if not x_internal_api_key:
        logger.warning("Request missing X-Internal-API-Key header")
        raise HTTPException(
            status_code=401,
            detail="Missing X-Internal-API-Key header"
        )

    if x_internal_api_key != expected_key:
        logger.warning("Invalid internal API key provided")
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )

    return True


@router.get("/vram/status")
async def get_vram_status(
    _: bool = Depends(verify_internal_api_key),
    orchestrator=Depends(get_orchestrator)
):
    """
    Get current VRAM usage and PSI metrics.

    Returns:
        dict: VRAM status with usage, available memory, PSI metrics
    """
    try:
        from app.utils.health_checks import check_vram_status
        status = await check_vram_status()

        logger.debug(f"VRAM status: {status}")
        return status

    except Exception as e:
        logger.error(f"Failed to get VRAM status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vram/models")
async def list_loaded_models(
    _: bool = Depends(verify_internal_api_key),
    orchestrator=Depends(get_orchestrator)
):
    """
    List all currently loaded models.

    Returns:
        list: Loaded models with details
    """
    try:
        registry = orchestrator._registry
        loaded_models = []

        for model_id in registry._loaded_models:
            model = registry.get(model_id)
            if model:
                loaded_models.append({
                    "model_id": model_id,
                    "backend": model.backend.value,
                    "vram_size_gb": model.vram_size_gb,
                    "priority": model.priority.value,
                    "last_accessed": model.last_accessed.isoformat() if model.last_accessed else None,
                    "is_external": model.is_external
                })

        logger.debug(f"Listed {len(loaded_models)} loaded models")
        return {"models": loaded_models}

    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vram/load")
async def load_model(
    request: LoadModelRequest,
    _: bool = Depends(verify_internal_api_key),
    orchestrator=Depends(get_orchestrator)
):
    """
    Load a specific model.

    Args:
        request: Model load request

    Returns:
        dict: Load result
    """
    try:
        logger.info(f"Internal API: Loading model {request.model_id}")

        await orchestrator.request_model_load(
            model_id=request.model_id,
            temperature=request.temperature,
            additional_args=request.additional_args
        )

        return {
            "status": "success",
            "model_id": request.model_id,
            "message": f"Model {request.model_id} loaded successfully"
        }

    except ValueError as e:
        logger.error(f"Invalid model load request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to load model {request.model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vram/unload")
async def unload_model(
    request: UnloadModelRequest,
    _: bool = Depends(verify_internal_api_key),
    orchestrator=Depends(get_orchestrator)
):
    """
    Unload a specific model.

    Args:
        request: Model unload request

    Returns:
        dict: Unload result
    """
    try:
        logger.info(f"Internal API: Unloading model {request.model_id}")

        await orchestrator.mark_model_unloaded(
            model_id=request.model_id,
            crashed=request.crashed
        )

        return {
            "status": "success",
            "model_id": request.model_id,
            "message": f"Model {request.model_id} unloaded successfully"
        }

    except Exception as e:
        logger.error(f"Failed to unload model {request.model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vram/evict")
async def emergency_evict(
    request: EvictRequest,
    _: bool = Depends(verify_internal_api_key),
    orchestrator=Depends(get_orchestrator)
):
    """
    Emergency evict models by priority.

    Args:
        request: Eviction request with priority level

    Returns:
        dict: Eviction result
    """
    try:
        from app.services.vram.interfaces import ModelPriority

        # Parse priority
        try:
            priority = ModelPriority[request.priority.upper()]
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid priority: {request.priority}. Must be one of: LOW, NORMAL, HIGH, CRITICAL"
            )

        logger.warning(f"Internal API: Emergency eviction requested (priority={priority.value})")

        result = await orchestrator.emergency_evict_lru(priority)

        return {
            "status": "success",
            "evicted": result.get("evicted", False),
            "model_id": result.get("model_id"),
            "size_gb": result.get("size_gb"),
            "reason": result.get("reason")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to perform emergency eviction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vram/available-models")
async def list_available_models(
    _: bool = Depends(verify_internal_api_key)
):
    """
    List all available models from default registry + active profile.

    Returns models from default registry with profile-specific overrides.
    This allows users to select any Ollama model in UI, while profile
    controls automatic routing decisions.

    Returns:
        list: Available models with capabilities
    """
    try:
        from app.config import get_active_profile
        from app.config.profiles.default import DEFAULT_MODELS

        profile = get_active_profile()

        # Create profile model lookup for overrides
        profile_models = {m.name: m for m in profile.available_models}

        # Build combined model list: default registry + profile overrides
        available_models = []
        seen_names = set()

        # Add all default registry models (with profile overrides if exist)
        for model in DEFAULT_MODELS:
            # Use profile version if exists, otherwise default
            model_config = profile_models.get(model.name, model)

            available_models.append({
                "name": model_config.name,
                "vram_size_gb": model_config.vram_size_gb,
                "priority": model_config.priority,
                "backend": {
                    "type": model_config.backend.type,
                    "endpoint": model_config.backend.endpoint
                },
                "capabilities": [
                    *([" vision"] if model_config.supports_vision else []),
                    *([" thinking"] if model_config.supports_thinking else []),
                    *([" tools"] if model_config.supports_tools else [])
                ]
            })
            seen_names.add(model_config.name)

        # Add profile-only models (not in default registry)
        for model in profile.available_models:
            if model.name not in seen_names:
                available_models.append({
                    "name": model.name,
                    "vram_size_gb": model.vram_size_gb,
                    "priority": model.priority,
                    "backend": {
                        "type": model.backend.type,
                        "endpoint": model.backend.endpoint
                    },
                    "capabilities": [
                        *([" vision"] if model.supports_vision else []),
                        *([" thinking"] if model.supports_thinking else []),
                        *([" tools"] if model.supports_tools else [])
                    ]
                })

        logger.debug(f"Listed {len(available_models)} available models (default registry + profile)")
        return {"models": available_models}

    except Exception as e:
        logger.error(f"Failed to list available models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Queue Management Endpoints


class MaintenanceModeRequest(BaseModel):
    """Request to set maintenance mode."""
    enabled: bool
    mode: str  # "soft" or "hard"


@router.get("/queue/stats")
async def get_queue_stats(
    _: bool = Depends(verify_internal_api_key)
):
    """
    Get queue statistics.

    Returns:
        dict: Queue size, max size, and full status
    """
    try:
        from app.dependencies import get_queue

        queue = get_queue()

        return {
            "queue_size": queue.size(),
            "is_full": queue.is_full(),
            "max_size": settings.MAX_QUEUE_SIZE
        }

    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue/purge")
async def purge_queue(
    _: bool = Depends(verify_internal_api_key)
):
    """
    Emergency purge of all pending requests in queue.

    This is a destructive operation.

    Returns:
        dict: Number of requests purged
    """
    try:
        from app.dependencies import get_queue

        queue = get_queue()
        initial_size = queue.size()

        # Clear the queue (implementation depends on queue type)
        # For now, dequeue all items
        purged_count = 0
        while queue.size() > 0:
            await queue.dequeue()
            purged_count += 1

        logger.warning(f"Queue purged: {purged_count} requests removed")

        return {
            "status": "success",
            "purged_count": purged_count
        }

    except Exception as e:
        logger.error(f"Failed to purge queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/maintenance")
async def set_maintenance_mode(
    request: MaintenanceModeRequest,
    _: bool = Depends(verify_internal_api_key)
):
    """
    Set maintenance mode.

    Note: This is a placeholder for MVP. In production, this would
    update runtime configuration and persist to database/config file.

    Args:
        request: Maintenance mode settings

    Returns:
        dict: Current maintenance status
    """
    try:
        # For MVP, just return the current settings
        # TODO: Implement runtime config modification
        logger.warning(
            f"Maintenance mode change requested: enabled={request.enabled}, mode={request.mode}"
        )
        logger.warning("Runtime config modification not yet implemented")

        return {
            "status": "accepted",
            "current_soft_maintenance": settings.MAINTENANCE_MODE,
            "current_hard_maintenance": settings.MAINTENANCE_MODE_HARD,
            "note": "Runtime config modification requires restart to take effect"
        }

    except Exception as e:
        logger.error(f"Failed to set maintenance mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_system_health(
    _: bool = Depends(verify_internal_api_key)
):
    """
    Get health status for all services.

    Returns:
        dict: Health status for fastapi-service, DynamoDB, Ollama, VRAM
    """
    try:
        from app.utils.health_checks import (
            check_dynamodb,
            check_ollama,
            check_vram_status
        )

        # Run all health checks
        dynamodb_healthy = await check_dynamodb()
        ollama_healthy = await check_ollama()
        vram_status = await check_vram_status()

        return {
            "services": {
                "fastapi": {
                    "healthy": True,
                    "message": "FastAPI service running"
                },
                "dynamodb": {
                    "healthy": dynamodb_healthy,
                    "message": "Connected" if dynamodb_healthy else "Unreachable"
                },
                "ollama": {
                    "healthy": ollama_healthy,
                    "message": "Connected" if ollama_healthy else "Unreachable"
                },
                "vram": {
                    "healthy": vram_status.get("healthy", False),
                    "warning": vram_status.get("warning", False),
                    "usage_pct": vram_status.get("usage_pct"),
                    "available_gb": vram_status.get("available_gb"),
                    "loaded_models": vram_status.get("loaded_models", 0)
                }
            },
            "details": vram_status
        }

    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))
