"""Memory Orchestrator for TROISE AI.

Provides lightweight memory management using BackendManager for actual operations.
Detects system RAM automatically and integrates with ProfileManager for fallback.

Key Features:
- Auto-detect system RAM via `free` command
- Priority-based eviction (LOW first, CRITICAL as last resort)
- Request load with automatic eviction when needed
- Sync with backends to reconcile state
- Health check loop for recovery probing
"""
import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Union, Tuple

from app.core.config import Config, ModelCapabilities, ModelPriority
from app.core.models import ExtendedOllamaModel, ExtendedOpenAIModel
from app.core.interfaces import IConfigProfile
from .backend_manager import BackendManager
from .model_factory import ModelFactory
from .profile_manager import ProfileManager

logger = logging.getLogger(__name__)


@dataclass
class LoadedModel:
    """Tracks state of a loaded model in VRAM."""
    model_id: str
    size_gb: float
    priority: ModelPriority
    keep_alive_until: datetime
    loaded_at: datetime
    last_accessed: datetime


class VRAMOrchestrator:
    """
    Lightweight VRAM management using BackendManager for actual operations.

    This class tracks which models are loaded, manages eviction based on
    priority and LRU ordering, and integrates with ProfileManager for
    fallback/recovery decisions.

    Example:
        orchestrator = VRAMOrchestrator(config, backend_manager, profile_manager)

        # Request to load a model (handles eviction automatically)
        success = await orchestrator.request_load("gpt-oss:20b")

        # Get current VRAM status
        status = await orchestrator.get_status()
    """

    VRAM_BUFFER_GB = 10.0  # Keep 10GB free for system
    HEALTH_CHECK_INTERVAL = 60  # Seconds between health checks

    def __init__(
        self,
        config: Config,
        backend_manager: BackendManager,
        profile_manager: ProfileManager,
    ):
        """
        Initialize the VRAM Orchestrator.

        Args:
            config: Application configuration.
            backend_manager: Backend manager for actual load/unload operations.
            profile_manager: Profile manager for fallback/recovery decisions.
        """
        self._config = config
        self._backend_manager = backend_manager
        self._profile_manager = profile_manager
        self._model_factory = ModelFactory(config)
        self._registry: Dict[str, LoadedModel] = {}
        self._loading: Set[str] = set()
        self._lock = asyncio.Lock()
        self._vram_limit_gb = self._detect_system_vram()

    SYSTEM_RESERVE_PERCENT = 0.05  # Reserve 5% of total RAM for system

    def _detect_system_vram(self) -> float:
        """
        Detect system memory limit for model loading.

        Uses total RAM minus 5% reserve for system processes.
        This provides a predictable limit regardless of current memory state.

        Returns:
            Available memory limit in GB (total * 0.95).
        """
        try:
            result = subprocess.run(
                ['free', '-b'],  # Get memory in bytes for precision
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.warning(f"free command failed: {result.stderr}")
                return 100.0

            # Parse the "Mem:" line from free output
            # Format: Mem:  total  used  free  shared  buff/cache  available
            for line in result.stdout.strip().split('\n'):
                if line.startswith('Mem:'):
                    parts = line.split()
                    total_bytes = int(parts[1])
                    total_gb = total_bytes / (1024 ** 3)
                    limit_gb = total_gb * (1 - self.SYSTEM_RESERVE_PERCENT)

                    logger.info(
                        f"System RAM: {total_gb:.1f}GB total, {limit_gb:.1f}GB limit for models (5% reserved)"
                    )
                    return limit_gb

            logger.warning("Could not parse free output, using 100GB default")
            return 100.0

        except FileNotFoundError:
            logger.warning("free command not found, using 100GB default")
            return 100.0
        except subprocess.TimeoutExpired:
            logger.warning("free command timed out, using 100GB default")
            return 100.0
        except Exception as e:
            logger.warning(f"Memory detection failed: {e}, using 100GB default")
            return 100.0

    def _get_current_memory_usage_gb(self) -> float:
        """
        Get current system memory usage dynamically.

        Returns:
            Current memory used in GB.
        """
        try:
            result = subprocess.run(
                ['free', '-b'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.startswith('Mem:'):
                        parts = line.split()
                        used_bytes = int(parts[2])  # "used" column
                        return used_bytes / (1024 ** 3)
        except Exception as e:
            logger.warning(f"RAM detection failed: {e}")

        return 0.0

    def _get_available_ram_gb(self) -> float:
        """
        Get available RAM for model loading.

        Calculates: limit (total * 0.95) - current usage

        Returns:
            Available RAM in GB.
        """
        current_used = self._get_current_memory_usage_gb()
        available = self._vram_limit_gb - current_used
        return max(0.0, available)

    @property
    def _profile(self) -> IConfigProfile:
        """Get active profile from ProfileManager."""
        return self._profile_manager.get_current_profile()

    def get_profile_model(self, role: str = "agent") -> str:
        """
        Get the default model for a role from the current profile.

        Args:
            role: Model role - "general", "research", "code", "braindump", "router",
                  "vision", "embedding", "image_handler", "image"

        Returns:
            Model ID from the profile for the specified role.
        """
        profile = self._profile
        role_map = {
            "general": profile.general_model,
            "research": profile.research_model,
            "code": profile.code_model,
            "braindump": profile.braindump_model,
            "router": profile.router_model,
            "vision": profile.vision_model,
            "embedding": profile.embedding_model,
            "image_handler": profile.image_handler_model,
            "image": profile.image_model,
        }
        return role_map.get(role, profile.general_model)

    @property
    def vram_limit_gb(self) -> float:
        """Get the current VRAM limit in GB."""
        return self._vram_limit_gb

    @property
    def current_usage_gb(self) -> float:
        """Get current VRAM usage in GB."""
        return sum(m.size_gb for m in self._registry.values())

    def _get_model_capabilities(self, model_id: str) -> Optional[ModelCapabilities]:
        """
        Get model config from profile's available_models.

        Args:
            model_id: The model identifier to look up.

        Returns:
            ModelCapabilities if found, None otherwise.
        """
        for model in self._profile.available_models:
            if model.name == model_id:
                return model
        return None

    def get_model_capabilities(self, model_id: str) -> Optional[ModelCapabilities]:
        """
        Get capabilities for a model if it exists in the current profile.

        Public interface for model validation when user specifies a model
        via user_config. Used by main.py to validate user model selection
        before routing/execution.

        Args:
            model_id: The model identifier to look up.

        Returns:
            ModelCapabilities if found, None otherwise.
        """
        return self._get_model_capabilities(model_id)

    async def list_available_models(self) -> List[Dict[str, Any]]:
        """
        List all models available in the current profile with their capabilities.

        Used by /models endpoint for web-service dropdown population.
        Returns model info including capabilities for UI hints (e.g., show
        thinking toggle only for models with supports_thinking=true).

        Returns:
            List of model info dicts including name, capabilities, and settings.
        """
        return [
            {
                "name": m.name,
                "vram_size_gb": m.vram_size_gb,
                "priority": m.priority,
                "backend": {"type": m.backend.type},
                "api_managed": m.api_managed,
                "supports_tools": m.supports_tools,
                "supports_vision": m.supports_vision,
                "supports_thinking": m.supports_thinking,
                "thinking_format": m.thinking_format,
                "default_thinking_level": m.default_thinking_level,
                "context_window": m.context_window,
            }
            for m in self._profile.available_models
        ]

    def is_loaded(self, model_id: str) -> bool:
        """
        Check if a model is currently loaded.

        Args:
            model_id: The model identifier to check.

        Returns:
            True if the model is loaded, False otherwise.
        """
        return model_id in self._registry

    def is_loading(self, model_id: str) -> bool:
        """
        Check if a model is currently being loaded.

        Args:
            model_id: The model identifier to check.

        Returns:
            True if the model is being loaded, False otherwise.
        """
        return model_id in self._loading

    async def request_load(self, model_id: str) -> bool:
        """
        Request to load a model. Handles eviction if needed.

        This method:
        1. Checks if model is already loaded in registry (updates last_accessed)
        2. Checks if model is already loaded in backend (syncs to registry)
        3. Validates model is in current profile
        4. Evicts lower-priority models if needed
        5. Loads the model via BackendManager
        6. Notifies ProfileManager of success/failure

        Args:
            model_id: The model identifier to load.

        Returns:
            True if the model was loaded successfully.

        Raises:
            ValueError: If model is not in the current profile.
            MemoryError: If there's not enough VRAM and eviction failed.
        """
        async with self._lock:
            logger.debug(f"request_load: {model_id}, registry={list(self._registry.keys())}")

            # Already in our registry?
            if model_id in self._registry:
                self._registry[model_id].last_accessed = datetime.now()
                logger.debug(f"Keep-alive extended: {model_id}")
                return True

            # Already loading?
            if model_id in self._loading:
                logger.debug(f"Model '{model_id}' is already being loaded")
                return True

            # Get model config FROM PROFILE
            model_caps = self._get_model_capabilities(model_id)
            if not model_caps:
                error = f"Model '{model_id}' not in profile '{self._profile.profile_name}'"
                logger.error(error)
                self._profile_manager.record_load_failure(model_id, error)
                raise ValueError(error)

            # Check if model is already loaded in backend (but not in our registry)
            try:
                loaded_models = await self._backend_manager.list_loaded_models()
                loaded_ids = {m.get('name', m.get('model', '')) for m in loaded_models}
                if model_id in loaded_ids:
                    # Model is already loaded in backend, just register it
                    await self._mark_loaded(model_id, model_caps)
                    self._profile_manager.record_load_success(model_id)
                    logger.info(f"Model already loaded in backend: {model_id}")
                    return True
            except Exception as e:
                logger.warning(f"Failed to check backend for loaded models: {e}")

            required_gb = model_caps.vram_size_gb

            # Check if eviction needed using fresh RAM detection
            # This accounts for memory used by other processes/models outside our registry
            available_gb = self._get_available_ram_gb()
            if required_gb > available_gb:
                logger.info(
                    f"Need {required_gb:.1f}GB for '{model_id}', "
                    f"only {available_gb:.1f}GB available (registry: {self.current_usage_gb:.1f}GB)"
                )
                freed = await self._evict_for_space(required_gb)
                if not freed:
                    # Memory release can be async (especially ComfyUI /free)
                    # FLUX model (~20GB) can take 10-20 seconds to fully release
                    # Retry with delays to allow memory to be properly released
                    max_retries = 15
                    retry_delay = 2.0  # seconds (total: 30s max wait)
                    for retry in range(max_retries):
                        await asyncio.sleep(retry_delay)
                        available_gb = self._get_available_ram_gb()
                        if required_gb <= available_gb:
                            logger.info(
                                f"Memory available after {retry + 1} retries: "
                                f"{available_gb:.1f}GB (need {required_gb:.1f}GB)"
                            )
                            break
                        logger.debug(
                            f"Waiting for memory release (retry {retry + 1}/{max_retries}): "
                            f"{available_gb:.1f}GB available, need {required_gb:.1f}GB"
                        )
                    else:
                        # All retries exhausted
                        available_gb = self._get_available_ram_gb()
                        if required_gb > available_gb:
                            error = f"Cannot free {required_gb:.1f}GB for '{model_id}', only {available_gb:.1f}GB available after {max_retries} retries"
                            logger.error(error)
                            self._profile_manager.record_load_failure(model_id, error)
                            raise MemoryError(error)

            # Mark as loading
            self._loading.add(model_id)
            load_start = time.time()

            try:
                # Determine keep_alive from backend options
                keep_alive = "10m"
                if model_caps.backend.options:
                    keep_alive = model_caps.backend.options.get("keep_alive", "10m")

                # Use BackendManager to actually load
                backend_type = model_caps.backend.type if model_caps.backend else "unknown"
                logger.info(f"Loading model via backend: {model_id} (type={backend_type}, size={required_gb:.1f}GB)")
                success = await self._backend_manager.load_model(model_id, keep_alive)
                load_ms = (time.time() - load_start) * 1000

                if success:
                    await self._mark_loaded(model_id, model_caps)
                    self._profile_manager.record_load_success(model_id)
                    logger.info(f"Model loaded: {model_id} ({required_gb:.1f}GB), load_time={load_ms:.0f}ms")
                else:
                    self._profile_manager.record_load_failure(model_id, "Backend returned false")
                    logger.error(f"Failed to load model '{model_id}': Backend returned false")

                return success

            except Exception as e:
                self._profile_manager.record_load_failure(model_id, str(e))
                logger.error(f"Failed to load model '{model_id}': {e}")
                raise

            finally:
                self._loading.discard(model_id)

    async def _mark_loaded(self, model_id: str, caps: ModelCapabilities) -> None:
        """
        Register model as loaded in the registry.

        Args:
            model_id: The model identifier.
            caps: The model capabilities.
        """
        # Parse keep_alive duration from backend options
        keep_alive_str = "10m"
        if caps.backend.options:
            keep_alive_str = caps.backend.options.get("keep_alive", "10m")

        # Parse duration (supports "10m", "1h", etc.)
        keep_alive_mins = self._parse_duration_minutes(keep_alive_str)

        # Convert priority string to enum
        priority = ModelPriority[caps.priority]

        self._registry[model_id] = LoadedModel(
            model_id=model_id,
            size_gb=caps.vram_size_gb,
            priority=priority,
            keep_alive_until=datetime.now() + timedelta(minutes=keep_alive_mins),
            loaded_at=datetime.now(),
            last_accessed=datetime.now(),
        )

    def _parse_duration_minutes(self, duration_str: str) -> int:
        """
        Parse duration string to minutes.

        Supports formats: "10m", "1h", "30s" (seconds rounded to 1 min)

        Args:
            duration_str: Duration string like "10m" or "1h".

        Returns:
            Duration in minutes.
        """
        duration_str = duration_str.strip().lower()

        if duration_str.endswith('h'):
            return int(duration_str[:-1]) * 60
        elif duration_str.endswith('m'):
            return int(duration_str[:-1])
        elif duration_str.endswith('s'):
            return max(1, int(duration_str[:-1]) // 60)
        else:
            # Assume minutes if no suffix
            return int(duration_str)

    async def _sync_registry_from_backends(self) -> None:
        """
        Sync registry with actual backend state.

        Discovers models loaded in backends that aren't in our registry
        and adds them if they're in the current profile. This is essential
        for eviction to work on startup when registry is empty.
        """
        try:
            loaded_models = await self._backend_manager.list_loaded_models()
            loaded_ids = {m.get('name', m.get('model', '')) for m in loaded_models}

            # Add backend models to registry if they're in our profile but not registered
            for model_id in loaded_ids:
                if model_id and model_id not in self._registry:
                    model_caps = self._get_model_capabilities(model_id)
                    if model_caps:
                        # Register the model that's loaded in backend
                        await self._mark_loaded(model_id, model_caps)
                        logger.info(f"Sync: Registered '{model_id}' from backend ({model_caps.vram_size_gb:.1f}GB)")

            # Also remove models from registry if they're no longer in backend
            for model_id in list(self._registry.keys()):
                if model_id not in loaded_ids:
                    logger.info(f"Sync: '{model_id}' no longer in backend, removing from registry")
                    del self._registry[model_id]

        except Exception as e:
            logger.warning(f"Failed to sync registry from backends: {e}")

    async def _evict_models(
        self,
        candidates: List[tuple],
        required_gb: float,
    ) -> float:
        """
        Evict models from candidates list until required_gb is freed.

        Args:
            candidates: List of (model_id, LoadedModel) tuples to evict.
            required_gb: Amount of VRAM to free in GB.

        Returns:
            Total GB freed.
        """
        freed_gb = 0.0
        for model_id, model in candidates:
            if freed_gb >= required_gb:
                break
            try:
                success = await self._backend_manager.unload_model(model_id)
                if success:
                    del self._registry[model_id]
                    freed_gb += model.size_gb
                    logger.info(f"Evicted: {model_id} ({model.size_gb:.1f}GB, {model.priority.name})")
                else:
                    logger.warning(f"Failed to evict '{model_id}': unload returned false")
            except Exception as e:
                logger.error(f"Failed to evict '{model_id}': {e}")
        return freed_gb

    async def _evict_for_space(self, required_gb: float) -> bool:
        """
        Evict LRU models via BackendManager to free space.

        Two-phase eviction:
        1. First evict non-CRITICAL models (LOW → NORMAL → HIGH by LRU)
        2. Last resort: evict CRITICAL models if still not enough space

        Args:
            required_gb: Amount of VRAM needed in GB.

        Returns:
            True if enough space was freed.
        """
        # First, sync registry with backends to discover loaded models
        # This is critical for eviction to work on startup when registry is empty
        await self._sync_registry_from_backends()

        # Phase 1: Evict non-CRITICAL models (LOW → NORMAL → HIGH by LRU)
        non_critical = [
            (mid, m) for mid, m in self._registry.items()
            if m.priority != ModelPriority.CRITICAL
        ]

        # Log eviction candidates
        total_non_critical_gb = sum(m.size_gb for _, m in non_critical)
        logger.info(
            f"Eviction: Need {required_gb:.1f}GB, found {len(non_critical)} non-CRITICAL models "
            f"({total_non_critical_gb:.1f}GB total), registry has {len(self._registry)} models"
        )

        # Sort by priority (LOW first), then by last_accessed (oldest first)
        non_critical.sort(key=lambda x: (x[1].priority.value, x[1].last_accessed), reverse=True)

        freed_gb = await self._evict_models(non_critical, required_gb)
        if freed_gb >= required_gb:
            return True

        # Phase 2: Last resort - evict CRITICAL models
        remaining_needed = required_gb - freed_gb
        critical = [
            (mid, m) for mid, m in self._registry.items()
            if m.priority == ModelPriority.CRITICAL
        ]

        if critical:
            # Sort by LRU (oldest first)
            critical.sort(key=lambda x: x[1].last_accessed)
            logger.warning(
                f"Last resort: Evicting CRITICAL models to free {remaining_needed:.1f}GB "
                f"(found {len(critical)} CRITICAL models)"
            )
            freed_gb += await self._evict_models(critical, remaining_needed)

        return freed_gb >= required_gb

    async def unload_model(self, model_id: str, force: bool = False) -> bool:
        """
        Explicitly unload a model.

        Args:
            model_id: The model identifier to unload.
            force: If True, allows unloading CRITICAL models.

        Returns:
            True if the model was unloaded successfully.
        """
        async with self._lock:
            if model_id not in self._registry:
                logger.warning(f"Model '{model_id}' not in registry, cannot unload")
                return False

            model = self._registry[model_id]

            if model.priority == ModelPriority.CRITICAL and not force:
                logger.warning(f"Use force=True to unload CRITICAL model '{model_id}'")
                return False

            try:
                success = await self._backend_manager.unload_model(model_id)

                if success:
                    del self._registry[model_id]
                    logger.info(f"Unloaded '{model_id}' ({model.size_gb:.1f}GB)")

                return success

            except Exception as e:
                logger.error(f"Failed to unload '{model_id}': {e}")
                return False

    async def sync_backends(self) -> None:
        """
        Reconcile registry with actual backend state.

        Call periodically to handle external unloads (e.g., models
        that expired due to keep_alive timeout) and discover newly
        loaded models.
        """
        async with self._lock:
            await self._sync_registry_from_backends()

    async def get_status(self) -> Dict[str, Any]:
        """
        Get current VRAM status.

        Returns:
            Dictionary containing:
            - used_gb: Current VRAM usage
            - limit_gb: VRAM limit
            - available_gb: Free VRAM
            - loaded_models: List of loaded model info
            - loading: List of models currently being loaded
        """
        return {
            "used_gb": self.current_usage_gb,
            "limit_gb": self._vram_limit_gb,
            "available_gb": self._vram_limit_gb - self.current_usage_gb,
            "loaded_models": [
                {
                    "model_id": m.model_id,
                    "size_gb": m.size_gb,
                    "priority": m.priority.name,
                    "loaded_at": m.loaded_at.isoformat(),
                    "last_accessed": m.last_accessed.isoformat(),
                    "keep_alive_until": m.keep_alive_until.isoformat(),
                }
                for m in self._registry.values()
            ],
            "loading": list(self._loading),
        }

    async def health_check_loop(self) -> None:
        """
        Periodic health check for recovery opportunities.

        This loop:
        1. Asks ProfileManager if we should probe for recovery
        2. If yes, attempts to load a small model from original profile
        3. Reports probe result back to ProfileManager

        Run this as a background task.
        """
        while True:
            await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)

            try:
                # Ask ProfileManager if we should probe for recovery
                if self._profile_manager.should_probe_recovery():
                    # Get LARGEST model from original profile to probe
                    # We need to prove the full profile can work, not just small models
                    original = self._profile_manager.get_original_profile()
                    largest = max(
                        original.available_models,
                        key=lambda m: m.vram_size_gb
                    )

                    logger.info(f"Probing recovery with largest model: '{largest.name}'")

                    try:
                        # Use request_load to go through full VRAM management path
                        # This ensures eviction, registry, and all checks are tested
                        success = await self.request_load(
                            largest.name,
                            keep_alive="1m",  # Short keep_alive for probe
                        )
                        self._profile_manager.record_probe_result(success, largest.name)

                    except Exception as e:
                        logger.warning(f"Recovery probe failed: {e}")
                        self._profile_manager.record_probe_result(False, largest.name)

            except Exception as e:
                logger.error(f"Health check loop error: {e}")

    def get_loaded_models(self) -> Dict[str, LoadedModel]:
        """
        Get all currently loaded models.

        Returns:
            Dictionary mapping model_id to LoadedModel.
        """
        return dict(self._registry)

    async def get_model(
        self,
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        additional_args: Optional[Dict[str, Any]] = None,
    ) -> Union[ExtendedOllamaModel, ExtendedOpenAIModel]:
        """
        Get a Strands-compatible Model for the specified model.

        This is the primary interface for agents and skills to get models.
        It ensures the model is loaded in VRAM and returns a configured
        Strands Model instance (ExtendedOllamaModel or ExtendedOpenAIModel).

        Args:
            model_id: The model identifier (e.g., "magistral:24b").
            temperature: Sampling temperature (default 0.7).
            max_tokens: Maximum tokens to generate (default 4096).
            additional_args: Optional backend-specific options.
                For Ollama: {"think": "high"} enables thinking, None disables.
                For OpenAI-compatible: merged into params.
                If None, auto-resolves from model capabilities.

        Returns:
            ExtendedOllamaModel or ExtendedOpenAIModel configured for the specified model.

        Raises:
            ValueError: If model is not in the current profile.
            MemoryError: If there's not enough VRAM and eviction failed.

        Example:
            # Router (no thinking)
            model = await orchestrator.get_model("gpt-oss:20b", additional_args=None)

            # Agent (with thinking)
            model = await orchestrator.get_model("gpt-oss:70b", additional_args={"think": "high"})
            agent = Agent(model=model, tools=[...])
        """
        # Ensure model is loaded
        await self.request_load(model_id)

        # Get model capabilities for thinking config
        model_caps = self._get_model_capabilities(model_id)
        if not model_caps:
            raise ValueError(f"Model '{model_id}' not found in profile")

        # Resolve additional_args (explicit override or auto from model caps)
        final_args = self._resolve_additional_args(model_caps, additional_args)

        # Get keep_alive from backend options
        keep_alive = "10m"
        if model_caps.backend.options:
            keep_alive = model_caps.backend.options.get("keep_alive", "10m")

        # Create and return the Strands Model via factory
        return self._model_factory.create_model(
            model_id=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            additional_args=final_args,
            keep_alive=keep_alive,
        )

    def _resolve_additional_args(
        self,
        model_caps: ModelCapabilities,
        override_args: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve additional_args from model caps and overrides.

        Priority:
        1. Explicit override from caller (normalized for model format)
        2. Auto-resolve from model capabilities (thinking_format)
        3. Fallback to model.options dict

        Args:
            model_caps: Model capabilities from profile.
            override_args: Explicit override from caller (or None).

        Returns:
            Resolved additional_args dict or None.
        """
        # If caller passed explicit args, normalize for model format
        if override_args is not None:
            return self._normalize_thinking_args(model_caps, override_args)

        # Auto-resolve from model capabilities
        if model_caps.supports_thinking and model_caps.thinking_format:
            if model_caps.thinking_format == "level":
                # gpt-oss models: use string level ('low', 'medium', 'high')
                level = model_caps.default_thinking_level or "medium"
                return {"think": level}
            else:
                # Boolean models (deepseek-r1): use True/False
                return {"think": True}

        # Fallback to options dict
        if model_caps.options:
            think_value = model_caps.options.get("think")
            if think_value is not None:
                return {"think": think_value}

        # No thinking config - return None (model default)
        return None

    def _normalize_thinking_args(
        self,
        model_caps: ModelCapabilities,
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Normalize thinking args for model's expected format.

        Handles conversion between formats:
        - Level-based models (gpt-oss): expect {'think': 'high'/'medium'/'low'}
        - Boolean models (deepseek-r1): expect {'think': True/False}

        Args:
            model_caps: Model capabilities from profile.
            args: Additional args dict from caller.

        Returns:
            Normalized args dict for the model's expected format.
        """
        if "think" not in args or not model_caps.supports_thinking:
            return args

        think_value = args["think"]
        result = dict(args)

        if model_caps.thinking_format == "level":
            # Model expects level string ('low', 'medium', 'high')
            if think_value is True:
                result["think"] = model_caps.default_thinking_level or "medium"
            elif think_value is False:
                del result["think"]  # Disable thinking
            # else: keep the level string as-is (already correct format)
        else:
            # Model expects boolean
            if isinstance(think_value, str):
                result["think"] = True  # Any level string → True
            # else: keep boolean as-is

        return result

    async def get_diffusion_pipeline(self, model_id: str) -> Any:
        """
        Get a diffusion pipeline for image generation.

        Ensures the model is loaded in VRAM and returns the pipeline.
        Only works for models with model_type="diffusion".

        Args:
            model_id: The diffusion model identifier (e.g., "flux2-dev-nvfp4").

        Returns:
            Diffusion pipeline (e.g., Flux2Pipeline).

        Raises:
            ValueError: If model is not in profile or not a diffusion model.
            MemoryError: If there's not enough VRAM and eviction failed.
            RuntimeError: If diffusion backend is not available.

        Example:
            pipe = await orchestrator.get_diffusion_pipeline("flux2-dev-nvfp4")
            image = pipe(prompt="A cat", num_inference_steps=28).images[0]
        """
        # Validate model is in profile
        model_caps = self._get_model_capabilities(model_id)
        if not model_caps:
            raise ValueError(f"Model '{model_id}' not in profile '{self._profile.profile_name}'")

        # Validate model is diffusion type
        if model_caps.model_type != "diffusion":
            raise ValueError(
                f"Model '{model_id}' is not a diffusion model "
                f"(model_type='{model_caps.model_type}')"
            )

        # Ensure model is loaded (handles eviction)
        await self.request_load(model_id)

        # Get pipeline from DiffusionClient
        diffusion_client = self._backend_manager.get_client("diffusion")
        if not diffusion_client:
            raise RuntimeError("Diffusion backend not configured")

        if not hasattr(diffusion_client, 'get_pipeline'):
            raise RuntimeError("Diffusion client does not support get_pipeline()")

        pipeline = diffusion_client.get_pipeline(model_id)
        if pipeline is None:
            raise RuntimeError(f"Pipeline for '{model_id}' not found after loading")

        return pipeline

    def get_diffusion_client(self, model_id: str) -> Any:
        """
        Get ComfyUI client for diffusion model image generation.

        Used for NVFP4 models that run via ComfyUI backend instead of
        in-process diffusers. Returns the ComfyUIClient for direct HTTP
        communication with the ComfyUI server.

        Args:
            model_id: Diffusion model identifier (e.g., "flux2-dev-nvfp4").

        Returns:
            ComfyUIClient instance for image generation.

        Raises:
            ValueError: If model not in profile or not a diffusion model.
            RuntimeError: If ComfyUI backend not configured.

        Example:
            comfyui = orchestrator.get_diffusion_client("flux2-dev-nvfp4")
            image_bytes = await comfyui.generate_image(
                prompt="A cat",
                width=1024,
                height=1024,
                steps=28,
            )
        """
        # Validate model is in profile
        model_caps = self._get_model_capabilities(model_id)
        if not model_caps:
            raise ValueError(f"Model '{model_id}' not in profile '{self._profile.profile_name}'")

        # Validate model is diffusion type
        if model_caps.model_type != "diffusion":
            raise ValueError(
                f"Model '{model_id}' is not a diffusion model "
                f"(model_type='{model_caps.model_type}')"
            )

        # Get ComfyUI client from backend manager
        comfyui_client = self._backend_manager.get_client("comfyui")
        if not comfyui_client:
            raise RuntimeError("ComfyUI backend not configured")

        return comfyui_client

    async def get_diffusion_context(self, model_id: str) -> Tuple[Any, Dict[str, Any]]:
        """
        Get ComfyUI client and workflow config for diffusion model.

        Ensures VRAM is available by calling request_load(), which may evict
        LLMs if needed. The diffusion model is registered in the registry
        for future eviction when LLMs need to load.

        Returns both the client and the model-specific workflow configuration
        from ModelCapabilities.options. This follows DIP by keeping model
        configuration in the profile rather than hardcoded in the client.

        Args:
            model_id: Diffusion model identifier (e.g., "flux2-dev-nvfp4").

        Returns:
            Tuple of (ComfyUIClient, workflow_config dict).

        Raises:
            ValueError: If model not in profile or not a diffusion model.
            RuntimeError: If ComfyUI backend not configured.
            MemoryError: If there's not enough VRAM and eviction failed.

        Example:
            comfyui, workflow_config = await orchestrator.get_diffusion_context("flux2-dev-nvfp4")
            image_bytes = await comfyui.generate_image(
                prompt="A cat",
                width=1024,
                height=1024,
                steps=28,
                workflow_config=workflow_config,
            )
        """
        # Validate model is in profile
        model_caps = self._get_model_capabilities(model_id)
        if not model_caps:
            raise ValueError(f"Model '{model_id}' not in profile '{self._profile.profile_name}'")

        # Validate model is diffusion type
        if model_caps.model_type != "diffusion":
            raise ValueError(
                f"Model '{model_id}' is not a diffusion model "
                f"(model_type='{model_caps.model_type}')"
            )

        # Request VRAM, evict LLMs if needed
        # This registers the model in the registry for future eviction
        success = await self.request_load(model_id)
        if not success:
            raise MemoryError(f"Failed to load diffusion model '{model_id}' - VRAM unavailable")

        # Get ComfyUI client from backend manager
        comfyui_client = self._backend_manager.get_client("comfyui")
        if not comfyui_client:
            raise RuntimeError("ComfyUI backend not configured")

        # Get workflow config from model options
        workflow_config = dict(model_caps.options.get("workflow", {}))

        # Add model_id for tracking (used by generate_image for logging)
        workflow_config["model_id"] = model_id

        return comfyui_client, workflow_config

    async def warmup_diffusion_model(self, model_id: Optional[str] = None) -> bool:
        """
        Pre-load diffusion model into VRAM by triggering a warmup workflow.

        Calls request_load() via get_diffusion_context() to ensure VRAM is
        available (evicting LLMs if needed). Then submits a tiny 64x64 image
        to trigger actual model loading in ComfyUI.

        Args:
            model_id: Diffusion model ID. If None, uses profile's default image model.

        Returns:
            True if warmup succeeded, False otherwise.

        Example:
            # Warmup default image model from profile
            success = await orchestrator.warmup_diffusion_model()

            # Warmup specific model
            success = await orchestrator.warmup_diffusion_model("flux2-dev-nvfp4")
        """
        try:
            # Use default image model if not specified
            if model_id is None:
                model_id = self.get_profile_model("image")

            # Get client and workflow config (now async, calls request_load)
            comfyui, workflow_config = await self.get_diffusion_context(model_id)
            if not comfyui:
                logger.warning(f"No ComfyUI client for model '{model_id}'")
                return False

            # Delegate to ComfyUIClient.warmup()
            success = await comfyui.warmup(workflow_config)
            if success:
                logger.info(f"Diffusion model warmup complete ({model_id})")
            else:
                logger.warning(f"Diffusion model warmup failed ({model_id})")
            return success

        except Exception as e:
            logger.warning(f"Diffusion model warmup skipped: {e}")
            return False
