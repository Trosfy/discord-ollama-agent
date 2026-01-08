"""HTTP client for communicating with fastapi-service internal VRAM endpoints."""

import httpx
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class VRAMClient:
    """
    HTTP client for fastapi-service internal VRAM API.

    Communicates with /internal/vram/* endpoints using INTERNAL_API_KEY.
    """

    def __init__(self, base_url: str, api_key: str):
        """
        Initialize VRAM client.

        Args:
            base_url: Base URL of fastapi-service (e.g., http://fastapi-service:8000)
            api_key: INTERNAL_API_KEY for service-to-service authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with internal API key."""
        return {
            "X-Internal-API-Key": self.api_key,
            "Content-Type": "application/json"
        }

    async def get_status(self) -> Dict:
        """
        Get VRAM status including usage, PSI metrics, and loaded models.

        Returns:
            dict: {
                "memory": {
                    "total_gb": float,
                    "used_gb": float,
                    "available_gb": float,
                    "usage_pct": float,
                    "psi_some_avg10": float,
                    "psi_full_avg10": float
                },
                "loaded_models": [...],
                "healthy": bool
            }
        """
        url = f"{self.base_url}/internal/vram/status"

        try:
            response = await self.client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get VRAM status: HTTP {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Failed to get VRAM status: {e}")
            raise

    async def list_models(self) -> List[Dict]:
        """
        List currently loaded models in VRAM.

        Returns:
            list: [
                {
                    "model_id": str,
                    "backend": str,
                    "size_gb": float,
                    "priority": str,
                    "last_access": str,
                    "is_external": bool
                },
                ...
            ]
        """
        url = f"{self.base_url}/internal/vram/models"

        try:
            response = await self.client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to list models: HTTP {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            raise

    async def list_available_models(self) -> List[Dict]:
        """
        List all available models from profile configuration.

        Returns:
            list: [
                {
                    "name": str,
                    "vram_size_gb": float,
                    "priority": str,
                    "backend": {"type": str, "endpoint": str},
                    "capabilities": list
                },
                ...
            ]
        """
        url = f"{self.base_url}/internal/vram/available-models"

        try:
            response = await self.client.get(url, headers=self._get_headers())
            response.raise_for_status()
            result = response.json()
            return result.get("models", [])
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to list available models: HTTP {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Failed to list available models: {e}")
            raise

    async def load_model(self, model_id: str, priority: Optional[str] = None) -> Dict:
        """
        Load a specific model into VRAM.

        Args:
            model_id: Model identifier (e.g., "qwen2.5:72b")
            priority: Optional priority override (HIGH, NORMAL, LOW)

        Returns:
            dict: {
                "status": "loaded" | "already_loaded" | "evicted_and_loaded",
                "model_id": str,
                "evicted_models": [...] (if eviction occurred)
            }
        """
        url = f"{self.base_url}/internal/vram/load"
        payload = {"model_id": model_id}

        if priority:
            payload["priority"] = priority

        try:
            response = await self.client.post(
                url,
                headers=self._get_headers(),
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to load model {model_id}: HTTP {e.response.status_code}")
            error_detail = e.response.json() if e.response.content else {}
            raise ValueError(f"Failed to load model: {error_detail.get('detail', str(e))}")
        except Exception as e:
            logger.error(f"Failed to load model {model_id}: {e}")
            raise

    async def unload_model(self, model_id: str) -> Dict:
        """
        Unload a specific model from VRAM.

        Args:
            model_id: Model identifier to unload

        Returns:
            dict: {
                "status": "unloaded",
                "model_id": str,
                "freed_gb": float
            }
        """
        url = f"{self.base_url}/internal/vram/unload"
        payload = {"model_id": model_id}

        try:
            response = await self.client.post(
                url,
                headers=self._get_headers(),
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to unload model {model_id}: HTTP {e.response.status_code}")
            error_detail = e.response.json() if e.response.content else {}
            raise ValueError(f"Failed to unload model: {error_detail.get('detail', str(e))}")
        except Exception as e:
            logger.error(f"Failed to unload model {model_id}: {e}")
            raise

    async def emergency_evict(self, priority: str) -> Dict:
        """
        Trigger emergency eviction of LRU model at specified priority level.

        Args:
            priority: Priority threshold (HIGH, NORMAL, LOW)

        Returns:
            dict: {
                "evicted": bool,
                "model_id": str (if evicted),
                "size_gb": float (if evicted),
                "reason": str (if not evicted)
            }
        """
        url = f"{self.base_url}/internal/vram/evict"
        payload = {"priority": priority}

        try:
            response = await self.client.post(
                url,
                headers=self._get_headers(),
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to trigger eviction: HTTP {e.response.status_code}")
            error_detail = e.response.json() if e.response.content else {}
            raise ValueError(f"Failed to evict: {error_detail.get('detail', str(e))}")
        except Exception as e:
            logger.error(f"Failed to trigger eviction: {e}")
            raise

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
