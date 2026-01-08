"""
Monitoring API - Server-Sent Events (SSE)

Provides real-time monitoring data for the Next.js frontend.
Uses SSE for one-way server → client communication.
"""

import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.utils.health_checks import check_vram_status, check_dynamodb, check_ollama
from app.dependencies import get_queue
from app.config import settings

router = APIRouter()


async def monitoring_event_generator() -> AsyncGenerator[dict, None]:
    """
    Generate monitoring events for SSE stream.

    Sends updates every 5 seconds with:
    - VRAM stats (usage, loaded models)
    - Service health (DynamoDB, Ollama)
    - Queue metrics
    """
    while True:
        try:
            # Gather all monitoring data
            vram_status = await check_vram_status()
            db_ok = await check_dynamodb()
            ollama_ok = await check_ollama()
            queue = get_queue()

            # Build monitoring payload
            data = {
                "timestamp": datetime.utcnow().isoformat(),
                "health": {
                    "status": "healthy" if vram_status.get("healthy", False) else "degraded",
                    "services": {
                        "dynamodb": db_ok,
                        "ollama": ollama_ok,
                    },
                },
                "vram": {
                    "total_gb": vram_status.get("total_gb", 0),
                    "used_gb": vram_status.get("used_gb", 0),
                    "available_gb": vram_status.get("available_gb", 0),
                    "usage_pct": vram_status.get("usage_pct", 0),
                    "loaded_models": vram_status.get("loaded_models", 0),
                    "models": vram_status.get("models", []),
                    "psi_some_avg10": vram_status.get("psi_some_avg10", 0),
                    "psi_full_avg10": vram_status.get("psi_full_avg10", 0),
                },
                "queue": {
                    "size": queue.size(),
                },
                "maintenance_mode": settings.MAINTENANCE_MODE,
            }

            # Yield SSE event
            yield {
                "event": "monitoring_update",
                "data": json.dumps(data),
            }

            # Wait 5 seconds before next update
            await asyncio.sleep(5)

        except asyncio.CancelledError:
            # Client disconnected
            break
        except Exception as e:
            # Send error event
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }
            await asyncio.sleep(5)


@router.get("/monitoring/stream")
async def monitoring_stream():
    """
    SSE endpoint for real-time monitoring data.

    Returns:
        EventSourceResponse: Server-Sent Events stream

    Usage (Frontend):
        const eventSource = new EventSource('/api/monitoring/stream');
        eventSource.addEventListener('monitoring_update', (event) => {
            const data = JSON.parse(event.data);
            console.log('VRAM:', data.vram);
        });
    """
    return EventSourceResponse(monitoring_event_generator())
