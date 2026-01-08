"""VRAM capacity validation service."""

import logging
from typing import Dict, Tuple
import httpx

logger = logging.getLogger(__name__)


class VRAMValidator:
    """
    Service for validating VRAM capacity before loading models.

    Uses system memory tracking from SystemMetricsService.
    Checks if sufficient VRAM is available before loading Ollama models.
    """

    def __init__(self, ollama_endpoint: str = "http://host.docker.internal:11434"):
        """
        Initialize VRAM validator.

        Args:
            ollama_endpoint: Base URL for Ollama API (to fetch model sizes)
        """
        self.ollama_endpoint = ollama_endpoint
        self.http_client = httpx.AsyncClient(timeout=10.0)

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()

    async def get_current_vram_stats(self) -> Dict:
        """
        Get current VRAM statistics from system memory.

        Uses SystemMetricsService to fetch free -m stats.

        Returns:
            dict: {
                "total_gb": float,
                "used_gb": float,
                "available_gb": float,
                "usage_percentage": float
            }
        """
        from app.services.system_metrics_service import SystemMetricsService

        try:
            metrics_service = SystemMetricsService()
            vram_stats = await metrics_service.fetch_vram_stats()
            return vram_stats
        except Exception as e:
            logger.error(f"Failed to fetch VRAM stats: {e}")
            # Return conservative estimate (assume low available space)
            return {
                "total_gb": 0,
                "used_gb": 0,
                "available_gb": 0,
                "usage_percentage": 100
            }

    async def get_model_size(self, model_name: str) -> float:
        """
        Get Ollama model size in GB.

        Queries Ollama /api/tags to find model size.

        Args:
            model_name: Ollama model name (e.g., "magistral:24b")

        Returns:
            float: Model size in GB (0.0 if not found)
        """
        try:
            url = f"{self.ollama_endpoint}/api/tags"
            response = await self.http_client.get(url)
            response.raise_for_status()

            data = response.json()
            models = data.get("models", [])

            for model in models:
                if model.get("name") == model_name:
                    size_bytes = model.get("size", 0)
                    size_gb = size_bytes / (1024**3)
                    logger.info(f"Model {model_name} size: {size_gb:.2f} GB")
                    return size_gb

            logger.warning(f"Model {model_name} not found in Ollama")
            return 0.0

        except Exception as e:
            logger.error(f"Failed to get model size for {model_name}: {e}")
            return 0.0

    async def validate_capacity(
        self,
        model_name: str,
        safety_margin_gb: float = 2.0
    ) -> Tuple[bool, str]:
        """
        Validate if sufficient VRAM is available to load model.

        Args:
            model_name: Ollama model to load
            safety_margin_gb: Additional buffer to prevent OOM (default 2GB)

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
                - is_valid: True if sufficient VRAM available
                - error_message: Human-readable error if validation fails
        """
        try:
            # Get current VRAM stats
            vram_stats = await self.get_current_vram_stats()
            available_gb = vram_stats.get("available_gb", 0)

            # Get model size
            model_size_gb = await self.get_model_size(model_name)

            if model_size_gb == 0:
                # Model size unknown - allow loading (risky but backwards compatible)
                logger.warning(
                    f"Cannot determine size for {model_name}, allowing load (risky)"
                )
                return True, ""

            # Calculate required space with safety margin
            required_gb = model_size_gb + safety_margin_gb

            # Check capacity
            if available_gb < required_gb:
                error_msg = (
                    f"Insufficient VRAM: Need {required_gb:.1f}GB "
                    f"({model_size_gb:.1f}GB model + {safety_margin_gb:.1f}GB buffer), "
                    f"only {available_gb:.1f}GB available"
                )
                logger.warning(f"❌ Capacity check failed for {model_name}: {error_msg}")
                return False, error_msg

            logger.info(
                f"✅ Capacity check passed for {model_name}: "
                f"Need {required_gb:.1f}GB, have {available_gb:.1f}GB"
            )
            return True, ""

        except Exception as e:
            logger.error(f"VRAM validation failed: {e}")
            # On error, allow loading (fail open for backwards compatibility)
            return True, ""
