"""VRAM monitoring API endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
import logging

from app.clients.vram_client import VRAMClient
from app.dependencies import get_vram_client
from app.middleware.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/vram", tags=["vram"])


@router.get("/status")
async def get_vram_status(
    admin_auth: Dict = Depends(require_admin),
    client: VRAMClient = Depends(get_vram_client)
):
    """
    Get current VRAM status including usage, PSI metrics, and loaded models.

    Requires admin authentication.

    Returns:
        dict: {
            "memory": {
                "total_gb": float,
                "used_gb": float,
                "available_gb": float,
                "usage_pct": float,
                "psi_some_avg10": float,
                "psi_full_avg10": float
            },
            "loaded_models": [...],
            "healthy": bool
        }
    """
    try:
        status = await client.get_status()
        return status

    except Exception as e:
        logger.error(f"Failed to get VRAM status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_vram_health(
    admin_auth: Dict = Depends(require_admin),
    client: VRAMClient = Depends(get_vram_client)
):
    """
    Get VRAM orchestrator health status.

    Returns simplified health check suitable for monitoring systems.

    Requires admin authentication.

    Returns:
        dict: {
            "healthy": bool,
            "usage_pct": float,
            "psi_full_avg10": float,
            "loaded_models_count": int
        }
    """
    try:
        status = await client.get_status()

        # Extract health indicators
        memory = status.get("memory", {})
        loaded_models = status.get("loaded_models", [])

        return {
            "healthy": status.get("healthy", False),
            "usage_pct": memory.get("usage_pct", 0.0),
            "psi_full_avg10": memory.get("psi_full_avg10", 0.0),
            "available_gb": memory.get("available_gb", 0.0),
            "loaded_models_count": len(loaded_models)
        }

    except Exception as e:
        logger.error(f"Failed to get VRAM health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{model_id}")
async def get_model_details(
    model_id: str,
    admin_auth: Dict = Depends(require_admin),
    client: VRAMClient = Depends(get_vram_client)
):
    """
    Get details for a specific loaded model.

    Requires admin authentication.

    Args:
        model_id: Model identifier

    Returns:
        dict: Model details including VRAM usage, priority, last access time
    """
    try:
        # Get all loaded models
        result = await client.list_models()
        models = result.get("models", [])

        # Find the specific model
        model = next(
            (m for m in models if m["model_id"] == model_id),
            None
        )

        if not model:
            raise HTTPException(
                status_code=404,
                detail=f"Model {model_id} not found in loaded models"
            )

        return model

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model details for {model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
