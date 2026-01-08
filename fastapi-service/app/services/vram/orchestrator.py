"""VRAM Orchestrator - Lightweight coordinator (Dependency Injection)."""
import asyncio
from typing import Optional, Dict, Any

from app.services.vram.interfaces import BackendType, ModelPriority
from app.services.vram.model_registry import ModelRegistry
from app.services.vram.interfaces import IMemoryMonitor, IEvictionStrategy, IBackendManager
from app.config import settings, get_model_capabilities
import logging_client

logger = logging_client.setup_logger('vram_orchestrator')


class VRAMOrchestrator:
    """
    Lightweight coordinator for VRAM management.

    Single Responsibility: Coordinate model load requests.
    Dependencies injected (Dependency Inversion Principle).
    Includes circuit breaker pattern to prevent crash loops.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        memory_monitor: IMemoryMonitor,
        eviction_strategy: IEvictionStrategy,
        backend_manager: IBackendManager,
        crash_tracker = None,  # Optional CrashTracker instance
        soft_limit_gb: float = 100.0,
        hard_limit_gb: float = 110.0
    ):
        self._registry = registry
        self._memory_monitor = memory_monitor
        self._eviction_strategy = eviction_strategy
        self._backend_manager = backend_manager
        self._crash_tracker = crash_tracker
        self._lock = asyncio.Lock()
        self._soft_limit_gb = soft_limit_gb
        self._hard_limit_gb = hard_limit_gb

    def update_limits(self, soft_limit_gb: float, hard_limit_gb: float) -> None:
        """
        Update VRAM limits at runtime.

        Called by switch_profile() when profile changes (e.g., circuit breaker fallback).
        Ensures orchestrator limits stay in sync with active profile.

        Args:
            soft_limit_gb: New soft limit
            hard_limit_gb: New hard limit
        """
        old_soft = self._soft_limit_gb
        old_hard = self._hard_limit_gb
        self._soft_limit_gb = soft_limit_gb
        self._hard_limit_gb = hard_limit_gb
        logger.info(
            f"🔄 VRAM limits updated: "
            f"soft={old_soft:.0f}GB→{soft_limit_gb:.0f}GB, "
            f"hard={old_hard:.0f}GB→{hard_limit_gb:.0f}GB"
        )

    async def request_model_load(
        self,
        model_id: str,
        temperature: float = 0.7,
        additional_args: Optional[Dict] = None
    ) -> None:
        """Coordinate model load with memory management."""
        async with self._lock:
            # 1. Check if already loaded
            if self._registry.is_loaded(model_id):
                model = self._registry.get(model_id)
                if model.is_external:
                    logger.debug(f"♻️  {model_id} is external (pre-loaded), skipping orchestration")
                    self._registry.update_access(model_id)
                    return
                logger.debug(f"♻️  {model_id} already loaded")
                self._registry.update_access(model_id)
                return

            # 2. Get model capabilities
            model_caps = get_model_capabilities(model_id)
            if not model_caps:
                raise ValueError(f"Model {model_id} not in config")

            required_gb = getattr(model_caps, 'vram_size_gb', 20.0)
            backend_type = BackendType(model_caps.backend.type)

            # Get priority from model caps or default to NORMAL
            priority_str = getattr(model_caps, 'priority', 'NORMAL').upper()
            try:
                priority = ModelPriority[priority_str]
            except KeyError:
                priority = ModelPriority.NORMAL
                logger.warning(f"⚠️  Unknown priority '{priority_str}', using NORMAL")

            # 2.5. Circuit breaker: Check crash history
            if settings.VRAM_CIRCUIT_BREAKER_ENABLED and self._crash_tracker:
                crash_status = self._crash_tracker.check_crash_history(model_id)

                if crash_status['needs_protection']:
                    logger.warning(
                        f"🔄 Circuit breaker triggered for {model_id}: "
                        f"{crash_status['crash_count']} crashes in last {settings.VRAM_CRASH_WINDOW_SECONDS}s. "
                        f"Proactively evicting LRU models for extra headroom..."
                    )

                    # Proactive eviction: Create extra headroom by evicting LRU models
                    # Target: Ensure we have model_size + buffer_gb free
                    buffer_gb = settings.VRAM_CIRCUIT_BREAKER_BUFFER_GB
                    target_free_gb = required_gb + buffer_gb

                    mem_status_check = await self._memory_monitor.get_status()
                    current_free = mem_status_check.available_gb

                    if current_free < target_free_gb:
                        need_to_free = target_free_gb - current_free
                        logger.info(
                            f"📤 Circuit breaker: Need to free {need_to_free:.1f}GB "
                            f"(current: {current_free:.1f}GB, target: {target_free_gb:.1f}GB)"
                        )

                        # Evict LRU models until we have enough space
                        # Prioritize LOW/NORMAL models (same as emergency eviction)
                        evicted_count = 0
                        freed_gb = 0.0

                        # Get all evictable models (LOW/NORMAL priority, sorted by LRU)
                        evictable = [
                            (mid, m) for mid, m in self._registry.get_all().items()
                            if m.priority.value >= ModelPriority.NORMAL.value  # LOW=4, NORMAL=3
                        ]
                        evictable.sort(key=lambda x: x[1].last_accessed)  # LRU first

                        for victim_id, victim in evictable:
                            if freed_gb >= need_to_free:
                                break

                            try:
                                await self._backend_manager.unload(victim_id, victim.backend)
                                self._registry.unregister(victim_id)
                                freed_gb += victim.size_gb
                                evicted_count += 1
                                logger.info(
                                    f"✅ Circuit breaker evicted {victim_id} "
                                    f"({victim.size_gb:.1f}GB, freed: {freed_gb:.1f}GB)"
                                )
                            except Exception as e:
                                logger.error(f"❌ Circuit breaker eviction failed for {victim_id}: {e}")

                        if freed_gb < need_to_free:
                            # Failed to free enough space - block the load
                            wait_seconds = int(settings.VRAM_CRASH_WINDOW_SECONDS - crash_status['last_crash_seconds_ago'])
                            raise MemoryError(
                                f"Circuit breaker: Cannot load {model_id} safely. "
                                f"Model has crashed {crash_status['crash_count']} times recently. "
                                f"No evictable models available to create safety buffer. "
                                f"Please wait {wait_seconds}s or free memory manually."
                            )

                        logger.info(
                            f"✅ Circuit breaker: Freed {freed_gb:.1f}GB by evicting {evicted_count} models. "
                            f"Loading {model_id} with extra headroom..."
                        )

            # 3. Check memory
            mem_status = await self._memory_monitor.get_status()
            headroom_gb = self._hard_limit_gb - mem_status.model_usage_gb
            logger.info(
                f"📊 Loading {model_id}: {required_gb:.1f}GB needed, "
                f"{mem_status.model_usage_gb:.1f}GB used, "
                f"{headroom_gb:.1f}GB headroom (limit: {self._hard_limit_gb:.0f}GB)"
            )

            # 4. Flush cache if large model (>70GB as per research)
            # Skip for external backends (SGLang) - they're pre-loaded on host
            is_external_backend = model_caps and model_caps.backend.type in ("sglang",)

            if required_gb > 70.0 and not is_external_backend:
                logger.info(f"💾 Large model detected ({required_gb:.1f}GB), flushing buffer cache")
                await self._memory_monitor.flush_cache()
            elif is_external_backend:
                logger.debug(f"⏭️  Skipping cache flush for external model {model_id}")

            # 5. Evict if needed
            # CRITICAL: Only count manageable models against limits (exclude external models like SGLang)
            current_usage = self._registry.get_total_usage_gb()
            manageable_usage = self._registry.get_manageable_vram_usage()
            projected_usage = manageable_usage + required_gb  # Use manageable, not total

            logger.debug(
                f"VRAM usage: {manageable_usage:.1f}GB manageable "
                f"({current_usage:.1f}GB total including external), "
                f"projected: {projected_usage:.1f}GB with {model_id}"
            )

            # Compare manageable usage against limits (external models don't count)
            if projected_usage > self._hard_limit_gb:
                logger.warning(
                    f"⚠️  Projected usage {projected_usage:.1f}GB exceeds hard limit {self._hard_limit_gb:.1f}GB"
                )

                victims = self._eviction_strategy.select_victims(
                    self._registry.get_all(),
                    required_gb,
                    manageable_usage,  # Use manageable usage, not total
                    self._hard_limit_gb
                )

                if not victims:
                    raise MemoryError(
                        f"Cannot free enough memory for {model_id} ({required_gb:.1f}GB). "
                        f"All models are protected or insufficient space."
                    )

                for victim_id in victims:
                    victim = self._registry.get(victim_id)
                    logger.info(f"📤 Evicting {victim_id} ({victim.size_gb:.1f}GB, backend={victim.backend.value})")

                    try:
                        await self._backend_manager.unload(victim_id, victim.backend)
                        self._registry.unregister(victim_id)
                        logger.info(f"✅ Successfully evicted {victim_id}")
                    except Exception as e:
                        logger.error(f"❌ Failed to evict {victim_id}: {e}")
                        # Continue with next victim

            # 6. Register model
            self._registry.register(model_id, backend_type, required_gb, priority)
            logger.info(
                f"✅ Registered {model_id} in VRAM orchestrator "
                f"(size={required_gb:.1f}GB, priority={priority.name})"
            )

    async def mark_model_accessed(self, model_id: str) -> None:
        """Update LRU timestamp for model."""
        self._registry.update_access(model_id)
        logger.debug(f"🔄 Updated LRU for {model_id}")

    async def mark_model_unloaded(
        self,
        model_id: str,
        crashed: bool = False,
        crash_reason: str = "generation_failure"
    ) -> None:
        """
        Mark model as unloaded.

        Args:
            model_id: Model to unload
            crashed: Whether model crashed (True) or was gracefully unloaded (False)
            crash_reason: Reason for crash (e.g., "sglang_connection_error", "generation_failure")
        """
        if self._registry.is_loaded(model_id):
            model = self._registry.get(model_id)

            # Skip unload for external models (pre-loaded, not managed by orchestrator)
            if model.is_external:
                logger.warning(
                    f"⏭️  Skipping unload for external model {model_id} "
                    f"(backend={model.backend.value}, is_external=True). "
                    f"External models are pre-loaded and managed by their host server."
                )
                # Still unregister from tracking (crash recording works)
                self._registry.unregister(model_id)
            else:
                # Manageable model - proceed with unload
                await self._backend_manager.unload(model_id, model.backend)
                self._registry.unregister(model_id)

            logger.info(f"✅ Marked {model_id} as unloaded (crashed={crashed})")
        else:
            logger.warning(f"⚠️  Model {model_id} not tracked as loaded (recording crash anyway)")

        # Record crash AFTER registry updates (works even if model not tracked)
        # This ensures circuit breaker gets notified for repeated connection errors
        if crashed and settings.VRAM_CIRCUIT_BREAKER_ENABLED and self._crash_tracker:
            self._crash_tracker.record_crash(model_id, reason=crash_reason)
            logger.warning(f"⚠️  Recorded crash for {model_id} in circuit breaker (reason: {crash_reason})")

    async def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status."""
        mem_status = await self._memory_monitor.get_status()

        # Calculate usage percentage using ONLY manageable models (exclude external)
        total_model_usage_gb = self._registry.get_total_usage_gb()
        manageable_usage_gb = self._registry.get_manageable_vram_usage()
        usage_pct = (manageable_usage_gb / self._hard_limit_gb * 100) if self._hard_limit_gb > 0 else 0

        # Get crash statistics if circuit breaker enabled
        crash_stats = []
        if settings.VRAM_CIRCUIT_BREAKER_ENABLED and self._crash_tracker:
            models_with_crashes = self._crash_tracker.get_all_models_with_crashes()
            for model_id in models_with_crashes:
                stats = self._crash_tracker.get_crash_stats(model_id)
                crash_stats.append({
                    "model_id": model_id,
                    "crash_count": stats['crash_count'],
                    "last_crash_ago_seconds": stats['last_crash_seconds_ago']
                })

        status = {
            "memory": {
                "total_gb": mem_status.total_gb,
                "used_gb": mem_status.used_gb,
                "available_gb": mem_status.available_gb,
                "model_usage_gb": mem_status.model_usage_gb,
                "total_model_vram_gb": total_model_usage_gb,  # All models (including external)
                "manageable_vram_gb": manageable_usage_gb,  # Only manageable models (excludes external)
                "soft_limit_gb": self._soft_limit_gb,
                "hard_limit_gb": self._hard_limit_gb,
                "usage_pct": usage_pct,  # Based on manageable VRAM only
                "psi_some_avg10": mem_status.psi_pressure.get('some_avg10', 0.0),
                "psi_full_avg10": mem_status.psi_pressure.get('full_avg10', 0.0)
            },
            "loaded_models": [
                {
                    "model_id": m.model_id,
                    "backend": m.backend.value,
                    "size_gb": m.size_gb,
                    "priority": m.priority.name,
                    "is_external": m.is_external,  # Show if pre-loaded external model
                    "loaded_at": m.loaded_at.isoformat(),
                    "last_accessed": m.last_accessed.isoformat()
                }
                for m in self._registry.get_all().values()
            ]
        }

        # Add crash tracker statistics if available
        if crash_stats:
            status["crash_tracker"] = {
                "models_with_crashes": crash_stats
            }

        return status

    async def flush_buffer_cache(self) -> None:
        """Manually flush buffer cache."""
        await self._memory_monitor.flush_cache()

    async def reconcile_registry(self) -> Dict[str, int]:
        """
        Reconcile registry with actual backend state.

        Detects and fixes desyncs caused by:
        - earlyoom killing models
        - Manual kills (SIGTERM, SIGKILL)
        - Ollama crashes
        - Other external failures

        Returns:
            Dict with reconciliation statistics: {
                'registry_count': int,
                'backend_count': int,
                'cleaned_count': int,
                'cleaned_models': list[str]
            }
        """
        # Only reconcile Ollama for now (other backends TODO)
        from app.services.vram.backend_managers import OllamaBackendManager

        ollama_manager = OllamaBackendManager()
        actually_loaded = ollama_manager.get_loaded_models()

        # Get what registry thinks is loaded (Ollama only)
        registry_models = {
            model_id: model
            for model_id, model in self._registry.get_all().items()
            if model.backend == BackendType.OLLAMA
        }

        # Find desyncs (in registry but not actually loaded)
        cleaned = []
        for model_id, model in registry_models.items():
            if model_id not in actually_loaded:
                logger.warning(
                    f"⚠️  Registry desync detected: {model_id} ({model.size_gb}GB) "
                    f"in registry but not in Ollama - cleaning up"
                )
                self._registry.unregister(model_id)
                cleaned.append(model_id)

        stats = {
            'registry_count': len(registry_models),
            'backend_count': len(actually_loaded),
            'cleaned_count': len(cleaned),
            'cleaned_models': cleaned
        }

        if cleaned:
            logger.info(
                f"🔄 Registry reconciliation: cleaned {len(cleaned)} desynced models "
                f"(registry: {stats['registry_count']}, actual: {stats['backend_count']})"
            )
        else:
            # No stale entries, but registry may not track all backend models (by design)
            if stats['registry_count'] == stats['backend_count']:
                logger.debug(
                    f"✅ Registry in sync (registry: {stats['registry_count']}, "
                    f"actual: {stats['backend_count']})"
                )
            else:
                untracked = stats['backend_count'] - stats['registry_count']
                logger.debug(
                    f"✅ No stale registry entries (registry: {stats['registry_count']}, "
                    f"actual: {stats['backend_count']}, {untracked} untracked backend models)"
                )

        return stats

    async def emergency_evict_lru(self, max_priority: ModelPriority = ModelPriority.LOW) -> Dict[str, Any]:
        """
        Emergency eviction triggered by high PSI.

        Evicts the least recently used model up to the specified priority level.
        Used to prevent earlyoom from killing models unpredictably.

        Args:
            max_priority: Maximum priority level to evict (default: LOW)
                         LOW = only evict LOW priority models
                         NORMAL = evict LOW and NORMAL priority models
                         HIGH = evict LOW, NORMAL, and HIGH (but not CRITICAL)

        Returns:
            Dict with eviction results: {
                'evicted': bool,
                'model_id': str or None,
                'size_gb': float,
                'reason': str
            }
        """
        async with self._lock:
            # Get all loaded models up to max_priority (sorted by LRU)
            candidates = [
                (model_id, model)
                for model_id, model in self._registry.get_all().items()
                if model.priority.value >= max_priority.value and model.priority != ModelPriority.CRITICAL
            ]

            if not candidates:
                logger.warning(
                    f"⚠️  Emergency eviction requested (max_priority={max_priority.name}) "
                    f"but no eligible models to evict"
                )
                return {
                    'evicted': False,
                    'model_id': None,
                    'size_gb': 0.0,
                    'reason': 'no_eligible_models'
                }

            # Sort by last_accessed (oldest first = LRU)
            candidates.sort(key=lambda x: x[1].last_accessed)

            # Evict the least recently used
            victim_id, victim = candidates[0]

            logger.warning(
                f"🚨 Emergency PSI eviction: {victim_id} "
                f"({victim.size_gb}GB, {victim.priority.name}, "
                f"last_accessed={victim.last_accessed.isoformat()})"
            )

            try:
                await self._backend_manager.unload(victim_id, victim.backend)
                self._registry.unregister(victim_id)

                return {
                    'evicted': True,
                    'model_id': victim_id,
                    'size_gb': victim.size_gb,
                    'reason': 'psi_emergency'
                }

            except Exception as e:
                logger.error(f"❌ Emergency eviction failed: {e}")
                return {
                    'evicted': False,
                    'model_id': victim_id,
                    'size_gb': 0.0,
                    'reason': f'eviction_failed: {e}'
                }
