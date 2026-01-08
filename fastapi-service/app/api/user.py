"""User endpoints for preference management."""
from fastapi import APIRouter, HTTPException, Depends
from app.models.requests import UpdatePreferencesRequest
from app.models.responses import UserResponse
from app.dependencies import get_storage
from app.utils.validators import validate_model, validate_temperature


router = APIRouter()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, storage=Depends(get_storage)):
    """
    Get user information.

    Args:
        user_id: User identifier

    Returns:
        UserResponse with user data

    Raises:
        HTTPException: If user not found
    """
    user = await storage.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        user_id=user['user_id'],
        discord_username=user['discord_username'],
        user_tier=user['user_tier'],
        preferred_model=user['preferred_model'],
        temperature=float(user['temperature']),
        tokens_remaining=int(user['tokens_remaining']),
        weekly_budget=int(user['weekly_token_budget'])
    )


@router.patch("/{user_id}/preferences")
async def update_preferences(
    user_id: str,
    request: UpdatePreferencesRequest,
    storage=Depends(get_storage)
):
    """
    Update user preferences.

    Args:
        user_id: User identifier
        request: UpdatePreferencesRequest with optional fields

    Returns:
        Update status

    Raises:
        HTTPException: If user not found or validation fails
    """
    user = await storage.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate inputs
    updates = {}
    if request.preferred_model:
        updates['preferred_model'] = validate_model(request.preferred_model)
    if request.temperature is not None:
        updates['temperature'] = str(validate_temperature(request.temperature))
    if request.base_prompt is not None:
        updates['base_prompt'] = request.base_prompt

    # Apply updates (simplified - would need proper DynamoDB update)
    # For MVP, this is a placeholder
    return {"status": "updated", "user_id": user_id, "updates": updates}


@router.get("/{user_id}/history")
async def get_user_history(user_id: str, storage=Depends(get_storage)):
    """
    Get user's conversation threads.

    Args:
        user_id: User identifier

    Returns:
        Dictionary with user_id and list of thread IDs
    """
    threads = await storage.get_user_threads(user_id)
    return {"user_id": user_id, "threads": threads}
