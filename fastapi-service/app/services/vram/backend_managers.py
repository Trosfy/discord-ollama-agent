"""Backend managers for model unloading (Strategy Pattern)."""
import subprocess
import httpx
from typing import Set
from app.services.vram.interfaces import IBackendManager, BackendType
from app.utils.model_utils import force_unload_model
from app.config import settings
import logging_client

logger = logging_client.setup_logger('vram_backends')


class OllamaBackendManager(IBackendManager):
    """Backend manager for Ollama models."""

    def supports(self, backend_type: BackendType) -> bool:
        """Check if this manager handles Ollama backend."""
        return backend_type == BackendType.OLLAMA

    async def unload(self, model_id: str, backend_type: BackendType) -> None:
        """Unload model from Ollama."""
        if not self.supports(backend_type):
            raise ValueError(f"OllamaBackendManager doesn't support {backend_type}")

        logger.info(f"🔽 Unloading Ollama model: {model_id}")

        # Use existing force_unload_model utility
        await force_unload_model(model_id)

        # Cleanup shared memory after unload
        await self.cleanup(backend_type)

        logger.info(f"✅ Ollama model unloaded: {model_id}")

    async def cleanup(self, backend_type: BackendType) -> None:
        """Clean up Ollama shared memory segments."""
        if not self.supports(backend_type):
            return

        try:
            # Get shared memory segments owned by 'nobody' (Ollama)
            result = subprocess.run(
                "ipcs -m | grep nobody | awk '{print $2}'",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                segment_ids = result.stdout.strip().split('\n')
                for seg_id in segment_ids:
                    subprocess.run(['ipcrm', '-m', seg_id], timeout=5)
                logger.info(f"🧹 Cleaned {len(segment_ids)} Ollama shared memory segments")
        except Exception as e:
            logger.warning(f"⚠️  Shared memory cleanup failed: {e}")

    def get_loaded_models(self) -> Set[str]:
        """
        Query Ollama for actually loaded models via HTTP API.

        Returns:
            Set of model IDs that are currently loaded in Ollama

        Note:
            This is the source of truth for what's actually running.
            Used for registry reconciliation to detect desyncs from external kills.
        """
        # Try HTTP API first (works in Docker)
        try:
            import httpx

            # Use /api/ps to get currently loaded models
            response = httpx.get(
                f"{settings.OLLAMA_HOST}/api/ps",
                timeout=5.0
            )

            if response.status_code == 200:
                data = response.json()
                loaded = {m['name'] for m in data.get('models', [])}
                logger.debug(f"🔍 Ollama has {len(loaded)} models loaded via HTTP: {loaded}")
                return loaded
            else:
                logger.warning(f"⚠️  Ollama HTTP API /api/ps returned status {response.status_code}")
                return set()

        except Exception as e:
            logger.debug(f"HTTP API /api/ps query failed: {e}, trying CLI fallback")

        # Fallback to CLI (only works if running on host)
        try:
            result = subprocess.run(
                ['ollama', 'ps'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                logger.debug(f"'ollama ps' failed: {result.stderr}")
                return set()

            # Parse output (format: NAME   ID   SIZE   PROCESSOR   UNTIL)
            loaded = set()
            lines = result.stdout.strip().split('\n')

            if len(lines) <= 1:
                return set()

            for line in lines[1:]:
                parts = line.split()
                if parts:
                    model_name = parts[0]
                    loaded.add(model_name)

            logger.debug(f"🔍 Ollama has {len(loaded)} models loaded: {loaded}")
            return loaded

        except FileNotFoundError:
            logger.debug("'ollama' CLI not available (running in Docker) - using registry only")
            return set()
        except subprocess.TimeoutExpired:
            logger.warning("⚠️  'ollama ps' timed out")
            return set()
        except Exception as e:
            logger.debug(f"Failed to query Ollama models: {e}")
            return set()


class TensorRTBackendManager(IBackendManager):
    """Backend manager for TensorRT-LLM models (stub for future implementation)."""

    def supports(self, backend_type: BackendType) -> bool:
        """Check if this manager handles TensorRT backend."""
        return backend_type == BackendType.TENSORRT

    async def unload(self, model_id: str, backend_type: BackendType) -> None:
        """Unload model from TensorRT-LLM."""
        if not self.supports(backend_type):
            raise ValueError(f"TensorRTBackendManager doesn't support {backend_type}")

        logger.warning(
            f"⚠️  TensorRT-LLM unload not yet implemented for {model_id}. "
            f"This will be added when TensorRT backend is integrated."
        )

        # TODO: Implement TensorRT-LLM unload API call
        # Example: POST {tensorrt_endpoint}/v1/unload with model_id

    async def cleanup(self, backend_type: BackendType) -> None:
        """Cleanup TensorRT resources."""
        # TODO: Implement cleanup if needed
        pass


class vLLMBackendManager(IBackendManager):
    """Backend manager for vLLM models (stub for future implementation)."""

    def supports(self, backend_type: BackendType) -> bool:
        """Check if this manager handles vLLM backend."""
        return backend_type == BackendType.VLLM

    async def unload(self, model_id: str, backend_type: BackendType) -> None:
        """Unload model from vLLM."""
        if not self.supports(backend_type):
            raise ValueError(f"vLLMBackendManager doesn't support {backend_type}")

        logger.warning(
            f"⚠️  vLLM unload not yet implemented for {model_id}. "
            f"This will be added when vLLM backend is integrated."
        )

        # TODO: Implement vLLM unload API call
        # Example: POST {vllm_endpoint}/v1/unload with model_id

    async def cleanup(self, backend_type: BackendType) -> None:
        """Cleanup vLLM resources."""
        # TODO: Implement cleanup if needed
        pass


class SGLangBackendManager(IBackendManager):
    """Backend manager for SGLang models."""

    def supports(self, backend_type: BackendType) -> bool:
        """Check if this manager handles SGLang backend."""
        return backend_type == BackendType.SGLANG

    async def unload(self, model_id: str, backend_type: BackendType) -> None:
        """
        SGLang doesn't support dynamic model unloading.

        This is a no-op. To switch models, restart SGLang server.
        """
        if not self.supports(backend_type):
            raise ValueError(f"SGLangBackendManager doesn't support {backend_type}")

        logger.warning(
            f"⚠️  SGLang doesn't support dynamic unloading of {model_id}. "
            f"Model stays loaded until SGLang server restarts. "
            f"VRAM orchestrator will track this in registry."
        )

    async def cleanup(self, backend_type: BackendType) -> None:
        """SGLang cleanup (no-op - server manages its own resources)."""
        pass

    def get_loaded_models(self) -> Set[str]:
        """
        Query SGLang server for loaded models.

        Returns:
            Set of model IDs currently loaded in SGLang

        Note:
            Used for registry reconciliation. SGLang loads models at startup,
            so this should return a consistent set until server restart.
        """
        try:
            # Query SGLang /v1/models endpoint
            response = httpx.get(
                f"{settings.SGLANG_ENDPOINT}/v1/models",
                timeout=5.0
            )

            if response.status_code == 200:
                data = response.json()
                loaded = {m["id"] for m in data.get("data", [])}
                logger.debug(f"🔍 SGLang has {len(loaded)} models loaded: {loaded}")
                return loaded
            else:
                logger.warning(f"⚠️  SGLang /v1/models returned status {response.status_code}")
                return set()

        except Exception as e:
            logger.debug(f"SGLang /v1/models query failed: {e}")
            return set()


class CompositeBackendManager(IBackendManager):
    """
    Composite manager that delegates to appropriate backend manager.

    This follows the Composite pattern - routes requests to the right backend.
    """

    def __init__(self):
        self._managers = [
            OllamaBackendManager(),
            SGLangBackendManager(),
            TensorRTBackendManager(),
            vLLMBackendManager()
        ]

    def supports(self, backend_type: BackendType) -> bool:
        """Check if any manager supports this backend type."""
        return any(mgr.supports(backend_type) for mgr in self._managers)

    async def unload(self, model_id: str, backend_type: BackendType) -> None:
        """Delegate unload to appropriate manager."""
        for manager in self._managers:
            if manager.supports(backend_type):
                await manager.unload(model_id, backend_type)
                return

        raise ValueError(f"No backend manager found for {backend_type}")

    async def cleanup(self, backend_type: BackendType) -> None:
        """Delegate cleanup to appropriate manager."""
        for manager in self._managers:
            if manager.supports(backend_type):
                await manager.cleanup(backend_type)
                return
