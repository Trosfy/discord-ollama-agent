"""Model management API endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
import logging

from app.models import (
    LoadModelRequest,
    UnloadModelRequest,
    EvictRequest,
    ModelListResponse,
    LoadModelResponse,
    UnloadModelResponse,
    EvictResponse,
    ModelInfo
)
from app.services.model_service import ModelService
from app.services.ollama_service import OllamaService
from app.services.vram_validator import VRAMValidator
from app.dependencies import get_model_service, get_ollama_service, get_vram_validator
from app.middleware.auth import require_admin
from app.backend_registry import BackendRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/models", tags=["models"])


@router.get("/list", response_model=ModelListResponse)
async def list_available_models(
    admin_auth: Dict = Depends(require_admin),
    service: ModelService = Depends(get_model_service),
    ollama_service: OllamaService = Depends(get_ollama_service)
):
    """
    List all available models from profile configuration with loaded status.

    Checks Ollama /api/ps to mark which models are currently loaded in VRAM.

    Requires admin authentication.

    Returns:
        ModelListResponse: List of available models with capabilities and loaded status
    """
    try:
        models_data = await service.list_available_models()

        # Get currently loaded models from Ollama
        loaded_model_names = set()
        try:
            loaded_models = await ollama_service.list_loaded_models()
            loaded_model_names = {m.get("name") for m in loaded_models if m.get("name")}
        except Exception as e:
            logger.warning(f"Failed to fetch loaded models from Ollama: {e}")

        # Convert to ModelInfo format with accurate is_loaded flag
        models = [
            ModelInfo(
                name=m["name"],
                vram_size_gb=m["vram_size_gb"],
                priority=m["priority"],
                backend=m["backend"],
                capabilities=m.get("capabilities", []),
                is_loaded=m["name"] in loaded_model_names
            )
            for m in models_data
        ]

        return ModelListResponse(
            models=models,
            count=len(models)
        )

    except Exception as e:
        logger.error(f"Failed to list available models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/loaded", response_model=ModelListResponse)
async def list_loaded_models(
    admin_auth: Dict = Depends(require_admin),
    service: ModelService = Depends(get_model_service)
):
    """
    List currently loaded models in VRAM.

    Requires admin authentication.

    Returns:
        ModelListResponse: List of loaded models with VRAM usage
    """
    try:
        models_data = await service.list_loaded_models()

        # Convert to ModelInfo format
        models = [
            ModelInfo(
                name=m["model_id"],
                vram_size_gb=m["vram_size_gb"],
                priority=m["priority"],
                backend={"type": m["backend"], "endpoint": ""},
                capabilities=None,
                is_loaded=True,
                last_accessed=m.get("last_accessed")
            )
            for m in models_data
        ]

        return ModelListResponse(
            models=models,
            count=len(models)
        )

    except Exception as e:
        logger.error(f"Failed to list loaded models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load", response_model=LoadModelResponse)
async def load_model(
    request: LoadModelRequest,
    admin_auth: Dict = Depends(require_admin),
    service: ModelService = Depends(get_model_service),
    ollama_service: OllamaService = Depends(get_ollama_service),
    vram_validator: VRAMValidator = Depends(get_vram_validator)
):
    """
    Load a specific model into VRAM or prewarm it.

    - SGLang models: Cannot be loaded via API (managed by container lifecycle)
    - Ollama models: Prewarm into memory for 10 minutes (with capacity validation)

    Requires admin authentication.

    Args:
        request: Model load request with model_id and optional priority

    Returns:
        LoadModelResponse: Load result with status
    """
    try:
        admin_user = admin_auth.get("user_id", "unknown")
        model_id = request.model_id

        # Determine backend for this model
        # Simple heuristic: models with "/" are SGLang (e.g., "openai/gpt-oss-120b")
        # Everything else is Ollama
        backend_type = "sglang" if "/" in model_id else "ollama"

        # Handle based on backend type
        if backend_type == "sglang":
            raise HTTPException(
                status_code=400,
                detail="SGLang models cannot be loaded via API. Use container management to start/stop SGLang services."
            )

        elif backend_type == "ollama":
            # Validate VRAM capacity before loading
            is_valid, error_msg = await vram_validator.validate_capacity(model_id)

            if not is_valid:
                logger.warning(
                    f"Admin {admin_user} blocked from loading {model_id}: {error_msg}"
                )
                raise HTTPException(
                    status_code=400,
                    detail=error_msg
                )

            # Capacity check passed - proceed with prewarming
            # Handles both text generation and embedding models automatically
            logger.info(f"Admin {admin_user} prewarming Ollama model: {model_id}")
            result = await ollama_service.prewarm_model(model_id)

            return LoadModelResponse(
                status="success",
                model_id=model_id,
                message=result["message"],
                details=result
            )

        else:
            raise HTTPException(status_code=400, detail=f"Unknown backend type: {backend_type}")

    except HTTPException:
        raise

    except ValueError as e:
        # Client-side error (invalid model, insufficient VRAM, etc.)
        logger.warning(f"Invalid load request: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unload", response_model=UnloadModelResponse)
async def unload_model(
    request: UnloadModelRequest,
    admin_auth: Dict = Depends(require_admin),
    service: ModelService = Depends(get_model_service),
    ollama_service: OllamaService = Depends(get_ollama_service)
):
    """
    Unload a specific model from VRAM or memory.

    - SGLang models: Cannot be unloaded via API (managed by container lifecycle)
    - Ollama models: Unload from memory immediately

    Requires admin authentication.

    Args:
        request: Model unload request with model_id

    Returns:
        UnloadModelResponse: Unload result with freed VRAM
    """
    try:
        admin_user = admin_auth.get("user_id", "unknown")
        model_id = request.model_id

        # Determine backend for this model
        # Simple heuristic: models with "/" are SGLang (e.g., "openai/gpt-oss-120b")
        # Everything else is Ollama
        backend_type = "sglang" if "/" in model_id else "ollama"

        # Handle based on backend type
        if backend_type == "sglang":
            raise HTTPException(
                status_code=400,
                detail="SGLang models cannot be unloaded via API. Use container management to start/stop SGLang services."
            )

        elif backend_type == "ollama":
            # Unload Ollama model immediately
            # Handles both text generation and embedding models automatically
            logger.info(f"Admin {admin_user} unloading Ollama model: {model_id}")
            result = await ollama_service.unload_model(model_id)

            return UnloadModelResponse(
                status="success",
                model_id=model_id,
                message=result["message"],
                freed_vram_gb=0.0  # Ollama doesn't report freed VRAM
            )

        else:
            raise HTTPException(status_code=400, detail=f"Unknown backend type: {backend_type}")

    except HTTPException:
        raise

    except ValueError as e:
        logger.warning(f"Invalid unload request: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to unload model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evict", response_model=EvictResponse)
async def emergency_evict(
    request: EvictRequest,
    admin_auth: Dict = Depends(require_admin),
    service: ModelService = Depends(get_model_service)
):
    """
    Trigger emergency eviction of LRU model at specified priority.

    This is a destructive operation that forcefully unloads models.

    Requires admin authentication.

    Args:
        request: Eviction request with priority threshold

    Returns:
        EvictResponse: Eviction result
    """
    try:
        admin_user = admin_auth.get("user_id", "unknown")

        result = await service.emergency_evict(
            priority=request.priority,
            admin_user=admin_user
        )

        return EvictResponse(**result)

    except ValueError as e:
        logger.warning(f"Invalid eviction request: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to trigger eviction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_models_summary(
    admin_auth: Dict = Depends(require_admin)
):
    """
    Get summary of models (with accurate loaded state) and queue status.

    Uses SystemMetricsService to fetch models with accurate is_loaded status:
    - Ollama: Syncs with /api/ps to show actually loaded models (from any source)
    - SGLang: Shows models only when container is running

    Also fetches queue size from fastapi-service.

    Requires admin authentication.

    Returns:
        dict: Models and queue summary with {loaded_models: [], queue_size: int}
    """
    import httpx
    from app.config import settings
    from app.services.system_metrics_service import SystemMetricsService

    try:
        # Use SystemMetricsService to get accurate model state (same as SSE stream)
        system_metrics = SystemMetricsService()

        # Fetch loaded models with accurate is_loaded flag
        loaded_models = await system_metrics.fetch_loaded_models()

        # Fetch queue size from fastapi-service
        queue_size = 0
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                fastapi_response = await client.get(f"{settings.FASTAPI_URL}/health")
                if fastapi_response.status_code == 200:
                    health_data = fastapi_response.json()
                    queue_size = health_data.get("queue_size", 0)
            except Exception as e:
                logger.warning(f"Failed to fetch queue stats: {e}")

        return {
            "loaded_models": loaded_models,
            "loaded_count": len(loaded_models),
            "queue_size": queue_size
        }

    except Exception as e:
        logger.error(f"Failed to get models summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
