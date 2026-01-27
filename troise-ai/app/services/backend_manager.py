"""
Backend Manager for TROISE AI.

Provides unified management for multiple AI inference backends:
- Ollama: Local LLM inference with dynamic model loading
- SGLang: High-performance serving with continuous batching
- vLLM: Production-ready LLM serving

Features:
- Async HTTP communication with backends
- SSH-based remote backend management on DGX
- Health checking and model lifecycle management
- Graceful error handling and logging
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, TYPE_CHECKING

import aiohttp
import asyncssh

from app.core.config import Config, BackendConfig

if TYPE_CHECKING:
    from app.core.interfaces.services import IComfyUICompletionWaiter

logger = logging.getLogger(__name__)


class IBackendClient(ABC):
    """
    Abstract interface for backend clients.

    All backend clients must implement these methods to provide
    a unified interface for model management across different
    inference backends.
    """

    @abstractmethod
    async def load_model(self, model_id: str, keep_alive: str = "10m") -> bool:
        """
        Load a model into the backend.

        Args:
            model_id: The model identifier to load.
            keep_alive: How long to keep the model loaded (e.g., "10m", "1h").

        Returns:
            True if the model was loaded successfully, False otherwise.
        """
        pass

    @abstractmethod
    async def unload_model(self, model_id: str) -> bool:
        """
        Unload a model from the backend.

        Args:
            model_id: The model identifier to unload.

        Returns:
            True if the model was unloaded successfully, False otherwise.
        """
        pass

    @abstractmethod
    async def list_loaded(self) -> List[Dict[str, Any]]:
        """
        List all currently loaded models.

        Returns:
            List of dictionaries containing model information.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the backend is healthy and responsive.

        Returns:
            True if the backend is healthy, False otherwise.
        """
        pass


class OllamaClient(IBackendClient):
    """
    Client for Ollama inference backend.

    Ollama provides local LLM inference with dynamic model loading/unloading.
    Models are loaded on-demand and can be kept in memory for a specified duration.
    """

    # Timeout for model loading (large models can take minutes to load)
    LOAD_TIMEOUT_SECONDS = 300  # 5 minutes
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 5  # Base delay, doubles each retry

    def __init__(self, host: str):
        """
        Initialize the Ollama client.

        Args:
            host: The Ollama server URL (e.g., "http://localhost:11434").
        """
        self.host = host.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def load_model(self, model_id: str, keep_alive: str = "10m") -> bool:
        """
        Load a model into Ollama by sending a generate request with keep_alive.

        This triggers Ollama to load the model into memory and keep it loaded
        for the specified duration. Includes retry logic for transient failures.

        Args:
            model_id: The model identifier to load.
            keep_alive: Duration to keep the model loaded (default: "10m").

        Returns:
            True if the model was loaded successfully, False otherwise.
        """
        import asyncio

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                session = await self._get_session()
                url = f"{self.host}/api/generate"
                payload = {
                    "model": model_id,
                    "prompt": "",
                    "keep_alive": keep_alive
                }

                # Use longer timeout for model loading (can take minutes for large models)
                timeout = aiohttp.ClientTimeout(total=self.LOAD_TIMEOUT_SECONDS)

                if attempt > 0:
                    logger.info(f"Retrying load for '{model_id}' (attempt {attempt + 1}/{self.MAX_RETRIES})")

                async with session.post(url, json=payload, timeout=timeout) as response:
                    if response.status == 200:
                        logger.info(f"Model '{model_id}' loaded successfully with keep_alive={keep_alive}")
                        return True
                    else:
                        error_text = await response.text()
                        last_error = f"HTTP {response.status} - {error_text}"
                        logger.warning(f"Load attempt {attempt + 1} failed for '{model_id}': {last_error}")

            except asyncio.TimeoutError:
                last_error = f"Timeout after {self.LOAD_TIMEOUT_SECONDS}s"
                logger.warning(f"Load attempt {attempt + 1} for '{model_id}' timed out")

            except aiohttp.ClientError as e:
                last_error = f"Connection error: {e}"
                logger.warning(f"Load attempt {attempt + 1} for '{model_id}' failed: {last_error}")

            except Exception as e:
                last_error = f"Unexpected error: {e}"
                logger.warning(f"Load attempt {attempt + 1} for '{model_id}' failed: {last_error}")

            # Wait before retry with exponential backoff
            if attempt < self.MAX_RETRIES - 1:
                delay = self.RETRY_DELAY_SECONDS * (2 ** attempt)
                logger.debug(f"Waiting {delay}s before retry...")
                await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(f"Failed to load model '{model_id}' after {self.MAX_RETRIES} attempts: {last_error}")
        return False

    async def unload_model(self, model_id: str) -> bool:
        """
        Unload a model from Ollama by setting keep_alive to "0".

        This tells Ollama to immediately unload the model from memory.

        Args:
            model_id: The model identifier to unload.

        Returns:
            True if the model was unloaded successfully, False otherwise.
        """
        import asyncio

        try:
            session = await self._get_session()
            url = f"{self.host}/api/generate"
            payload = {
                "model": model_id,
                "prompt": "",
                "keep_alive": "0"
            }

            # Timeout for unload (should be quick, but allow time for large models)
            timeout = aiohttp.ClientTimeout(total=60)

            async with session.post(url, json=payload, timeout=timeout) as response:
                if response.status == 200:
                    logger.info(f"Model '{model_id}' unloaded successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to unload model '{model_id}': {response.status} - {error_text}")
                    return False

        except asyncio.TimeoutError:
            logger.error(f"Timeout unloading model '{model_id}'")
            return False
        except aiohttp.ClientError as e:
            logger.error(f"Connection error unloading model '{model_id}': {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error unloading model '{model_id}': {e}")
            return False

    async def list_loaded(self) -> List[Dict[str, Any]]:
        """
        List all currently loaded models in Ollama.

        Uses the /api/ps endpoint to get information about running models.

        Returns:
            List of dictionaries containing model information including
            name, size, and loaded duration.
        """
        try:
            session = await self._get_session()
            url = f"{self.host}/api/ps"

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    models = data.get("models", [])
                    logger.debug(f"Found {len(models)} loaded models in Ollama")
                    return models
                else:
                    logger.error(f"Failed to list loaded models: {response.status}")
                    return []

        except aiohttp.ClientError as e:
            logger.error(f"Connection error listing loaded models: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing loaded models: {e}")
            return []

    async def health_check(self) -> bool:
        """
        Check if Ollama is healthy by querying the /api/tags endpoint.

        Uses a 5-second timeout to prevent hanging on unresponsive servers.

        Returns:
            True if Ollama is responsive, False otherwise.
        """
        try:
            session = await self._get_session()
            url = f"{self.host}/api/tags"
            timeout = aiohttp.ClientTimeout(total=5)

            async with session.get(url, timeout=timeout) as response:
                is_healthy = response.status == 200
                if is_healthy:
                    logger.debug(f"Ollama health check passed at {self.host}")
                else:
                    logger.warning(f"Ollama health check failed: {response.status}")
                return is_healthy

        except aiohttp.ClientError as e:
            logger.error(f"Ollama health check failed - connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"Ollama health check failed - unexpected error: {e}")
            return False


class SGLangClient(IBackendClient):
    """
    Client for SGLang inference backend.

    SGLang provides high-performance serving with continuous batching.
    Unlike Ollama, SGLang typically runs a single model per instance,
    so model loading/unloading is handled at the process level rather
    than through API calls.
    """

    def __init__(self, host: str):
        """
        Initialize the SGLang client.

        Args:
            host: The SGLang server URL (e.g., "http://localhost:30000").
        """
        self.host = host.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self._loaded_model: Optional[str] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def load_model(self, model_id: str, keep_alive: str = "10m") -> bool:
        """
        Track model as loaded for SGLang.

        SGLang runs a single model per instance, so "loading" a model
        means the instance should be started with that model. This method
        only tracks state; actual model loading requires starting the
        SGLang server with the appropriate model.

        Args:
            model_id: The model identifier to track as loaded.
            keep_alive: Ignored for SGLang (instance-level management).

        Returns:
            True if the model is now tracked as loaded.
        """
        # SGLang is single-model-per-instance, track state only
        self._loaded_model = model_id
        logger.info(f"SGLang model state updated: {model_id}")
        return True

    async def unload_model(self, model_id: str) -> bool:
        """
        Mark model as unloaded for SGLang.

        This only updates internal state. Actual model unloading requires
        stopping the SGLang server instance.

        Args:
            model_id: The model identifier to mark as unloaded.

        Returns:
            True if the model was marked as unloaded.
        """
        if self._loaded_model == model_id:
            self._loaded_model = None
            logger.info(f"SGLang model state cleared: {model_id}")
        return True

    async def list_loaded(self) -> List[Dict[str, Any]]:
        """
        List the currently tracked model for this SGLang instance.

        Returns:
            List containing the loaded model info, or empty list if none.
        """
        if self._loaded_model:
            return [{"name": self._loaded_model, "backend": "sglang"}]
        return []

    async def health_check(self) -> bool:
        """
        Check if SGLang is healthy by querying the /health endpoint.

        Returns:
            True if SGLang is responsive, False otherwise.
        """
        try:
            session = await self._get_session()
            url = f"{self.host}/health"
            timeout = aiohttp.ClientTimeout(total=5)

            async with session.get(url, timeout=timeout) as response:
                is_healthy = response.status == 200
                if is_healthy:
                    logger.debug(f"SGLang health check passed at {self.host}")
                else:
                    logger.warning(f"SGLang health check failed: {response.status}")
                return is_healthy

        except aiohttp.ClientError as e:
            logger.error(f"SGLang health check failed - connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"SGLang health check failed - unexpected error: {e}")
            return False


class VLLMClient(IBackendClient):
    """
    Client for vLLM inference backend.

    vLLM provides production-ready LLM serving with high throughput.
    Like SGLang, vLLM typically runs a single model per instance.
    """

    def __init__(self, host: str):
        """
        Initialize the vLLM client.

        Args:
            host: The vLLM server URL (e.g., "http://localhost:8000").
        """
        self.host = host.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self._loaded_model: Optional[str] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def load_model(self, model_id: str, keep_alive: str = "10m") -> bool:
        """
        Track model as loaded for vLLM.

        vLLM runs a single model per instance. This method only tracks state.

        Args:
            model_id: The model identifier to track as loaded.
            keep_alive: Ignored for vLLM (instance-level management).

        Returns:
            True if the model is now tracked as loaded.
        """
        self._loaded_model = model_id
        logger.info(f"vLLM model state updated: {model_id}")
        return True

    async def unload_model(self, model_id: str) -> bool:
        """
        Mark model as unloaded for vLLM.

        Args:
            model_id: The model identifier to mark as unloaded.

        Returns:
            True if the model was marked as unloaded.
        """
        if self._loaded_model == model_id:
            self._loaded_model = None
            logger.info(f"vLLM model state cleared: {model_id}")
        return True

    async def list_loaded(self) -> List[Dict[str, Any]]:
        """
        List the currently tracked model for this vLLM instance.

        Returns:
            List containing the loaded model info, or empty list if none.
        """
        if self._loaded_model:
            return [{"name": self._loaded_model, "backend": "vllm"}]
        return []

    async def health_check(self) -> bool:
        """
        Check if vLLM is healthy by querying the /health endpoint.

        Returns:
            True if vLLM is responsive, False otherwise.
        """
        try:
            session = await self._get_session()
            url = f"{self.host}/health"
            timeout = aiohttp.ClientTimeout(total=5)

            async with session.get(url, timeout=timeout) as response:
                is_healthy = response.status == 200
                if is_healthy:
                    logger.debug(f"vLLM health check passed at {self.host}")
                else:
                    logger.warning(f"vLLM health check failed: {response.status}")
                return is_healthy

        except aiohttp.ClientError as e:
            logger.error(f"vLLM health check failed - connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"vLLM health check failed - unexpected error: {e}")
            return False


class ComfyUIClient(IBackendClient):
    """
    HTTP backend client for ComfyUI image generation.

    Implements IBackendClient for VRAMOrchestrator integration.
    ComfyUI manages its own model lifecycle (lazy loading on first prompt).
    Supports NVFP4 quantized models like FLUX.2-dev-NVFP4.

    Uses WebSocket for efficient completion detection with HTTP polling fallback.
    """

    WORKFLOW_TIMEOUT_SECONDS = 900  # 15 min for image generation (FLUX.2 can be slow)
    HEALTH_TIMEOUT_SECONDS = 10
    HISTORY_POLL_RETRIES = 10       # Retries after WebSocket completion signal
    HISTORY_POLL_DELAY = 0.5        # Delay between history polls (seconds)

    def __init__(self, host: str):
        """
        Initialize ComfyUI client.

        Args:
            host: ComfyUI server URL (e.g., "http://localhost:8188").
        """
        self._host = host.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self._loaded_models: set = set()  # Track which models have been used

        # WebSocket completion detection (DIP: interface-based)
        self._completion_waiter: Optional["IComfyUICompletionWaiter"] = None
        self._ws_lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close HTTP session and WebSocket connection."""
        if self._session and not self._session.closed:
            await self._session.close()
        # Disconnect WebSocket if connected
        if self._completion_waiter and hasattr(self._completion_waiter, 'disconnect'):
            try:
                await self._completion_waiter.disconnect()
            except Exception as e:
                logger.debug(f"ComfyUI: Error disconnecting WebSocket: {e}")
            self._completion_waiter = None

    async def load_model(self, model_id: str, keep_alive: str = "10m") -> bool:
        """
        Mark model as loaded (ComfyUI loads lazily on first prompt).

        ComfyUI doesn't have explicit load API - models load when referenced
        in a workflow. We track state for VRAMOrchestrator compatibility.

        Args:
            model_id: The diffusion model identifier.
            keep_alive: Ignored for ComfyUI.

        Returns:
            True (ComfyUI loads models on demand).
        """
        self._loaded_models.add(model_id)
        logger.info(f"ComfyUI: Marked model '{model_id}' as available")
        return True

    async def unload_model(self, model_id: str) -> bool:
        """
        Request ComfyUI to free model from memory.

        Uses ComfyUI's /free endpoint to release VRAM.

        Args:
            model_id: The diffusion model identifier to unload.

        Returns:
            True if freed successfully, False otherwise.
        """
        try:
            session = await self._get_session()
            # ComfyUI /free endpoint releases models from VRAM
            # Both flags needed: unload_models removes from cache, free_memory releases RAM
            async with session.post(
                f"{self._host}/free",
                json={"unload_models": True, "free_memory": True},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    self._loaded_models.discard(model_id)
                    logger.info(f"ComfyUI: Freed model '{model_id}'")
                    return True
                else:
                    logger.warning(f"ComfyUI: Failed to free model, status {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"ComfyUI: Error freeing model: {e}")
            return False

    async def list_loaded(self) -> List[Dict[str, Any]]:
        """
        List models marked as loaded.

        Returns:
            List of dictionaries containing model information.
        """
        return [{"name": m, "backend": "comfyui"} for m in self._loaded_models]

    async def health_check(self) -> bool:
        """
        Check if ComfyUI server is responsive.

        Returns:
            True if ComfyUI is responsive, False otherwise.
        """
        try:
            session = await self._get_session()
            async with session.get(
                f"{self._host}/",
                timeout=aiohttp.ClientTimeout(total=self.HEALTH_TIMEOUT_SECONDS)
            ) as resp:
                is_healthy = resp.status == 200
                if is_healthy:
                    logger.debug(f"ComfyUI health check passed at {self._host}")
                else:
                    logger.warning(f"ComfyUI health check failed: {resp.status}")
                return is_healthy
        except Exception as e:
            logger.warning(f"ComfyUI health check failed: {e}")
            return False

    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        steps: int = 28,
        guidance: float = 4.0,
        seed: Optional[int] = None,
        workflow_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[bytes]:
        """
        Generate image using ComfyUI workflow API.

        Args:
            prompt: Text prompt for image generation.
            width: Output width in pixels.
            height: Output height in pixels.
            steps: Number of inference steps.
            guidance: Guidance scale.
            seed: Random seed (None for random).
            workflow_config: Model-specific workflow settings from profile.
                Contains keys like unet_name, clip_name, vae_name, etc.

        Returns:
            PNG image bytes on success, None on failure.
        """
        import random

        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        if workflow_config is None:
            workflow_config = {}

        # Build ComfyUI workflow JSON using config from profile
        workflow = self._build_workflow(
            prompt=prompt,
            width=width,
            height=height,
            steps=steps,
            guidance=guidance,
            seed=seed,
            config=workflow_config,
        )

        try:
            session = await self._get_session()

            # Connect WebSocket FIRST to get client_id for event routing
            # ComfyUI sends completion events only to the client that submitted the prompt
            waiter = await self._get_completion_waiter()
            client_id = waiter.client_id if waiter else None

            # Build submission payload (include client_id if available)
            payload = {"prompt": workflow}
            if client_id:
                payload["client_id"] = client_id

            # Submit workflow
            async with session.post(
                f"{self._host}/prompt",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"ComfyUI: Prompt submission failed: {resp.status} - {error_text}")
                    return None
                result = await resp.json()
                prompt_id = result.get("prompt_id")

            if not prompt_id:
                logger.error("ComfyUI: No prompt_id returned")
                return None

            logger.info(f"ComfyUI: Submitted workflow, prompt_id={prompt_id}, client_id={client_id}")

            # Wait for completion via WebSocket (client_id already connected)
            image_data = await self._wait_for_completion(prompt_id)
            return image_data

        except Exception as e:
            logger.error(f"ComfyUI: Image generation failed: {e}", exc_info=True)
            return None

    def _build_workflow(
        self,
        prompt: str,
        width: int,
        height: int,
        steps: int,
        guidance: float,
        seed: int,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build ComfyUI workflow JSON from configuration.

        Config-driven workflow builder supporting different model types.
        Model-specific settings come from ModelCapabilities.options["workflow"].

        FLUX.2 workflow structure (Mistral-based encoder):
        - UNETLoader: Load diffusion model
        - CLIPLoader: Load text encoder (Mistral-based for FLUX.2 NVFP4)
        - VAELoader: Load VAE
        - CLIPTextEncode: Standard text encoding (Mistral encoder is single-output)
        - FluxGuidance: Add guidance scale to conditioning
        - EmptyFlux2LatentImage: Create latent
        - KSampler: Sample (cfg=1.0, guidance handled via FluxGuidance node)
        - VAEDecode: Decode to image
        - SaveImage: Save output

        Note: CLIPTextEncodeFlux is for dual T5XXL+CLIP-L encoders. The Mistral-based
        FLUX.2 encoder uses standard CLIPTextEncode + FluxGuidance instead.

        Args:
            prompt: Text prompt.
            width: Image width.
            height: Image height.
            steps: Inference steps.
            guidance: Guidance scale (passed to FluxGuidance node).
            seed: Random seed.
            config: Workflow configuration from profile.

        Returns:
            ComfyUI workflow dictionary.
        """
        # Get model files from config (with sensible defaults for FLUX.2)
        unet_name = config.get("unet_name", "flux2-dev-nvfp4.safetensors")
        clip_name = config.get("clip_name", "mistral_3_small_flux2_fp4_mixed.safetensors")
        clip_type = config.get("clip_type", "flux2")
        vae_name = config.get("vae_name", "flux2-vae.safetensors")
        latent_type = config.get("latent_type", "EmptyFlux2LatentImage")
        sampler_name = config.get("sampler_name", "euler")
        scheduler = config.get("scheduler", "simple")

        return {
            "1": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": unet_name,
                    "weight_dtype": "default"
                }
            },
            "2": {
                "class_type": "CLIPLoader",
                "inputs": {
                    "clip_name": clip_name,
                    "type": clip_type
                }
            },
            "3": {
                "class_type": "VAELoader",
                "inputs": {
                    "vae_name": vae_name
                }
            },
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["2", 0],
                    "text": prompt
                }
            },
            "4a": {
                "class_type": "FluxGuidance",
                "inputs": {
                    "conditioning": ["4", 0],
                    "guidance": guidance
                }
            },
            "5": {
                "class_type": latent_type,
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1
                }
            },
            "6": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["4a", 0],
                    "negative": ["4a", 0],  # No negative for FLUX (same as positive)
                    "latent_image": ["5", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": 1.0,  # CFG=1.0 for FLUX (guidance in text encoder)
                    "sampler_name": sampler_name,
                    "scheduler": scheduler,
                    "denoise": 1.0
                }
            },
            "7": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["6", 0],
                    "vae": ["3", 0]
                }
            },
            "8": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["7", 0],
                    "filename_prefix": "troise"
                }
            }
        }

    async def _get_completion_waiter(self) -> Optional["IComfyUICompletionWaiter"]:
        """Get or create WebSocket completion waiter (lazy initialization).

        Returns:
            IComfyUICompletionWaiter if connected, None if connection failed.
        """
        async with self._ws_lock:
            # Check if we have a valid connection
            if self._completion_waiter and self._completion_waiter.is_connected:
                return self._completion_waiter

            # Try to create new WebSocket connection
            try:
                from .comfyui_websocket import ComfyUIWebSocket
                ws = ComfyUIWebSocket(self._host)
                await ws.connect()
                self._completion_waiter = ws  # Store as interface type
                logger.info("ComfyUI WebSocket connected for completion detection")
                return self._completion_waiter
            except Exception as e:
                logger.warning(f"ComfyUI WebSocket connection failed: {e}, will use HTTP polling")
                self._completion_waiter = None
                return None

    async def _wait_for_completion(self, prompt_id: str) -> Optional[bytes]:
        """Wait for workflow completion with WebSocket + polling fallback.

        Tries WebSocket first for efficient real-time detection.
        Falls back to HTTP polling if WebSocket is unavailable.

        Args:
            prompt_id: The ComfyUI prompt ID to wait for.

        Returns:
            Image bytes on success, None on failure/timeout.
        """
        # Try WebSocket-based completion detection first
        result = await self._wait_for_completion_ws(prompt_id)
        if result is not None:
            return result

        # Fall back to HTTP polling
        logger.info("ComfyUI: Falling back to HTTP polling for completion")
        return await self._wait_for_completion_poll(prompt_id)

    async def _wait_for_completion_ws(self, prompt_id: str) -> Optional[bytes]:
        """Wait for completion via WebSocket, then fetch image.

        Uses IComfyUICompletionWaiter interface (DIP).

        Args:
            prompt_id: The ComfyUI prompt ID to wait for.

        Returns:
            Image bytes if WebSocket succeeded and image retrieved, None otherwise.
        """
        waiter = await self._get_completion_waiter()
        if waiter is None:
            return None  # Fall back to polling

        try:
            success = await waiter.wait_for_completion(prompt_id, self.WORKFLOW_TIMEOUT_SECONDS)
            if not success:
                logger.warning(f"ComfyUI: WebSocket reported failure for prompt {prompt_id}")
                return None

            # WebSocket confirmed completion - fetch image with retry
            # (handles race condition where history isn't updated yet)
            return await self._poll_history_with_retry(prompt_id)

        except Exception as e:
            logger.warning(f"ComfyUI: WebSocket completion failed: {e}")
            return None

    async def _poll_history_with_retry(self, prompt_id: str) -> Optional[bytes]:
        """Poll /history with retries after WebSocket completion signal.

        Handles race condition where execution_success fires before outputs are persisted.

        Args:
            prompt_id: The ComfyUI prompt ID.

        Returns:
            Image bytes on success, None on failure.
        """
        session = await self._get_session()

        for attempt in range(self.HISTORY_POLL_RETRIES):
            try:
                async with session.get(f"{self._host}/history/{prompt_id}") as resp:
                    if resp.status != 200:
                        await asyncio.sleep(self.HISTORY_POLL_DELAY)
                        continue

                    history = await resp.json()
                    if prompt_id not in history:
                        await asyncio.sleep(self.HISTORY_POLL_DELAY)
                        continue

                    outputs = history[prompt_id].get("outputs", {})
                    for node_id, output in outputs.items():
                        if "images" in output:
                            image_info = output["images"][0]
                            filename = image_info["filename"]
                            subfolder = image_info.get("subfolder", "")
                            logger.info(f"ComfyUI: Image ready after {attempt + 1} poll(s): {filename}")
                            return await self._fetch_image(filename, subfolder)

                    # Outputs exist but no image yet
                    await asyncio.sleep(self.HISTORY_POLL_DELAY)

            except Exception as e:
                logger.warning(f"ComfyUI: History poll attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(self.HISTORY_POLL_DELAY)

        logger.error(f"ComfyUI: Failed to retrieve image after {self.HISTORY_POLL_RETRIES} history polls")
        return None

    async def _wait_for_completion_poll(self, prompt_id: str) -> Optional[bytes]:
        """Poll for workflow completion and retrieve image (fallback method).

        This is the original polling implementation used when WebSocket is unavailable.

        Args:
            prompt_id: The ComfyUI prompt ID to wait for.

        Returns:
            Image bytes on success, None on failure/timeout.
        """
        session = await self._get_session()
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < self.WORKFLOW_TIMEOUT_SECONDS:
            try:
                async with session.get(f"{self._host}/history/{prompt_id}") as resp:
                    if resp.status != 200:
                        await asyncio.sleep(1)
                        continue

                    history = await resp.json()
                    if prompt_id not in history:
                        await asyncio.sleep(1)
                        continue

                    outputs = history[prompt_id].get("outputs", {})
                    # Find SaveImage node output
                    for node_id, output in outputs.items():
                        if "images" in output:
                            image_info = output["images"][0]
                            filename = image_info["filename"]
                            subfolder = image_info.get("subfolder", "")

                            logger.info(f"ComfyUI: Image ready: {filename}")
                            # Fetch image from ComfyUI
                            return await self._fetch_image(filename, subfolder)

                    # No image output yet
                    await asyncio.sleep(1)

            except Exception as e:
                logger.warning(f"ComfyUI: Error polling history: {e}")
                await asyncio.sleep(1)

        logger.error(f"ComfyUI: Timeout waiting for prompt {prompt_id}")
        return None

    async def _fetch_image(self, filename: str, subfolder: str) -> Optional[bytes]:
        """
        Fetch generated image from ComfyUI.

        Args:
            filename: Image filename.
            subfolder: Subfolder within output directory.

        Returns:
            Image bytes on success, None on failure.
        """
        session = await self._get_session()
        params = {"filename": filename, "type": "output"}
        if subfolder:
            params["subfolder"] = subfolder

        async with session.get(f"{self._host}/view", params=params) as resp:
            if resp.status == 200:
                return await resp.read()
            logger.error(f"ComfyUI: Failed to fetch image: {resp.status}")
            return None

    async def warmup(self, workflow_config: Dict[str, Any]) -> bool:
        """
        Pre-load diffusion models by generating a tiny test image.

        Submits a minimal 64x64 workflow to force model loading into VRAM.
        This is called on startup to ensure first user request is fast.

        Args:
            workflow_config: Model-specific workflow settings from profile.

        Returns:
            True if warmup succeeded, False otherwise.
        """
        logger.info("ComfyUI: Starting warmup (pre-loading models)...")
        try:
            result = await self.generate_image(
                prompt="warmup",
                width=64,
                height=64,
                steps=1,
                guidance=1.0,
                seed=42,
                workflow_config=workflow_config,
            )
            if result:
                logger.info("ComfyUI: Warmup complete - models loaded into VRAM")
                return True
            else:
                logger.warning("ComfyUI: Warmup failed - no image returned")
                return False
        except Exception as e:
            logger.error(f"ComfyUI: Warmup failed: {e}")
            return False


class DiffusionClient(IBackendClient):
    """
    In-process backend for diffusion models (FLUX, Stable Diffusion).

    Unlike HTTP-based backends, this manages GPU memory directly via diffusers.
    Load/unload means loading/releasing the pipeline from GPU.
    """

    def __init__(self):
        """Initialize the DiffusionClient with empty pipeline registry."""
        import asyncio
        self._pipelines: Dict[str, Any] = {}  # model_id -> pipeline
        self._lock = asyncio.Lock()

    async def load_model(self, model_id: str, keep_alive: str = "10m") -> bool:
        """
        Load diffusion pipeline into GPU memory.

        Args:
            model_id: The diffusion model identifier to load.
            keep_alive: Ignored for diffusion (in-process management).

        Returns:
            True if the model was loaded successfully, False otherwise.
        """
        import asyncio

        async with self._lock:
            if model_id in self._pipelines:
                logger.info(f"Diffusion model '{model_id}' already loaded")
                return True

            try:
                logger.info(f"Loading diffusion model '{model_id}'...")
                pipeline = await asyncio.to_thread(
                    self._load_diffusion_pipeline, model_id
                )

                if pipeline:
                    self._pipelines[model_id] = pipeline
                    logger.info(f"Diffusion model '{model_id}' loaded successfully")
                    return True
                return False

            except Exception as e:
                logger.error(f"Failed to load diffusion model '{model_id}': {e}")
                return False

    async def unload_model(self, model_id: str) -> bool:
        """
        Unload diffusion pipeline and free GPU memory.

        Args:
            model_id: The diffusion model identifier to unload.

        Returns:
            True if the model was unloaded successfully, False otherwise.
        """
        import torch

        async with self._lock:
            if model_id in self._pipelines:
                try:
                    del self._pipelines[model_id]
                    torch.cuda.empty_cache()
                    logger.info(f"Diffusion model '{model_id}' unloaded successfully")
                    return True
                except Exception as e:
                    logger.error(f"Error unloading diffusion model '{model_id}': {e}")
                    return False
            else:
                logger.warning(f"Diffusion model '{model_id}' not loaded, nothing to unload")
                return True

    async def list_loaded(self) -> List[Dict[str, Any]]:
        """
        List currently loaded diffusion pipelines.

        Returns:
            List of dictionaries containing model information.
        """
        return [{"name": mid, "backend": "diffusion"} for mid in self._pipelines]

    async def health_check(self) -> bool:
        """
        Check if diffusion backend is available.

        Always returns True as this is an in-process backend.

        Returns:
            True (always available).
        """
        return True

    def get_pipeline(self, model_id: str) -> Optional[Any]:
        """
        Get a loaded pipeline for direct use.

        Args:
            model_id: The diffusion model identifier.

        Returns:
            The diffusion pipeline, or None if not loaded.
        """
        return self._pipelines.get(model_id)

    def _load_diffusion_pipeline(self, model_id: str) -> Any:
        """
        Load appropriate diffusion pipeline (runs in thread pool).

        Args:
            model_id: The diffusion model identifier.

        Returns:
            The loaded diffusion pipeline.

        Raises:
            ValueError: If the model_id is unknown.
        """
        if model_id == "flux2-dev-bnb4bit":
            # BitsAndBytes 4-bit quantized FLUX.2-dev with full diffusers support
            from diffusers import Flux2Pipeline, Flux2Transformer2DModel
            from transformers import Mistral3ForConditionalGeneration
            import torch

            repo_id = "diffusers/FLUX.2-dev-bnb-4bit"
            torch_dtype = torch.bfloat16

            logger.info("Loading FLUX 2.dev 4-bit transformer...")
            transformer = Flux2Transformer2DModel.from_pretrained(
                repo_id,
                subfolder="transformer",
                torch_dtype=torch_dtype,
                device_map="cpu",
            )

            logger.info("Loading FLUX 2.dev 4-bit text encoder (Mistral3)...")
            text_encoder = Mistral3ForConditionalGeneration.from_pretrained(
                repo_id,
                subfolder="text_encoder",
                torch_dtype=torch_dtype,
                device_map="cpu",
            )

            logger.info("Loading FLUX 2.dev 4-bit pipeline...")
            pipe = Flux2Pipeline.from_pretrained(
                repo_id,
                transformer=transformer,
                text_encoder=text_encoder,
                torch_dtype=torch_dtype,
            )

            logger.info("Enabling model CPU offload...")
            pipe.enable_model_cpu_offload()

            return pipe

        raise ValueError(f"Unknown diffusion model: {model_id}")


class BackendManager:
    """
    Unified manager for all AI inference backends.

    Provides a single interface to manage multiple backend types (Ollama, SGLang, vLLM)
    including remote management via SSH for DGX servers.

    Features:
    - Automatic client initialization from configuration
    - SSH-based remote backend start/stop on DGX
    - Health checking across all backends
    - Model lifecycle management (load/unload)
    - Aggregated model listing
    """

    def __init__(self, config: Config):
        """
        Initialize the BackendManager.

        Args:
            config: The application configuration containing backend
                    and DGX SSH settings.
        """
        self.config = config
        self._clients: Dict[str, IBackendClient] = {}
        self._ssh_conn: Optional[asyncssh.SSHClientConnection] = None

        self._init_clients()

    def _init_clients(self) -> None:
        """
        Initialize backend clients from configuration.

        Creates appropriate client instances for each configured backend
        based on the backend type (ollama, sglang, vllm).
        """
        for name, backend_config in self.config.backends.items():
            client = self._create_client(backend_config)
            if client:
                self._clients[name] = client
                logger.info(f"Initialized {backend_config.type} client '{name}' at {backend_config.host}")

    def _create_client(self, backend_config: BackendConfig) -> Optional[IBackendClient]:
        """
        Create a backend client based on configuration.

        Args:
            backend_config: The backend configuration.

        Returns:
            An appropriate IBackendClient instance, or None if type is unknown.
        """
        backend_type = backend_config.type.lower()

        if backend_type == "ollama":
            return OllamaClient(backend_config.host)
        elif backend_type == "sglang":
            return SGLangClient(backend_config.host)
        elif backend_type == "vllm":
            return VLLMClient(backend_config.host)
        elif backend_type == "comfyui":
            return ComfyUIClient(backend_config.host)
        elif backend_type == "diffusion":
            return DiffusionClient()
        else:
            logger.warning(f"Unknown backend type: {backend_type}")
            return None

    async def _get_ssh(self) -> Optional[asyncssh.SSHClientConnection]:
        """
        Get or create an SSH connection to the DGX server.

        Uses configuration from config.dgx_config with keys:
        - host: DGX server hostname
        - user: SSH username
        - ssh_key: Path to SSH private key

        Returns:
            An asyncssh connection, or None if connection fails.
        """
        if self._ssh_conn and not self._ssh_conn.is_closed():
            return self._ssh_conn

        dgx_config = self.config.dgx_config
        if not dgx_config:
            logger.error("DGX configuration not found")
            return None

        host = dgx_config.get("host")
        user = dgx_config.get("user")
        ssh_key = dgx_config.get("ssh_key")

        if not all([host, user, ssh_key]):
            logger.error("Incomplete DGX configuration: host, user, and ssh_key required")
            return None

        try:
            self._ssh_conn = await asyncssh.connect(
                host=host,
                username=user,
                client_keys=[ssh_key],
                known_hosts=None  # In production, configure known_hosts properly
            )
            logger.info(f"SSH connection established to {user}@{host}")
            return self._ssh_conn

        except asyncssh.Error as e:
            logger.error(f"SSH connection failed to {host}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error establishing SSH connection: {e}")
            return None

    async def close(self) -> None:
        """Close all client sessions and SSH connection."""
        for name, client in self._clients.items():
            if hasattr(client, 'close'):
                await client.close()
                logger.debug(f"Closed client '{name}'")

        if self._ssh_conn and not self._ssh_conn.is_closed():
            self._ssh_conn.close()
            await self._ssh_conn.wait_closed()
            logger.debug("SSH connection closed")

    async def start_backend(self, backend_name: str, model: Optional[str] = None) -> bool:
        """
        Start a backend on the DGX server via SSH.

        Executes the backend's configured dgx_script to start the service.

        Args:
            backend_name: The name of the backend to start.
            model: Optional model to pass to the start script.

        Returns:
            True if the backend was started successfully, False otherwise.
        """
        if backend_name not in self.config.backends:
            logger.error(f"Backend '{backend_name}' not found in configuration")
            return False

        backend_config = self.config.backends[backend_name]
        if not backend_config.dgx_script:
            logger.error(f"No dgx_script configured for backend '{backend_name}'")
            return False

        ssh = await self._get_ssh()
        if not ssh:
            return False

        try:
            # Build command with optional model argument
            cmd = backend_config.dgx_script
            if model:
                cmd = f"{cmd} --model {model}"

            result = await ssh.run(cmd)

            if result.exit_status == 0:
                logger.info(f"Backend '{backend_name}' started successfully")
                return True
            else:
                logger.error(f"Failed to start backend '{backend_name}': {result.stderr}")
                return False

        except asyncssh.Error as e:
            logger.error(f"SSH error starting backend '{backend_name}': {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error starting backend '{backend_name}': {e}")
            return False

    async def stop_backend(self, backend_name: str) -> bool:
        """
        Stop a backend on the DGX server via SSH.

        Executes the backend's dgx_script with 'stop' argument.

        Args:
            backend_name: The name of the backend to stop.

        Returns:
            True if the backend was stopped successfully, False otherwise.
        """
        if backend_name not in self.config.backends:
            logger.error(f"Backend '{backend_name}' not found in configuration")
            return False

        backend_config = self.config.backends[backend_name]
        if not backend_config.dgx_script:
            logger.error(f"No dgx_script configured for backend '{backend_name}'")
            return False

        ssh = await self._get_ssh()
        if not ssh:
            return False

        try:
            # Derive stop script from start script (convention: add 'stop' argument)
            cmd = f"{backend_config.dgx_script} stop"

            result = await ssh.run(cmd)

            if result.exit_status == 0:
                logger.info(f"Backend '{backend_name}' stopped successfully")
                return True
            else:
                logger.error(f"Failed to stop backend '{backend_name}': {result.stderr}")
                return False

        except asyncssh.Error as e:
            logger.error(f"SSH error stopping backend '{backend_name}': {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error stopping backend '{backend_name}': {e}")
            return False

    async def health_check(self, backend_name: str) -> bool:
        """
        Check if a specific backend is healthy.

        Args:
            backend_name: The name of the backend to check.

        Returns:
            True if the backend is healthy, False otherwise.
        """
        if backend_name not in self._clients:
            logger.warning(f"Backend '{backend_name}' not found")
            return False

        return await self._clients[backend_name].health_check()

    async def load_model(self, model_id: str, keep_alive: str = "10m") -> bool:
        """
        Load a model into the appropriate backend.

        Determines the correct backend for the model using configuration
        and delegates to the appropriate client.

        Args:
            model_id: The model identifier to load.
            keep_alive: How long to keep the model loaded (default: "10m").

        Returns:
            True if the model was loaded successfully, False otherwise.
        """
        # Find the backend for this model
        backend_config = self.config.get_backend_for_model(model_id)
        if not backend_config:
            logger.error(f"No backend found for model '{model_id}'")
            return False

        backend_type = backend_config.type.lower()
        logger.debug(f"load_model: {model_id}, backend_type={backend_type}")

        # Direct check for ComfyUI models (diffusion backend type)
        # This ensures ComfyUI models are always routed correctly
        if backend_type == "comfyui":
            comfyui_client = self._clients.get("comfyui")
            if comfyui_client:
                logger.debug(f"Routing {model_id} to ComfyUI client")
                return await comfyui_client.load_model(model_id, keep_alive)
            else:
                logger.error(f"ComfyUI client not available for model '{model_id}'")
                return False

        # Find the client for this backend type (match by type, not object equality)
        for name, config in self.config.backends.items():
            if config.type == backend_type and name in self._clients:
                return await self._clients[name].load_model(model_id, keep_alive)

        # Fallback to default ollama client
        if "ollama" in self._clients:
            return await self._clients["ollama"].load_model(model_id, keep_alive)

        logger.error(f"No suitable client found for model '{model_id}' (backend type: {backend_type})")
        return False

    async def unload_model(self, model_id: str) -> bool:
        """
        Unload a model from the appropriate backend.

        Args:
            model_id: The model identifier to unload.

        Returns:
            True if the model was unloaded successfully, False otherwise.
        """
        # Check if this is a ComfyUI model (tracked in client's _loaded_models)
        # ComfyUI models may not be in profile config, so check the client directly
        comfyui_client = self._clients.get("comfyui")
        if comfyui_client and hasattr(comfyui_client, '_loaded_models'):
            if model_id in comfyui_client._loaded_models:
                logger.info(f"Unloading ComfyUI model: {model_id}")
                return await comfyui_client.unload_model(model_id)

        # Find the backend for this model
        backend_config = self.config.get_backend_for_model(model_id)
        if not backend_config:
            logger.error(f"No backend found for model '{model_id}'")
            return False

        # Find the client for this backend type (match by type, not object equality)
        for name, config in self.config.backends.items():
            if config.type == backend_config.type and name in self._clients:
                return await self._clients[name].unload_model(model_id)

        # Fallback to default ollama client
        if "ollama" in self._clients:
            return await self._clients["ollama"].unload_model(model_id)

        logger.error(f"No suitable client found for model '{model_id}' (backend type: {backend_config.type})")
        return False

    async def list_loaded_models(self, backend_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all loaded models across backends.

        Args:
            backend_name: Optional specific backend to query. If None,
                         queries all backends and aggregates results.

        Returns:
            List of dictionaries containing model information from all
            queried backends.
        """
        if backend_name:
            if backend_name not in self._clients:
                logger.warning(f"Backend '{backend_name}' not found")
                return []

            models = await self._clients[backend_name].list_loaded()
            # Add backend name to each model entry
            for model in models:
                model["backend_name"] = backend_name
            return models

        # Query all backends
        all_models = []
        for name, client in self._clients.items():
            try:
                models = await client.list_loaded()
                for model in models:
                    model["backend_name"] = name
                all_models.extend(models)
            except Exception as e:
                logger.error(f"Error listing models from backend '{name}': {e}")

        return all_models

    def get_client(self, backend_name: str) -> Optional[IBackendClient]:
        """
        Get a specific backend client.

        Args:
            backend_name: The name of the backend.

        Returns:
            The backend client, or None if not found.
        """
        return self._clients.get(backend_name)
