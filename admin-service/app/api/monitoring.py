"""
Monitoring API - Server-Sent Events (SSE)

Provides real-time monitoring data aggregated from multiple sources for the admin dashboard.
Uses SSE for one-way server → client communication.

Data sources:
- SystemMetricsService: VRAM, PSI, queue metrics
- HealthCheckerService: Service health status
"""

import asyncio
from datetime import datetime
from typing import AsyncGenerator, Dict
import logging

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.middleware.auth import require_admin_sse
from app.services.system_metrics_service import SystemMetricsService
from app.services.health_checker_service import HealthCheckerService
from app.utils.json_encoder import json_dumps

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["monitoring"])


async def monitoring_event_generator(
    system_metrics: SystemMetricsService,
    health_checker: HealthCheckerService
) -> AsyncGenerator[dict, None]:
    """
    Generate monitoring events for SSE stream.

    Pulls data from two sources:
    - SystemMetricsService: VRAM, PSI, queue metrics
    - HealthCheckerService: Service health status

    Sends updates every 5 seconds with complete monitoring snapshot.
    """
    while True:
        try:
            # Pull from both services
            system_snapshot = await system_metrics.get_system_snapshot()
            health_snapshot = health_checker.get_health_snapshot()

            # Combine data from both sources
            data = {
                "timestamp": system_snapshot.get("timestamp"),
                "vram": system_snapshot.get("vram", {}),
                "queue_size": system_snapshot.get("queue_size", 0),
                "psi": system_snapshot.get("psi", {}),
                "gpu": system_snapshot.get("gpu", {}),
                "cpu_utilization": system_snapshot.get("cpu_utilization", 0),
                "maintenance_mode": system_snapshot.get("maintenance_mode", False),
                "services": health_snapshot  # Service health from HealthCheckerService
            }

            # Yield SSE event (no event type - use default 'message')
            yield {
                "data": json_dumps(data),
            }

            # Wait 5 seconds before next update
            await asyncio.sleep(5)

        except asyncio.CancelledError:
            # Client disconnected
            logger.info("Monitoring SSE client disconnected")
            break
        except Exception as e:
            logger.error(f"Error in monitoring stream: {e}", exc_info=True)
            # Send error event (no event type - use default 'message')
            yield {
                "data": json_dumps({
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }),
            }
            await asyncio.sleep(5)


@router.get("/monitoring/stream")
async def monitoring_stream(
    request: Request,
    admin_auth: Dict = Depends(require_admin_sse)
):
    """
    SSE endpoint for real-time admin monitoring data.

    Requires admin authentication via ?token query parameter or Authorization header.

    Pulls data from:
    - app.state.system_metrics: VRAM, PSI, queue
    - app.state.health_checker: Service health

    Returns:
        EventSourceResponse: Server-Sent Events stream

    Usage (Frontend):
        const eventSource = new EventSource('/admin/monitoring/stream?token=YOUR_JWT_TOKEN');
        eventSource.addEventListener('monitoring_update', (event) => {
            const data = JSON.parse(event.data);
            console.log('VRAM:', data.vram);
            console.log('Services:', data.services);
        });
    """
    # Get services from app state (started in main.py)
    system_metrics = request.app.state.system_metrics
    health_checker = request.app.state.health_checker

    return EventSourceResponse(
        monitoring_event_generator(system_metrics, health_checker)
    )
