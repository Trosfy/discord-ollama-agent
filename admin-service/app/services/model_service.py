"""Model management service for admin operations."""

from typing import Dict, List, Optional
import logging
from datetime import datetime

from app.interfaces.protocols import IVRAMClient, INotificationService
from app.middleware.audit_log import log_admin_action

logger = logging.getLogger(__name__)


class ModelService:
    """
    Business logic for model management operations.

    Handles:
    - Listing available and loaded models
    - Loading and unloading models
    - Emergency evictions
    - Audit logging
    - Discord webhook notifications

    Now follows Dependency Inversion Principle:
    - Depends on IVRAMClient interface (not concrete VRAMClient)
    - Depends on INotificationService interface (not concrete WebhookService)
    - Can be tested with mock implementations
    """

    def __init__(self, vram_client: IVRAMClient, webhook: Optional[INotificationService] = None):
        """
        Initialize model service with dependencies.

        Args:
            vram_client: VRAM client interface for model operations
            webhook: Optional notification service for event alerts
        """
        self.vram_client = vram_client
        self.webhook = webhook

    async def list_available_models(self) -> List[Dict]:
        """
        List all available models from profile configuration.

        Returns:
            list: Available models with metadata
        """
        try:
            models = await self.vram_client.list_available_models()
            logger.debug(f"Retrieved {len(models)} available models")
            return models

        except Exception as e:
            logger.error(f"Failed to list available models: {e}")
            raise

    async def list_loaded_models(self) -> List[Dict]:
        """
        List currently loaded models in VRAM.

        Returns:
            list: Loaded models with VRAM usage details
        """
        try:
            result = await self.vram_client.list_models()
            models = result.get("models", [])
            logger.debug(f"Retrieved {len(models)} loaded models")
            return models

        except Exception as e:
            logger.error(f"Failed to list loaded models: {e}")
            raise

    async def load_model(
        self,
        model_id: str,
        admin_user: str,
        priority: Optional[str] = None
    ) -> Dict:
        """
        Load a specific model into VRAM.

        Args:
            model_id: Model identifier to load
            admin_user: Admin user performing the action
            priority: Optional priority override

        Returns:
            dict: Load result with status and details
        """
        logger.info(f"Admin {admin_user} loading model: {model_id}")

        try:
            # Call VRAM client to load model
            result = await self.vram_client.load_model(model_id, priority)

            # Audit log
            await log_admin_action(
                admin_user=admin_user,
                action="model_load",
                parameters={"model_id": model_id, "priority": priority},
                result="success"
            )

            logger.info(f"Model {model_id} loaded successfully by {admin_user}")

            # Send webhook notification
            if self.webhook:
                await self.webhook.send_event("model_loaded", {
                    "model_id": model_id,
                    "vram_size_gb": result.get("vram_size_gb", 0),
                    "priority": priority,
                    "admin_user": admin_user
                })

            return {
                "status": "success",
                "model_id": model_id,
                "message": f"Model {model_id} loaded successfully",
                "details": result
            }

        except ValueError as e:
            # Client-side error (invalid model, insufficient VRAM, etc.)
            logger.warning(f"Failed to load model {model_id}: {e}")

            await log_admin_action(
                admin_user=admin_user,
                action="model_load",
                parameters={"model_id": model_id, "priority": priority},
                result=f"failure: {str(e)}"
            )

            raise

        except Exception as e:
            # Server-side error
            logger.error(f"Failed to load model {model_id}: {e}")

            await log_admin_action(
                admin_user=admin_user,
                action="model_load",
                parameters={"model_id": model_id, "priority": priority},
                result=f"error: {str(e)}"
            )

            raise

    async def unload_model(self, model_id: str, admin_user: str) -> Dict:
        """
        Unload a specific model from VRAM.

        Args:
            model_id: Model identifier to unload
            admin_user: Admin user performing the action

        Returns:
            dict: Unload result with freed VRAM amount
        """
        logger.info(f"Admin {admin_user} unloading model: {model_id}")

        try:
            # Call VRAM client to unload model
            result = await self.vram_client.unload_model(model_id)

            # Audit log
            await log_admin_action(
                admin_user=admin_user,
                action="model_unload",
                parameters={"model_id": model_id},
                result="success"
            )

            logger.info(f"Model {model_id} unloaded successfully by {admin_user}")

            # Send webhook notification
            if self.webhook:
                await self.webhook.send_event("model_unloaded", {
                    "model_id": model_id,
                    "freed_gb": result.get("freed_gb", 0),
                    "admin_user": admin_user
                })

            return {
                "status": "success",
                "model_id": model_id,
                "message": f"Model {model_id} unloaded successfully",
                "details": result
            }

        except ValueError as e:
            logger.warning(f"Failed to unload model {model_id}: {e}")

            await log_admin_action(
                admin_user=admin_user,
                action="model_unload",
                parameters={"model_id": model_id},
                result=f"failure: {str(e)}"
            )

            raise

        except Exception as e:
            logger.error(f"Failed to unload model {model_id}: {e}")

            await log_admin_action(
                admin_user=admin_user,
                action="model_unload",
                parameters={"model_id": model_id},
                result=f"error: {str(e)}"
            )

            raise

    async def emergency_evict(self, priority: str, admin_user: str) -> Dict:
        """
        Trigger emergency eviction of LRU model at specified priority.

        Args:
            priority: Priority threshold (HIGH, NORMAL, LOW)
            admin_user: Admin user performing the action

        Returns:
            dict: Eviction result
        """
        logger.warning(
            f"Admin {admin_user} triggering emergency eviction "
            f"(priority={priority})"
        )

        try:
            # Call VRAM client to trigger eviction
            result = await self.vram_client.emergency_evict(priority)

            # Audit log
            await log_admin_action(
                admin_user=admin_user,
                action="emergency_evict",
                parameters={"priority": priority},
                result="success" if result.get("evicted") else "no_models_evicted"
            )

            if result.get("evicted"):
                logger.warning(
                    f"Emergency eviction successful: {result.get('model_id')} "
                    f"({result.get('size_gb')}GB freed) by {admin_user}"
                )

                # Send webhook notification
                if self.webhook:
                    await self.webhook.send_event("emergency_eviction", {
                        "evicted": True,
                        "model_id": result.get("model_id"),
                        "size_gb": result.get("size_gb"),
                        "priority": priority,
                        "reason": result.get("reason", "Manual eviction"),
                        "admin_user": admin_user
                    })

            else:
                logger.info(f"No models to evict at priority {priority}")

            return {
                "status": "success",
                "evicted": result.get("evicted", False),
                "model_id": result.get("model_id"),
                "size_gb": result.get("size_gb"),
                "reason": result.get("reason"),
                "message": (
                    f"Evicted {result.get('model_id')} ({result.get('size_gb')}GB)"
                    if result.get("evicted")
                    else result.get("reason", "No models to evict")
                )
            }

        except ValueError as e:
            logger.warning(f"Failed to trigger eviction: {e}")

            await log_admin_action(
                admin_user=admin_user,
                action="emergency_evict",
                parameters={"priority": priority},
                result=f"failure: {str(e)}"
            )

            raise

        except Exception as e:
            logger.error(f"Failed to trigger eviction: {e}")

            await log_admin_action(
                admin_user=admin_user,
                action="emergency_evict",
                parameters={"priority": priority},
                result=f"error: {str(e)}"
            )

            raise

    async def get_vram_status(self) -> Dict:
        """
        Get current VRAM status and metrics.

        Returns:
            dict: VRAM usage, PSI metrics, loaded models
        """
        try:
            status = await self.vram_client.get_status()
            logger.debug("Retrieved VRAM status")
            return status

        except Exception as e:
            logger.error(f"Failed to get VRAM status: {e}")
            raise
