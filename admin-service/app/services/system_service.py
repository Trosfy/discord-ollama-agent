"""System control service for maintenance mode, queue management, and health checks."""
import sys
sys.path.insert(0, '/shared')

import httpx
from typing import Dict
from datetime import datetime, timezone
import logging

from app.config import settings
from app.middleware.audit_log import log_admin_action

logger = logging.getLogger(__name__)


class SystemService:
    """
    Business logic for system control operations.

    Handles:
    - Queue statistics and management
    - Maintenance mode (soft/hard)
    - System health checks across all services
    - Audit logging for all system operations
    """

    def __init__(self):
        """Initialize system service with HTTP client."""
        self.troise_ai_url = settings.TROISE_AI_URL
        self.api_key = settings.INTERNAL_API_KEY

    async def get_queue_stats(self) -> Dict:
        """
        Get current queue statistics from fastapi-service.

        Returns:
            dict: Queue statistics with size, max_size, is_full

        Raises:
            Exception: If unable to retrieve queue stats
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.fastapi_url}/internal/queue/stats",
                    headers={"X-Internal-API-Key": self.api_key},
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to get queue stats: {e}")
            raise Exception(f"Failed to retrieve queue statistics: {str(e)}")

    async def purge_queue(self, admin_user: str) -> Dict:
        """
        Emergency purge of the request queue.

        This is a destructive operation that clears all pending requests.

        Args:
            admin_user: ID of admin performing the purge

        Returns:
            dict: Result with purged_count

        Raises:
            Exception: If unable to purge queue
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.fastapi_url}/internal/queue/purge",
                    headers={"X-Internal-API-Key": self.api_key},
                    timeout=10.0
                )
                response.raise_for_status()
                result = response.json()

            # Audit log
            await log_admin_action(
                admin_user=admin_user,
                action="queue_purge",
                parameters={},
                result=f"success: purged {result.get('purged_count', 0)} requests"
            )

            logger.warning(f"Queue purged by {admin_user}: {result.get('purged_count', 0)} requests removed")

            return {
                "status": "success",
                "purged_count": result.get("purged_count", 0),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to purge queue: {e}")

            await log_admin_action(
                admin_user=admin_user,
                action="queue_purge",
                parameters={},
                result=f"error: {str(e)}"
            )

            raise Exception(f"Failed to purge queue: {str(e)}")

    async def set_maintenance_mode(
        self,
        enabled: bool,
        mode: str,
        admin_user: str
    ) -> Dict:
        """
        Enable or disable maintenance mode.

        Args:
            enabled: True to enable, False to disable
            mode: "soft" (queue still works) or "hard" (reject all)
            admin_user: ID of admin making the change

        Returns:
            dict: Result with current maintenance status

        Raises:
            ValueError: If invalid mode
            Exception: If unable to set maintenance mode
        """
        if mode not in ["soft", "hard"]:
            raise ValueError(f"Invalid maintenance mode: {mode}. Must be 'soft' or 'hard'")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.fastapi_url}/internal/maintenance",
                    headers={"X-Internal-API-Key": self.api_key},
                    json={"enabled": enabled, "mode": mode},
                    timeout=10.0
                )
                response.raise_for_status()
                result = response.json()

            # Audit log
            action = f"maintenance_{'enabled' if enabled else 'disabled'}"
            await log_admin_action(
                admin_user=admin_user,
                action=action,
                parameters={"mode": mode, "enabled": enabled},
                result="success"
            )

            logger.info(
                f"Maintenance mode {'enabled' if enabled else 'disabled'} "
                f"({mode}) by {admin_user}"
            )

            return {
                "status": "success",
                "maintenance_enabled": enabled,
                "mode": mode,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to set maintenance mode: {e}")

            await log_admin_action(
                admin_user=admin_user,
                action=f"maintenance_{'enabled' if enabled else 'disabled'}",
                parameters={"mode": mode, "enabled": enabled},
                result=f"error: {str(e)}"
            )

            raise Exception(f"Failed to set maintenance mode: {str(e)}")

    async def get_all_health_checks(self) -> Dict:
        """
        Get health status for all services.

        Checks:
        - fastapi-service
        - DynamoDB
        - Ollama
        - VRAM orchestrator

        Returns:
            dict: Health status for each service with overall health
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.fastapi_url}/internal/health",
                    headers={"X-Internal-API-Key": self.api_key},
                    timeout=10.0
                )
                response.raise_for_status()
                health_data = response.json()

            # Calculate overall health
            all_healthy = all(
                service.get("healthy", False)
                for service in health_data.get("services", {}).values()
            )

            return {
                "overall_healthy": all_healthy,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "services": health_data.get("services", {}),
                "details": health_data.get("details", {})
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to get health checks: {e}")
            return {
                "overall_healthy": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "services": {}
            }
