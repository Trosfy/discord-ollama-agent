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
    get_storage,
    get_user_storage,
    get_file_service
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
    storage = get_storage()  # Conversation storage
    user_storage = get_user_storage()  # User data storage

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
                    data, bot_id, websocket, queue, token_tracker, storage, user_storage, ws_manager
                )

            elif message_type == 'reset':
                await handle_reset_request(data, storage, websocket)

            elif message_type == 'close':
                await handle_close_request(data, storage, websocket)

            elif message_type == 'summarize':
                await handle_summarize_request(data, storage, websocket)

            elif message_type == 'cancel':
                await handle_cancel_request(data, queue, websocket)

            elif message_type == 'ping':
                await websocket.send_json({'type': 'pong'})

            elif message_type == 'configure':
                await handle_configure_request(data, user_storage, websocket)

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
    storage,
    user_storage,
    ws_manager
):
    """Handle incoming message request from Discord bot."""
    # Log incoming message
    logger.info(f"📨 Received message from user {data.get('user_id')}: {data.get('message')}")

    # Check maintenance mode
    if settings.MAINTENANCE_MODE_HARD:
        await websocket.send_json({
            'type': 'error',
            'error': settings.MAINTENANCE_MESSAGE_HARD,
            'channel_id': data.get('channel_id'),
            'message_id': data.get('message_id')
        })
        return

    # Check queue capacity
    if queue.is_full():
        await websocket.send_json({
            'type': 'error',
            'error': 'Queue is full. Please try again in a few minutes.',
            'channel_id': data.get('channel_id'),
            'message_id': data.get('message_id')
        })
        return

    # Get or create user
    user_tokens = await user_storage.get_user_tokens(data['user_id'])
    if not user_tokens:
        await user_storage.create_user(
            user_id=data['user_id'],
            discord_username=f"user_{data['user_id'][:8]}",
            user_tier='free'
        )
        user_tokens = await user_storage.get_user_tokens(data['user_id'])

    # Process file attachments if present
    file_refs = []
    attachments = data.get('attachments', [])

    if attachments:
        # Send early status indicator BEFORE processing files
        await ws_manager.send_status_indicator(
            bot_id=bot_id,
            channel_id=data['channel_id'],
            message_id=data['message_id'],
            status_type='processing_files',
            request_id='pending',
            message_channel_id=data.get('message_channel_id')
        )

        logger.info(f"📎 Processing {len(attachments)} file attachment(s)")
        file_service = get_file_service()

        for attachment_data in attachments:
            try:
                # Decode base64 file data
                import base64
                file_data = base64.b64decode(attachment_data['data_base64'])

                # Save temp file and process (OCR for images, etc.)
                file_info = await file_service.save_temp_file(
                    file_data=file_data,
                    filename=attachment_data['filename'],
                    content_type=attachment_data['content_type'],
                    user_id=data['user_id']
                )

                file_refs.append(file_info)
                logger.info(f"✅ Processed attachment: {attachment_data['filename']} → {file_info['file_id']}")

            except Exception as e:
                logger.error(f"❌ Failed to process attachment {attachment_data.get('filename')}: {e}")
                # Continue processing other attachments even if one fails

    # Estimate tokens (include file content in estimation)
    message_with_files = data['message']
    if file_refs:
        # Add extracted content to token estimation
        for file_ref in file_refs:
            extracted = file_ref.get('extracted_content', '')
            if extracted:
                message_with_files += f"\n[File: {file_ref['filename']}]\n{extracted}"

    estimated_tokens = await token_tracker.count_tokens(message_with_files)

    # Add to queue
    request = {
        'user_id': data['user_id'],
        'conversation_id': data['conversation_id'],
        'message': data['message'],
        'message_id': data['message_id'],
        'channel_id': data['channel_id'],
        'message_channel_id': data.get('message_channel_id'),  # Where the original message is (for reactions)
        'estimated_tokens': estimated_tokens,
        'bot_id': bot_id,
        'file_refs': file_refs  # NEW: Include processed file references
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
            'error': str(e),
            'channel_id': data.get('channel_id'),
            'message_id': data.get('message_id')
        })


async def handle_reset_request(data: Dict, storage, websocket: WebSocket):
    """Handle thread context reset request."""
    conversation_id = data.get('conversation_id')
    user_id = data.get('user_id')

    if not conversation_id:
        await websocket.send_json({
            'type': 'error',
            'error': 'No conversation_id provided'
        })
        return

    try:
        # Get all messages in thread
        messages = await storage.get_conversation_messages(conversation_id)

        if not messages:
            logger.info(f"Thread {conversation_id} has no messages to delete")
            await websocket.send_json({
                'type': 'reset_complete',
                'conversation_id': conversation_id,
                'deleted_count': 0
            })
            return

        # Delete all messages
        timestamps = [msg['message_timestamp'] for msg in messages]
        await storage.delete_messages(conversation_id, timestamps)

        logger.info(f"🔄 Reset thread {conversation_id}: deleted {len(timestamps)} messages (user: {user_id})")

        await websocket.send_json({
            'type': 'reset_complete',
            'conversation_id': conversation_id,
            'deleted_count': len(timestamps)
        })

    except Exception as e:
        logger.error(f"Failed to reset thread {conversation_id}: {e}")
        await websocket.send_json({
            'type': 'error',
            'error': f'Failed to reset thread: {str(e)}'
        })


async def handle_close_request(data: Dict, storage, websocket: WebSocket):
    """Handle thread close and delete request."""
    conversation_id = data.get('conversation_id')
    user_id = data.get('user_id')

    if not conversation_id:
        await websocket.send_json({
            'type': 'error',
            'error': 'No conversation_id provided'
        })
        return

    try:
        # Get all messages in thread
        messages = await storage.get_conversation_messages(conversation_id)

        if not messages:
            logger.info(f"Thread {conversation_id} has no messages to delete")
            await websocket.send_json({
                'type': 'close_complete',
                'conversation_id': conversation_id,
                'deleted_count': 0
            })
            return

        # Delete all messages
        timestamps = [msg['message_timestamp'] for msg in messages]
        await storage.delete_messages(conversation_id, timestamps)

        logger.info(f"🗑️ Closed thread {conversation_id}: deleted {len(timestamps)} messages (user: {user_id})")

        await websocket.send_json({
            'type': 'close_complete',
            'conversation_id': conversation_id,
            'deleted_count': len(timestamps)
        })

    except Exception as e:
        logger.error(f"Failed to close thread {conversation_id}: {e}")
        await websocket.send_json({
            'type': 'error',
            'error': f'Failed to close thread: {str(e)}'
        })


async def handle_summarize_request(data: Dict, storage, websocket: WebSocket):
    """Handle thread summarization request."""
    from app.dependencies import get_summarization_service

    conversation_id = data.get('conversation_id')
    user_id = data.get('user_id')
    interaction_id = data.get('interaction_id')

    if not conversation_id:
        await websocket.send_json({
            'type': 'error',
            'error': 'No conversation_id provided',
            'interaction_id': interaction_id
        })
        return

    try:
        # Get all messages in thread
        messages = await storage.get_conversation_messages(conversation_id)

        if not messages:
            logger.info(f"Thread {conversation_id} has no messages to summarize")
            await websocket.send_json({
                'type': 'summarize_response',
                'conversation_id': conversation_id,
                'summary': None,
                'interaction_id': interaction_id
            })
            return

        # Get summarization service
        summarization_service = get_summarization_service()

        # Generate summary
        logger.info(f"📝 Generating summary for thread {conversation_id} ({len(messages)} messages)")
        summary = await summarization_service.generate_summary(messages)

        # Delete all old messages
        timestamps = [msg['message_timestamp'] for msg in messages]
        await storage.delete_messages(conversation_id, timestamps)

        # Add summary as new message
        import time
        from datetime import datetime

        summary_timestamp = datetime.utcnow().isoformat()
        await storage.add_message(
            conversation_id=conversation_id,
            message_id=f"summary_{int(time.time())}",
            role='system',
            content=f"[Previous conversation summary]\n{summary}",
            token_count=len(summary) // 4,  # Rough estimate
            user_id=user_id,
            model_used='summary',
            is_summary=True
        )

        logger.info(f"📝 Summarized thread {conversation_id}: {len(timestamps)} messages → summary (user: {user_id})")

        # Send summary back to user
        await websocket.send_json({
            'type': 'summarize_response',
            'conversation_id': conversation_id,
            'summary': summary,
            'interaction_id': interaction_id,
            'messages_summarized': len(timestamps)
        })

    except Exception as e:
        logger.error(f"Failed to summarize thread {conversation_id}: {e}")
        await websocket.send_json({
            'type': 'summarize_response',
            'conversation_id': conversation_id,
            'error': str(e),
            'interaction_id': interaction_id
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


async def handle_configure_request(data: Dict, user_storage, websocket: WebSocket):
    """Handle user preference configuration request."""
    from app.config import get_available_model_names

    user_id = data.get('user_id')
    setting = data.get('setting')
    value = data.get('value')
    interaction_id = data.get('interaction_id')

    if not user_id or not setting:
        await websocket.send_json({
            'type': 'configure_response',
            'error': 'Missing user_id or setting',
            'interaction_id': interaction_id
        })
        return

    try:
        # Get current user preferences for response
        user_prefs = await user_storage.get_user_preferences(user_id)
        if not user_prefs:
            # User doesn't exist yet - create with defaults
            await user_storage.create_user(
                user_id=user_id,
                discord_username=f"user_{user_id[:8]}",
                user_tier='free'
            )
            user_prefs = await user_storage.get_user_preferences(user_id)

        # Handle different settings
        if setting == 'temperature':
            # Validate temperature value
            if value is not None:
                try:
                    temp_float = float(value)
                    if not 0.0 <= temp_float <= 2.0:
                        raise ValueError("Temperature must be between 0.0 and 2.0")
                    value = temp_float
                except (ValueError, TypeError) as e:
                    await websocket.send_json({
                        'type': 'configure_response',
                        'error': f'Invalid temperature value: {str(e)}',
                        'interaction_id': interaction_id
                    })
                    return

            # Update temperature
            await user_storage.update_temperature(user_id, value)

            # Build response message
            current_display = f"{value}" if value is not None else "default"
            system_default = settings.DEFAULT_TEMPERATURE
            message = f"✅ Temperature set to **{current_display}**\n"
            message += f"Current: {value if value is not None else system_default} | System default: {system_default}"

            logger.info(f"⚙️  Updated temperature for user {user_id}: {current_display}")

        elif setting == 'thinking':
            # Update thinking mode
            await user_storage.update_thinking(user_id, value)

            # Build response message
            if value is True:
                current_display = "enabled (force on)"
            elif value is False:
                current_display = "disabled (force off)"
            else:
                current_display = "default (auto-detect)"

            message = f"✅ Thinking mode set to **{current_display}**\n"
            message += f"Thinking will be {'always enabled' if value is True else 'always disabled' if value is False else 'automatically enabled for REASONING/RESEARCH routes'}"

            logger.info(f"⚙️  Updated thinking mode for user {user_id}: {current_display}")

        elif setting == 'model':
            # Validate model name
            if value is not None and value != 'trollama':
                available_models = get_available_model_names()
                if value not in available_models:
                    await websocket.send_json({
                        'type': 'configure_response',
                        'error': f"Model '{value}' not available. Choose from: {', '.join(available_models)}",
                        'interaction_id': interaction_id
                    })
                    return

            # Update model preference
            await user_storage.update_model(user_id, value)

            # Build response message
            current_display = value if value else "System Recommendation"
            message = f"✅ Preferred model set to **{current_display}**\n"
            message += f"Current: {current_display} | System default: System Recommendation"

            logger.info(f"⚙️  Updated preferred model for user {user_id}: {current_display}")

        elif setting == 'reset':
            # Reset all preferences to defaults
            await user_storage.reset_preferences(user_id)

            # Build response message
            message = f"✅ All preferences reset to system defaults\n"
            message += f"Temperature: {settings.DEFAULT_TEMPERATURE} | Thinking: auto | Model: System Recommendation"

            logger.info(f"⚙️  Reset all preferences for user {user_id}")

        else:
            await websocket.send_json({
                'type': 'configure_response',
                'error': f"Unknown setting: {setting}",
                'interaction_id': interaction_id
            })
            return

        # Send success response
        await websocket.send_json({
            'type': 'configure_response',
            'success': True,
            'message': message,
            'setting': setting,
            'value': value,
            'interaction_id': interaction_id
        })

    except Exception as e:
        logger.error(f"Failed to configure {setting} for user {user_id}: {e}")
        await websocket.send_json({
            'type': 'configure_response',
            'error': f'Failed to update {setting}: {str(e)}',
            'interaction_id': interaction_id
        })
