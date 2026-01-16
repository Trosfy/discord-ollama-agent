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

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

import aiohttp
import asyncssh

from app.core.config import Config, BackendConfig

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
        for the specified duration.

        Args:
            model_id: The model identifier to load.
            keep_alive: Duration to keep the model loaded (default: "10m").

        Returns:
            True if the model was loaded successfully, False otherwise.
        """
        try:
            session = await self._get_session()
            url = f"{self.host}/api/generate"
            payload = {
                "model": model_id,
                "prompt": "",
                "keep_alive": keep_alive
            }

            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Model '{model_id}' loaded successfully with keep_alive={keep_alive}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to load model '{model_id}': {response.status} - {error_text}")
                    return False

        except aiohttp.ClientError as e:
            logger.error(f"Connection error loading model '{model_id}': {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error loading model '{model_id}': {e}")
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
        try:
            session = await self._get_session()
            url = f"{self.host}/api/generate"
            payload = {
                "model": model_id,
                "prompt": "",
                "keep_alive": "0"
            }

            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Model '{model_id}' unloaded successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to unload model '{model_id}': {response.status} - {error_text}")
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

        # Find the client for this backend type
        for name, config in self.config.backends.items():
            if config == backend_config and name in self._clients:
                return await self._clients[name].load_model(model_id, keep_alive)

        # Fallback to default ollama client
        if "ollama" in self._clients:
            return await self._clients["ollama"].load_model(model_id, keep_alive)

        logger.error(f"No suitable client found for model '{model_id}'")
        return False

    async def unload_model(self, model_id: str) -> bool:
        """
        Unload a model from the appropriate backend.

        Args:
            model_id: The model identifier to unload.

        Returns:
            True if the model was unloaded successfully, False otherwise.
        """
        # Find the backend for this model
        backend_config = self.config.get_backend_for_model(model_id)
        if not backend_config:
            logger.error(f"No backend found for model '{model_id}'")
            return False

        # Find the client for this backend type
        for name, config in self.config.backends.items():
            if config == backend_config and name in self._clients:
                return await self._clients[name].unload_model(model_id)

        # Fallback to default ollama client
        if "ollama" in self._clients:
            return await self._clients["ollama"].unload_model(model_id)

        logger.error(f"No suitable client found for model '{model_id}'")
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
