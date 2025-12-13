"""WebSocket endpoints for Discord bot communication."""
import sys
sys.path.insert(0, '/shared')

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict
import json

from app.dependencies import (
    get_websocket_manager,
    get_queue,
    get_token_tracker,
    get_storage
)
from app.config import settings
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')


router = APIRouter()


@router.websocket("/ws/discord")
async def discord_websocket(websocket: WebSocket):
    """WebSocket endpoint for Discord bot connection."""
    await websocket.accept()

    ws_manager = get_websocket_manager()
    queue = get_queue()
    token_tracker = get_token_tracker()
    storage = get_storage()

    # Wait for bot to identify itself
    bot_id = None
    try:
        identify_msg = await websocket.receive_text()
        bot_data = json.loads(identify_msg)
        bot_id = bot_data.get('bot_id')

        if not bot_id:
            await websocket.close(code=1008, reason="No bot_id provided")
            return

        # Register connection
        await ws_manager.register(bot_id, websocket)

        # Send acknowledgment
        await websocket.send_json({
            'type': 'connected',
            'bot_id': bot_id
        })

        # Main message loop
        while True:
            data = await websocket.receive_json()

            message_type = data.get('type')

            if message_type == 'message':
                await handle_message_request(
                    data, bot_id, websocket, queue, token_tracker, storage
                )

            elif message_type == 'cancel':
                await handle_cancel_request(data, queue, websocket)

            elif message_type == 'ping':
                await websocket.send_json({'type': 'pong'})

    except WebSocketDisconnect:
        if bot_id:
            await ws_manager.unregister(bot_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if bot_id:
            await ws_manager.unregister(bot_id)
        await websocket.close(code=1011, reason=str(e))


async def handle_message_request(
    data: Dict,
    bot_id: str,
    websocket: WebSocket,
    queue,
    token_tracker,
    storage
):
    """Handle incoming message request from Discord bot."""
    # Log incoming message
    logger.info(f"📨 Received message from user {data.get('user_id')}: {data.get('message')}")

    # Check maintenance mode
    if settings.MAINTENANCE_MODE_HARD:
        await websocket.send_json({
            'type': 'error',
            'error': settings.MAINTENANCE_MESSAGE_HARD
        })
        return

    # Check queue capacity
    if queue.is_full():
        await websocket.send_json({
            'type': 'error',
            'error': 'Queue is full. Please try again in a few minutes.'
        })
        return

    # Get or create user
    user = await storage.get_user(data['user_id'])
    if not user:
        await storage.create_user(
            user_id=data['user_id'],
            discord_username=f"user_{data['user_id'][:8]}",
            user_tier='free'
        )
        user = await storage.get_user(data['user_id'])

    # Estimate tokens
    estimated_tokens = await token_tracker.count_tokens(data['message'])

    # Add to queue
    request = {
        'user_id': data['user_id'],
        'thread_id': data['thread_id'],
        'message': data['message'],
        'message_id': data['message_id'],
        'channel_id': data['channel_id'],
        'estimated_tokens': estimated_tokens,
        'bot_id': bot_id
    }

    try:
        request_id = await queue.enqueue(request)

        # Send queued confirmation
        await websocket.send_json({
            'type': 'queued',
            'request_id': request_id,
            'queue_position': await queue.get_position(request_id),
            'maintenance_mode': settings.MAINTENANCE_MODE
        })

        # Send maintenance warning if applicable
        if settings.MAINTENANCE_MODE:
            await websocket.send_json({
                'type': 'maintenance_warning',
                'message': settings.MAINTENANCE_MESSAGE
            })

    except Exception as e:
        await websocket.send_json({
            'type': 'error',
            'error': str(e)
        })


async def handle_cancel_request(data: Dict, queue, websocket: WebSocket):
    """Handle request cancellation."""
    request_id = data.get('request_id')

    if not request_id:
        await websocket.send_json({
            'type': 'error',
            'error': 'No request_id provided'
        })
        return

    cancelled = await queue.cancel(request_id)

    await websocket.send_json({
        'type': 'cancelled' if cancelled else 'cancel_failed',
        'request_id': request_id,
        'reason': 'Request already processing' if not cancelled else None
    })
