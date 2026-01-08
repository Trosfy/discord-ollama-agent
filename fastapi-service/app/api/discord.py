"""Discord-specific REST endpoints (optional, for direct API access)."""
from fastapi import APIRouter, HTTPException, Depends
from app.models.requests import MessageRequest
from app.models.responses import QueuedResponse
from app.dependencies import get_queue, get_token_tracker, get_storage
from app.config import settings


router = APIRouter()


@router.post("/message", response_model=QueuedResponse)
async def submit_message(
    request: MessageRequest,
    queue=Depends(get_queue),
    token_tracker=Depends(get_token_tracker),
    storage=Depends(get_storage)
):
    """
    Submit a message via REST API (alternative to WebSocket).

    Args:
        request: MessageRequest with user_id, thread_id, message, etc.

    Returns:
        QueuedResponse with request_id and queue position

    Raises:
        HTTPException: If maintenance mode or queue full
    """
    if settings.MAINTENANCE_MODE_HARD:
        raise HTTPException(
            status_code=503,
            detail=settings.MAINTENANCE_MESSAGE_HARD
        )

    if queue.is_full():
        raise HTTPException(
            status_code=429,
            detail="Queue is full. Please try again later."
        )

    # Get or create user
    user = await storage.get_user(request.user_id)
    if not user:
        await storage.create_user(
            user_id=request.user_id,
            discord_username=f"user_{request.user_id[:8]}"
        )

    estimated_tokens = await token_tracker.count_tokens(request.message)

    queue_request = {
        'user_id': request.user_id,
        'thread_id': request.thread_id,
        'message': request.message,
        'message_id': request.message_id,
        'channel_id': request.channel_id,
        'estimated_tokens': estimated_tokens,
        'bot_id': None  # No WebSocket callback for REST
    }

    request_id = await queue.enqueue(queue_request)
    position = await queue.get_position(request_id)

    return QueuedResponse(
        request_id=request_id,
        queue_position=position,
        eta_seconds=position * 30  # Rough estimate
    )


@router.get("/status/{request_id}")
async def get_request_status(request_id: str, queue=Depends(get_queue)):
    """
    Get status of a queued request.

    Args:
        request_id: Unique request identifier

    Returns:
        Status dictionary
    """
    status = await queue.get_status(request_id)
    return status


@router.delete("/cancel/{request_id}")
async def cancel_request(request_id: str, queue=Depends(get_queue)):
    """
    Cancel a queued request.

    Args:
        request_id: Unique request identifier

    Returns:
        Cancellation status

    Raises:
        HTTPException: If request cannot be cancelled
    """
    cancelled = await queue.cancel(request_id)
    if not cancelled:
        raise HTTPException(
            status_code=400,
            detail="Request cannot be cancelled (already processing)"
        )
    return {"status": "cancelled", "request_id": request_id}
