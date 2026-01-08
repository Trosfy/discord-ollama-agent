"""Ollama model management service for prewarming and unloading models."""

import httpx
import logging
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, List

logger = logging.getLogger(__name__)


class OllamaService:
    """
    Service for managing Ollama model lifecycle (prewarm/unload).

    Tracks prewarmed models in memory with timestamps to determine
    when models will be automatically unloaded (after 10 minutes).

    State management:
    - Models are prewarmed by sending empty prompt with keep_alive="10m"
    - Models are unloaded by sending empty prompt with keep_alive="0"
    - Tracks prewarm timestamps to estimate when models will expire
    """

    def __init__(self, ollama_endpoint: str = "http://host.docker.internal:11434"):
        """
        Initialize Ollama service.

        Args:
            ollama_endpoint: Base URL for Ollama API
        """
        self.ollama_endpoint = ollama_endpoint
        self.http_client = httpx.AsyncClient(timeout=30.0)

        # Track prewarmed models: {model_name: prewarm_timestamp}
        self._prewarmed_models: Dict[str, datetime] = {}

        # 10 minutes keep_alive duration
        self.keep_alive_duration = timedelta(minutes=10)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()

    async def prewarm_model(self, model_name: str) -> Dict:
        """
        Prewarm an Ollama model into memory for 10 minutes.

        For text generation models: Uses /api/generate with empty prompt
        For embedding models: Uses /api/embeddings with dummy text

        Args:
            model_name: Name of the Ollama model to prewarm

        Returns:
            dict: Result with status and message

        Raises:
            Exception: If Ollama API call fails
        """
        try:
            logger.info(f"Prewarming Ollama model: {model_name}")

            # Check if this is an embedding model
            is_embedding = "embedding" in model_name.lower()

            if is_embedding:
                # Use embeddings endpoint for embedding models
                url = f"{self.ollama_endpoint}/api/embeddings"
                payload = {
                    "model": model_name,
                    "prompt": "warmup",  # Dummy text for prewarm
                    "keep_alive": "10m",  # Keep in memory for 10 minutes
                }
            else:
                # Use generate endpoint for text generation models
                url = f"{self.ollama_endpoint}/api/generate"
                payload = {
                    "model": model_name,
                    "prompt": "",  # Empty prompt - just prewarm
                    "keep_alive": "10m",  # Keep in memory for 10 minutes
                    "stream": False
                }

            response = await self.http_client.post(url, json=payload)
            response.raise_for_status()

            # Track prewarm timestamp
            self._prewarmed_models[model_name] = datetime.utcnow()

            logger.info(f"✅ Successfully prewarmed {model_name} (embedding={is_embedding})")
            return {
                "status": "success",
                "message": f"Model {model_name} prewarmed for 10 minutes",
                "expires_at": (datetime.utcnow() + self.keep_alive_duration).isoformat()
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Failed to prewarm {model_name}: HTTP {e.response.status_code}")
            raise Exception(f"Ollama API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"❌ Failed to prewarm {model_name}: {e}")
            raise

    async def unload_model(self, model_name: str) -> Dict:
        """
        Unload an Ollama model from memory immediately.

        For text generation models: Uses /api/generate with keep_alive="0"
        For embedding models: Uses /api/embeddings with keep_alive="0"

        Args:
            model_name: Name of the Ollama model to unload

        Returns:
            dict: Result with status and message

        Raises:
            Exception: If Ollama API call fails
        """
        try:
            logger.info(f"Unloading Ollama model: {model_name}")

            # Check if this is an embedding model
            is_embedding = "embedding" in model_name.lower()

            if is_embedding:
                # Use embeddings endpoint for embedding models
                url = f"{self.ollama_endpoint}/api/embeddings"
                payload = {
                    "model": model_name,
                    "prompt": "unload",  # Dummy text
                    "keep_alive": "0",  # Unload immediately
                }
            else:
                # Use generate endpoint for text generation models
                url = f"{self.ollama_endpoint}/api/generate"
                payload = {
                    "model": model_name,
                    "prompt": "",  # Empty prompt
                    "keep_alive": "0",  # Unload immediately
                    "stream": False
                }

            response = await self.http_client.post(url, json=payload)
            response.raise_for_status()

            # Remove from tracking
            self._prewarmed_models.pop(model_name, None)

            logger.info(f"✅ Successfully unloaded {model_name} (embedding={is_embedding})")
            return {
                "status": "success",
                "message": f"Model {model_name} unloaded from memory"
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Failed to unload {model_name}: HTTP {e.response.status_code}")
            raise Exception(f"Ollama API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"❌ Failed to unload {model_name}: {e}")
            raise

    async def sync_loaded_models(self) -> None:
        """
        Sync internal state with actual Ollama loaded models.

        Queries Ollama's /api/ps endpoint to get actually loaded models
        and updates the _prewarmed_models dict accordingly.

        This ensures the admin dashboard shows accurate model state even
        if models were loaded by other services (fastapi-service, etc.).
        """
        try:
            url = f"{self.ollama_endpoint}/api/ps"
            response = await self.http_client.get(url)
            response.raise_for_status()

            data = response.json()
            loaded_models = data.get("models", [])

            # Update _prewarmed_models for any loaded models we weren't tracking
            now = datetime.utcnow()
            for model_info in loaded_models:
                model_name = model_info.get("name", "")
                if model_name and model_name not in self._prewarmed_models:
                    # Add as if it was just prewarmed (we don't know actual load time)
                    self._prewarmed_models[model_name] = now
                    logger.info(f"📊 Synced loaded model from Ollama: {model_name}")

        except Exception as e:
            logger.warning(f"Failed to sync with Ollama ps: {e}")

    async def list_loaded_models(self) -> List[Dict]:
        """
        List currently loaded models from Ollama /api/ps.

        Returns:
            list: [{"name": "model_name", "size": bytes, ...}, ...]
        """
        try:
            url = f"{self.ollama_endpoint}/api/ps"
            response = await self.http_client.get(url)
            response.raise_for_status()

            data = response.json()
            return data.get("models", [])

        except Exception as e:
            logger.warning(f"Failed to list loaded models from Ollama: {e}")
            return []

    def is_prewarmed(self, model_name: str) -> bool:
        """
        Check if a model is currently prewarmed (still within 10-minute window).

        Args:
            model_name: Name of the model to check

        Returns:
            bool: True if model is prewarmed and hasn't expired yet
        """
        if model_name not in self._prewarmed_models:
            return False

        prewarm_time = self._prewarmed_models[model_name]
        expiry_time = prewarm_time + self.keep_alive_duration

        # Check if still within 10-minute window
        if datetime.utcnow() < expiry_time:
            return True
        else:
            # Expired - remove from tracking
            self._prewarmed_models.pop(model_name, None)
            return False

    def get_prewarmed_models(self) -> Set[str]:
        """
        Get set of all currently prewarmed model names.

        Automatically cleans up expired entries.

        Returns:
            set: Set of prewarmed model names
        """
        now = datetime.utcnow()

        # Clean up expired models
        expired = [
            name for name, prewarm_time in self._prewarmed_models.items()
            if now >= prewarm_time + self.keep_alive_duration
        ]

        for name in expired:
            logger.debug(f"Prewarm expired for {name}")
            self._prewarmed_models.pop(name, None)

        return set(self._prewarmed_models.keys())

    def get_time_remaining(self, model_name: str) -> Optional[int]:
        """
        Get remaining seconds until model is auto-unloaded.

        Args:
            model_name: Name of the model

        Returns:
            int: Seconds remaining, or None if not prewarmed
        """
        if model_name not in self._prewarmed_models:
            return None

        prewarm_time = self._prewarmed_models[model_name]
        expiry_time = prewarm_time + self.keep_alive_duration
        remaining = (expiry_time - datetime.utcnow()).total_seconds()

        return max(0, int(remaining))
