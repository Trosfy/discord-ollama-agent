"""
Chat WebSocket API - Real-time Token Streaming

Provides WebSocket endpoint for streaming chat responses token-by-token.
REQUIRED feature (per plan) for real-time user ↔ Trollama conversation.
"""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi import status

from app.dependencies import get_queue, get_storage, get_ws_manager, get_token_tracker
from app.interfaces.storage import IConversationStorage
from app.interfaces.queue import QueueInterface
from app.interfaces.websocket import WebSocketInterface
from app.services.token_tracker import TokenTracker

import logging_client

logger = logging_client.setup_logger("chat_ws")

router = APIRouter()


@router.websocket("/ws/chat/{conversation_id}")
async def chat_websocket(
    websocket: WebSocket,
    conversation_id: str,
    queue: QueueInterface = Depends(get_queue),
    storage: IConversationStorage = Depends(get_storage),
    ws_manager: WebSocketInterface = Depends(get_ws_manager),
    token_tracker: TokenTracker = Depends(get_token_tracker),
):
    """
    WebSocket endpoint for real-time chat streaming.

    Architecture: All messages go through the queue (same as Discord).
    This ensures proper decoupling, rate limiting, and monitoring.
    Uses ws_manager pattern for unified WebSocket management.

    Protocol:
    1. Client sends: {"type": "message", "content": "user message", "model": "llama2"}
    2. Server enqueues request and returns request_id
    3. Server streams: {"type": "token", "content": "token"}
    4. Server sends: {"type": "done", "message_id": "...", "tokens_used": 123}
    5. On error: {"type": "error", "error": "error message"}

    Args:
        websocket: WebSocket connection
        conversation_id: Conversation ID
        queue: Request queue
        storage: Conversation storage
        ws_manager: WebSocket manager (unified with Discord)
    """
    # Validate origin for CORS (WebSocket doesn't use CORS middleware)
    origin = websocket.headers.get("origin")
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:8502",
        "http://dgx-spark.netbird.cloud:8080",  # Production web UI (HTTP)
        "https://dgx-spark.netbird.cloud",
    ]

    if origin and origin not in allowed_origins:
        logger.warning(f"WebSocket connection rejected: invalid origin {origin}")
        await websocket.close(code=1008)  # Policy violation
        return

    await websocket.accept()

    # Register WebSocket connection in ws_manager (same pattern as Discord)
    client_id = f"webui_{conversation_id}"
    await ws_manager.register(client_id, websocket)
    logger.info(f"WebSocket connected: conversation_id={conversation_id}, client_id={client_id}")

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message_type = data.get("type")

            if message_type == "message":
                # Extract message details
                user_message = data.get("content", "")
                model = data.get("model")
                temperature = data.get("temperature", 0.7)
                thinking_enabled = data.get("thinking_enabled")  # None = model default
                enable_web_search = data.get("enable_web_search", True)
                file_refs = data.get("file_refs", [])  # Pre-uploaded file references

                if not user_message and not file_refs:
                    await websocket.send_json({
                        "type": "error",
                        "error": "Message content or file attachments required"
                    })
                    continue

                logger.info(f"Received message: conversation_id={conversation_id}, length={len(user_message)}, files={len(file_refs)}")

                try:
                    # TODO: Get user_id from WebSocket auth/session
                    user_id = "websocket_user"  # Placeholder

                    # Include file content in token estimation (same as Discord)
                    message_for_estimation = user_message
                    if file_refs:
                        for file_ref in file_refs:
                            extracted = file_ref.get('extracted_content', '')
                            if extracted:
                                message_for_estimation += f"\n[File: {file_ref.get('filename', 'unknown')}]\n{extracted}"

                    # Estimate tokens for budget tracking (same as Discord)
                    estimated_tokens = await token_tracker.count_tokens(message_for_estimation)

                    # Build request for queue (same structure as Discord)
                    request = {
                        "user_id": user_id,
                        "conversation_id": conversation_id,
                        "message": user_message or "Please analyze the attached file(s).",
                        "model": model,
                        "temperature": temperature,
                        "thinking_enabled": thinking_enabled,  # True/False/None (model default)
                        "enable_web_search": enable_web_search,
                        "estimated_tokens": estimated_tokens,
                        "webui_client_id": client_id,  # Use client_id like Discord uses bot_id
                        "file_refs": file_refs,  # Include file references for orchestrator
                        "metadata": {
                            "source": "webui",
                            "timestamp": asyncio.get_event_loop().time(),
                        }
                    }

                    # Enqueue request (goes through queue like Discord messages)
                    request_id = await queue.enqueue(request)

                    # Get queue position
                    position = await queue.get_position(request_id)

                    # Send acknowledgment with queue info
                    await websocket.send_json({
                        "type": "queued",
                        "request_id": request_id,
                        "queue_position": position,
                    })

                    logger.info(f"Enqueued request: request_id={request_id}, position={position}")

                    # Note: Queue worker will process this request and stream tokens
                    # back through ws_manager.send_to_client(client_id, ...).
                    # The actual streaming happens in the queue worker, not here.

                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "error": str(e)
                    })

            elif message_type == "ping":
                # Keep-alive ping
                await websocket.send_json({"type": "pong"})

            elif message_type == "history":
                # Fetch conversation history from DynamoDB
                try:
                    messages = await storage.get_conversation_messages(conversation_id)
                    
                    # Convert to frontend-friendly format (handle Decimal types)
                    formatted_messages = []
                    for msg in messages:
                        token_count = msg.get("token_count", 0)
                        # Convert Decimal to int if needed
                        if hasattr(token_count, '__int__'):
                            token_count = int(token_count)

                        # Handle generation_time (Decimal to float)
                        generation_time = msg.get("generation_time")
                        if generation_time is not None and hasattr(generation_time, '__float__'):
                            generation_time = float(generation_time)

                        formatted_messages.append({
                            "id": str(msg.get("message_timestamp", msg.get("timestamp", ""))),
                            "role": msg.get("role", "user"),
                            "content": msg.get("content", ""),
                            "timestamp": str(msg.get("message_timestamp", "")),
                            "tokensUsed": token_count,
                            "model": msg.get("model_used"),  # Include model used for this message
                            "generationTime": generation_time,  # Include for tokens/sec calculation
                        })
                    
                    logger.info(f"Fetched {len(formatted_messages)} messages for conversation {conversation_id}")
                    await websocket.send_json({
                        "type": "history",
                        "conversation_id": conversation_id,
                        "messages": formatted_messages
                    })
                except Exception as e:
                    logger.error(f"Failed to fetch history for {conversation_id}: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Failed to fetch history: {str(e)}"
                    })

            elif message_type == "close":
                # Close/delete conversation - remove all messages from DynamoDB
                try:
                    messages = await storage.get_conversation_messages(conversation_id)
                    
                    if not messages:
                        logger.info(f"Conversation {conversation_id} has no messages to delete")
                        await websocket.send_json({
                            "type": "close_complete",
                            "conversation_id": conversation_id,
                            "deleted_count": 0
                        })
                    else:
                        # Delete all messages
                        timestamps = [msg['message_timestamp'] for msg in messages]
                        await storage.delete_messages(conversation_id, timestamps)
                        
                        logger.info(f"Closed conversation {conversation_id}: deleted {len(timestamps)} messages")
                        await websocket.send_json({
                            "type": "close_complete",
                            "conversation_id": conversation_id,
                            "deleted_count": len(timestamps)
                        })
                except Exception as e:
                    logger.error(f"Failed to close conversation {conversation_id}: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Failed to close conversation: {str(e)}"
                    })

            else:
                await websocket.send_json({
                    "type": "error",
                    "error": f"Unknown message type: {message_type}"
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: conversation_id={conversation_id}, client_id={client_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "error": str(e)
            })
        except:
            pass
    finally:
        # Unregister WebSocket connection from ws_manager
        await ws_manager.unregister(client_id)
        logger.info(f"WebSocket unregistered: client_id={client_id}")
