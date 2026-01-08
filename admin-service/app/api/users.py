"""User management API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Dict, Optional
import logging

from app.services.user_service import UserService
from app.dependencies import get_user_service
from app.middleware.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/users", tags=["users"])


# Request Models
class GrantTokensRequest(BaseModel):
    """Request to grant tokens to a user."""
    amount: int = Field(..., gt=0, description="Number of tokens to grant")
    reason: Optional[str] = Field(None, description="Reason for granting tokens")


class BanUserRequest(BaseModel):
    """Request to ban a user."""
    reason: str = Field(..., min_length=1, description="Reason for ban")


@router.post("/{user_id}/grant-tokens")
async def grant_tokens(
    user_id: str,
    request: GrantTokensRequest,
    admin_auth: Dict = Depends(require_admin),
    service: UserService = Depends(get_user_service)
):
    """
    Grant bonus tokens to a user.

    Requires admin authentication.

    Args:
        user_id: User ID to grant tokens to
        request: Grant tokens request with amount and optional reason

    Returns:
        dict: Operation result with new token balance
    """
    try:
        admin_user = admin_auth.get("user_id", "unknown")

        result = await service.grant_tokens(
            user_id=user_id,
            amount=request.amount,
            admin_user=admin_user,
            reason=request.reason
        )

        return result

    except ValueError as e:
        logger.warning(f"Invalid grant tokens request: {e}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to grant tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{user_id}/ban")
async def ban_user(
    user_id: str,
    request: BanUserRequest,
    admin_auth: Dict = Depends(require_admin),
    service: UserService = Depends(get_user_service)
):
    """
    Ban a user from using the service.

    This is a destructive operation that prevents the user from making requests.

    Requires admin authentication.

    Args:
        user_id: User ID to ban
        request: Ban request with reason

    Returns:
        dict: Operation result
    """
    try:
        admin_user = admin_auth.get("user_id", "unknown")

        result = await service.ban_user(
            user_id=user_id,
            admin_user=admin_user,
            reason=request.reason
        )

        return result

    except ValueError as e:
        logger.warning(f"Invalid ban request: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to ban user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{user_id}/unban")
async def unban_user(
    user_id: str,
    admin_auth: Dict = Depends(require_admin),
    service: UserService = Depends(get_user_service)
):
    """
    Unban a previously banned user.

    Requires admin authentication.

    Args:
        user_id: User ID to unban

    Returns:
        dict: Operation result
    """
    try:
        admin_user = admin_auth.get("user_id", "unknown")

        result = await service.unban_user(
            user_id=user_id,
            admin_user=admin_user
        )

        return result

    except ValueError as e:
        logger.warning(f"Invalid unban request: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to unban user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_all_users(
    limit: int = Query(100, ge=1, le=500, description="Maximum number of users to return"),
    offset: int = Query(0, ge=0, description="Number of users to skip"),
    admin_auth: Dict = Depends(require_admin),
    service: UserService = Depends(get_user_service)
):
    """
    List all users with pagination.

    Requires admin authentication.

    Args:
        limit: Maximum number of users to return (1-500)
        offset: Number of users to skip (for pagination)

    Returns:
        dict: List of users with pagination info
    """
    try:
        result = await service.list_all_users(limit=limit, offset=offset)
        return result

    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}")
async def get_user_stats(
    user_id: str,
    admin_auth: Dict = Depends(require_admin),
    service: UserService = Depends(get_user_service)
):
    """
    Get detailed stats for a specific user.

    Requires admin authentication.

    Args:
        user_id: User ID to get stats for

    Returns:
        dict: User stats including tokens, tier, preferences, ban status
    """
    try:
        stats = await service.get_user_stats(user_id)
        return stats

    except ValueError as e:
        logger.warning(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to get user stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
