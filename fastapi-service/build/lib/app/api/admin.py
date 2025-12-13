"""Admin endpoints for system management."""
from fastapi import APIRouter, HTTPException, Depends
from app.models.requests import GrantTokensRequest
from app.dependencies import get_storage, get_queue
from app.config import settings


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
