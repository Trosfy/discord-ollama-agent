"""Main FastAPI application entry point."""
import sys
sys.path.insert(0, '/shared')

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
import os

from app.config import settings

# Import logging client
import logging_client
import init_dynamodb

# Initialize logger
logger = logging_client.setup_logger('fastapi')

# ============================================================================
# Load Configuration Profile (MUST happen before other imports use settings)
# ============================================================================
try:
    from app.config.profiles.factory import ProfileFactory
    from app.config import set_active_profile

    profile_name = settings.VRAM_PROFILE
    logger.info(f"🎯 Loading configuration profile: {profile_name}")

    profile = ProfileFactory.load_profile(profile_name)
    set_active_profile(profile)

    logger.info(f"✅ Active profile: {profile_name}")
    logger.info(f"   Available models: {len(profile.available_models)}")
    logger.info(f"   VRAM hard limit: {profile.vram_hard_limit_gb}GB")
    logger.info(f"   VRAM soft limit: {profile.vram_soft_limit_gb}GB")

    # Log model roster for debugging
    for model in profile.available_models:
        logger.info(
            f"   - {model.name} "
            f"({model.vram_size_gb}GB, priority={model.priority})"
        )

except Exception as e:
    logger.error(f"❌ Failed to load configuration profile: {e}")
    logger.error(f"   Make sure VRAM_PROFILE env var is set correctly")
    raise

# Continue with normal imports (now safe to use settings.ROUTER_MODEL, etc.)
from app.api import websocket, discord, admin, user, internal, monitoring, chat_ws, files
from app.dependencies import (
    get_storage,
    get_queue,
    get_llm,
    get_websocket_manager,
    get_orchestrator,
    get_queue_worker
)
from app.utils.health_checks import (
    check_dynamodb,
    check_ollama,
    check_ollama_model_loaded,
    check_vram_status
)


async def background_vram_monitor():
    """
    Background task to monitor VRAM and PSI.

    Features:
    - Logs warnings when approaching limits or under memory pressure
    - Reconciles registry with backend every 30 seconds to detect desyncs
    - Proactively evicts models when PSI is high (prevents earlyoom kills)

    From research: PSI provides early warning before OOM.
    """
    logger.info(
        "🔍 Starting background VRAM monitor "
        "(reconciliation + proactive PSI eviction enabled)"
    )

    from app.services.vram import get_orchestrator
    from app.services.vram.interfaces import ModelPriority

    while True:
        try:
            status = await check_vram_status()
            psi_full_avg10 = status.get('psi_full_avg10', 0.0)

            # Proactive PSI-based eviction (PREVENTS earlyoom kills)
            if psi_full_avg10 > settings.VRAM_PSI_CRITICAL_THRESHOLD:
                # Critical PSI - evict NORMAL priority models
                logger.critical(
                    f"🚨 CRITICAL PSI ({psi_full_avg10:.1f}%) - "
                    f"triggering emergency eviction (NORMAL priority)"
                )
                try:
                    orchestrator = get_orchestrator()
                    result = await orchestrator.emergency_evict_lru(ModelPriority.NORMAL)

                    if result['evicted']:
                        logger.warning(
                            f"🔄 Emergency eviction: {result['model_id']} "
                            f"({result['size_gb']}GB) freed to prevent earlyoom kill"
                        )
                    else:
                        logger.error(
                            f"❌ Emergency eviction failed: {result['reason']}"
                        )
                except Exception as e:
                    logger.error(f"❌ Emergency eviction error: {e}")

            elif psi_full_avg10 > settings.VRAM_PSI_WARNING_THRESHOLD:
                # Warning PSI - evict LOW priority models only
                logger.warning(
                    f"⚠️  WARNING PSI ({psi_full_avg10:.1f}%) - "
                    f"triggering emergency eviction (LOW priority)"
                )
                try:
                    orchestrator = get_orchestrator()
                    result = await orchestrator.emergency_evict_lru(ModelPriority.LOW)

                    if result['evicted']:
                        logger.info(
                            f"🔄 Emergency eviction: {result['model_id']} "
                            f"({result['size_gb']}GB) freed"
                        )
                    else:
                        logger.debug(f"No LOW priority models to evict")
                except Exception as e:
                    logger.error(f"❌ Emergency eviction error: {e}")

            # Log health status
            if not status['healthy']:
                if status.get('error'):
                    logger.error(f"❌ VRAM health check failed: {status['error']}")
                else:
                    logger.warning(
                        f"⚠️  VRAM health degraded: "
                        f"{status['usage_pct']:.1f}% usage, "
                        f"PSI some={status['psi_some_avg10']:.1f}%, "
                        f"PSI full={psi_full_avg10:.1f}%"
                    )

            elif status.get('warning'):
                logger.info(
                    f"⚠️  VRAM warning: "
                    f"{status['usage_pct']:.1f}% usage, "
                    f"{status['loaded_models']} models loaded"
                )

            # Reconcile registry every 30 seconds (EVERY iteration)
            try:
                orchestrator = get_orchestrator()
                reconcile_stats = await orchestrator.reconcile_registry()

                if reconcile_stats['cleaned_count'] > 0:
                    logger.warning(
                        f"🔄 Registry reconciliation: "
                        f"cleaned {reconcile_stats['cleaned_count']} desynced models "
                        f"({', '.join(reconcile_stats['cleaned_models'])})"
                    )
            except Exception as e:
                logger.error(f"❌ Registry reconciliation failed: {e}")

            # Check every 30 seconds (HEALTH_CHECK_INTERVAL)
            await asyncio.sleep(settings.HEALTH_CHECK_INTERVAL)

        except asyncio.CancelledError:
            logger.info("🛑 VRAM monitor stopped")
            raise
        except Exception as e:
            logger.error(f"❌ VRAM monitor error: {e}")
            await asyncio.sleep(settings.HEALTH_CHECK_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with VRAM monitoring."""
    logger.info("Starting Discord-Trollama Agent...")

    # Initialize DynamoDB tables (centralized)
    logger.info("Initializing DynamoDB tables...")
    try:
        tables_created = await init_dynamodb.initialize_all_tables()
        if tables_created:
            logger.info(f"Created tables: {', '.join(tables_created)}")
        else:
            logger.info("All tables already exist")
    except Exception as e:
        logger.error(f"Failed to initialize DynamoDB tables: {e}")
        raise

    # Initialize queue
    queue = get_queue()
    await queue.start()
    logger.info("Queue started")

    # Start queue worker
    worker = get_queue_worker()
    await worker.start()
    logger.info("Queue worker started")

    # Pre-register external models (SGLang) if orchestrator enabled
    if settings.VRAM_ENABLE_ORCHESTRATOR:
        from app.services.vram import get_orchestrator as get_vram_orchestrator
        from app.config import get_active_profile

        orchestrator = get_vram_orchestrator()
        profile = get_active_profile()

        sglang_models = [m for m in profile.available_models if m.backend.type == "sglang"]

        if sglang_models:
            logger.info(f"🔍 Performance profile detected - pre-registering {len(sglang_models)} SGLang models")

            from app.services.vram.backend_managers import SGLangBackendManager
            from app.services.vram.interfaces import BackendType, ModelPriority

            sglang_manager = SGLangBackendManager()

            try:
                # Query SGLang server for actually loaded models
                loaded_models = sglang_manager.get_loaded_models()

                if not loaded_models:
                    raise RuntimeError("SGLang server returned no loaded models - is it running correctly?")

                logger.info(f"🔍 SGLang reports {len(loaded_models)} models loaded: {loaded_models}")

                for model_caps in sglang_models:
                    model_name = model_caps.name

                    # Handle name mapping (validate at startup)
                    sglang_model_name = model_name
                    # DEPRECATED: Eagle3 model (SGLang not in use)
                    # if model_name == "gpt-oss-120b-eagle3":
                    #     sglang_model_name = "openai/gpt-oss-120b"
                    #     logger.info(f"📋 Model name mapping: {model_name} → {sglang_model_name}")

                    if sglang_model_name in loaded_models:
                        priority = ModelPriority[model_caps.priority.upper()]

                        orchestrator._registry.register(
                            model_id=model_name,  # Profile name
                            backend=BackendType.SGLANG,
                            size_gb=model_caps.vram_size_gb,
                            priority=priority,
                            is_external=True  # Mark as external
                        )

                        logger.info(
                            f"✅ Pre-registered external SGLang model: {model_name} "
                            f"({model_caps.vram_size_gb}GB, priority={priority.name}, is_external=True)"
                        )
                    else:
                        logger.warning(
                            f"⚠️  SGLang model {model_name} configured but not loaded. "
                            f"Expected: {sglang_model_name}, Got: {loaded_models}"
                        )

            except Exception as e:
                logger.error(f"❌ Failed to pre-register SGLang models: {e}")
                logger.warning(
                    "🚨 SGLang server is not reachable or not functioning correctly. "
                    "Performance profile requires SGLang, but it's unavailable."
                )
                logger.warning(
                    "⚠️  DEGRADING TO CONSERVATIVE PROFILE (12GB budget, 5 small models)"
                )
                logger.warning(
                    "   Reason: If SGLang stuck at 84GB, only ~30GB RAM available - "
                    "not enough for balanced (100GB+), but enough for conservative (12GB)"
                )
                logger.warning("   To restore performance profile:")
                logger.warning("   1. Check SGLang: docker logs trollama-sglang")
                logger.warning("   2. Restart SGLang: ./scripts/model_management/stop_sglang.sh && ./scripts/model_management/start_sglang.sh")
                logger.warning("   3. Restart FastAPI: docker compose restart fastapi-service")

                # GRACEFUL DEGRADATION: Load conservative profile instead
                from app.config import set_active_profile
                from app.config.profiles.conservative import ConservativeProfile
                logger.warning("🔄 Loading ConservativeProfile as fallback...")

                # Switch active profile (updates global _active_profile)
                original_profile_name = profile.profile_name if profile else profile_name
                set_active_profile(ConservativeProfile())
                settings.VRAM_PROFILE = "conservative"  # Update env var for consistency

                logger.warning("✅ Degraded to conservative profile successfully")

                # IMPORTANT: Notify ProfileManager about startup degradation
                # This allows ProfileManager to check for recovery on subsequent requests
                from app.dependencies import get_profile_manager
                profile_manager = get_profile_manager()
                logger.info(f"📝 Setting ProfileManager fallback state: fallback_active=True, original_profile={original_profile_name}")
                profile_manager._fallback_active = True
                profile_manager._original_profile_name = original_profile_name
                logger.info(
                    f"✅ ProfileManager notified of startup fallback "
                    f"({original_profile_name} → conservative) - "
                    f"State verified: fallback_active={profile_manager._fallback_active}, "
                    f"original={profile_manager._original_profile_name}"
                )

                # Don't raise - continue with conservative profile

    # Start background VRAM monitoring
    monitor_task = None
    if settings.VRAM_ENABLE_ORCHESTRATOR:
        monitor_task = asyncio.create_task(background_vram_monitor())
        logger.info("✅ Background VRAM monitor started")

    # Health checks
    db_ok = await check_dynamodb()
    ollama_ok = await check_ollama()

    # Check profile's router model (not hardcoded default)
    profile = get_active_profile()
    router_model = profile.router_model

    # Determine if router model is external (SGLang, TensorRT, etc.)
    from app.config import get_model_capabilities
    model_caps = get_model_capabilities(router_model)
    is_external = model_caps and model_caps.backend.type not in ("ollama",)

    if is_external:
        # For external models, check VRAM orchestrator registry instead of Ollama
        if settings.VRAM_ENABLE_ORCHESTRATOR:
            from app.services.vram import get_orchestrator as get_vram_orchestrator
            orchestrator = get_vram_orchestrator()
            model_ok = orchestrator._registry.is_loaded(router_model)
        else:
            model_ok = False  # Can't verify without orchestrator
    else:
        # For Ollama models, check Ollama API
        model_ok = await check_ollama_model_loaded(router_model)

    if db_ok:
        logger.info("DynamoDB: OK")
    else:
        logger.error("DynamoDB: FAIL")

    if ollama_ok:
        logger.info("Ollama: OK")
    else:
        logger.error("Ollama: FAIL")

    if model_ok:
        backend_type = model_caps.backend.type if model_caps else "unknown"
        logger.info(f"Model ({router_model}): Loaded (backend={backend_type})")
    else:
        logger.warning(f"Model ({router_model}): Not loaded")

    if not all([db_ok, ollama_ok]):
        logger.warning("Some services unavailable, but starting anyway...")

    logger.info(f"FastAPI service ready on {settings.HOST}:{settings.PORT}")

    yield

    # Shutdown
    logger.info("Shutting down...")
    if monitor_task:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
    await worker.stop()
    await queue.stop()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# ============================================================================
# CORS Configuration - Allow Next.js frontend (web-service)
# ============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8502",  # Next.js dev (external port)
        "http://localhost:3000",  # Next.js dev (internal port)
        "http://web-service:3000",  # Docker (internal)
        "https://dgx-spark.netbird.cloud",  # Production deployment
        "https://dgx-spark.netbird.cloud:8502",  # Production deployment (explicit port)
        os.getenv("WEB_SERVICE_URL", ""),  # Additional origin from env
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(websocket.router, tags=["websocket"])
app.include_router(discord.router, prefix="/api/discord", tags=["discord"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(user.router, prefix="/api/user", tags=["user"])
app.include_router(internal.router, prefix="/internal", tags=["internal"])
app.include_router(monitoring.router, prefix="/api", tags=["monitoring"])  # SSE monitoring
app.include_router(chat_ws.router, tags=["chat_websocket"])  # WebSocket chat streaming
app.include_router(files.router, prefix="/api/files", tags=["files"])  # File upload


@app.get("/health")
async def health_check():
    """Enhanced health check endpoint with VRAM monitoring."""
    vram = await check_vram_status()

    return {
        "status": "healthy" if vram.get('healthy', False) else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "dynamodb": await check_dynamodb(),
            "ollama": await check_ollama(),
            "model_loaded": await check_ollama_model_loaded(),
        },
        "vram": vram,
        "queue_size": get_queue().size(),
        "websocket_connections": get_websocket_manager().count_connections(),
        "maintenance_mode": settings.MAINTENANCE_MODE,
        "maintenance_mode_hard": settings.MAINTENANCE_MODE_HARD
    }


@app.get("/")
async def root():
    """Root endpoint with API documentation."""
    return {
        "message": "Discord-Trollama Agent API",
        "version": settings.VERSION,
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "vram": {
                "status": "/vram/status",
                "health": "/vram/health",
                "psi": "/vram/psi",
                "flush_cache": "POST /vram/flush-cache",
                "unload_model": "POST /vram/unload/{model_id}"
            },
            "admin": {
                "reconcile": "POST /vram/admin/reconcile",
                "crashes": "GET /vram/admin/crashes",
                "clear_crash": "DELETE /vram/admin/crashes/{model_id}"
            }
        }
    }


# VRAM Orchestrator Endpoints

@app.get("/vram/status")
async def vram_detailed_status():
    """Get detailed VRAM orchestrator status."""
    from app.services.vram import get_orchestrator
    orchestrator = get_orchestrator()
    return await orchestrator.get_status()


@app.post("/vram/unload/{model_id}")
async def force_unload(model_id: str):
    """Manually unload a specific model."""
    from app.services.vram import get_orchestrator
    orchestrator = get_orchestrator()
    await orchestrator.mark_model_unloaded(model_id)
    return {"status": "unloaded", "model_id": model_id}


@app.post("/vram/flush-cache")
async def flush_cache():
    """Manually flush buffer cache (requires sudo)."""
    from app.services.vram import get_orchestrator
    orchestrator = get_orchestrator()
    await orchestrator.flush_buffer_cache()
    return {"status": "cache_flushed"}


@app.get("/vram/psi")
async def get_psi():
    """Get current PSI (Pressure Stall Information)."""
    from app.services.vram import get_orchestrator
    orchestrator = get_orchestrator()
    status = await orchestrator.get_status()
    return {
        "psi": {
            "some_avg10": status['memory']['psi_some_avg10'],
            "full_avg10": status['memory']['psi_full_avg10']
        },
        "thresholds": {
            "some_warning": 20.0,
            "some_critical": 50.0,
            "full_warning": 5.0,
            "full_critical": 15.0
        }
    }


# Admin API - Manual Override Endpoints

@app.post("/vram/admin/reconcile")
async def force_reconciliation():
    """
    Force registry reconciliation (manually sync with backend).

    Useful for recovery after external OOM kills or manual interventions.
    """
    from app.services.vram import get_orchestrator
    orchestrator = get_orchestrator()
    stats = await orchestrator.reconcile_registry()
    return {
        "status": "reconciled",
        "registry_count": stats['registry_count'],
        "backend_count": stats['backend_count'],
        "cleaned_count": stats['cleaned_count'],
        "cleaned_models": stats['cleaned_models']
    }


@app.delete("/vram/admin/crashes/{model_id}")
async def clear_crash_history(model_id: str):
    """
    Clear crash history for a specific model.

    Useful for resetting circuit breaker after fixing model issues.
    """
    from app.services.vram import get_crash_tracker

    if not settings.VRAM_CIRCUIT_BREAKER_ENABLED:
        return {
            "status": "disabled",
            "message": "Circuit breaker is disabled"
        }

    crash_tracker = get_crash_tracker()

    # Check if model has crash history
    status_before = crash_tracker.check_crash_history(model_id)
    crash_count = status_before['crash_count']

    # Clear history
    crash_tracker.clear_history(model_id)

    return {
        "status": "cleared",
        "model_id": model_id,
        "crashes_cleared": crash_count
    }


@app.get("/vram/admin/crashes")
async def get_all_crashes():
    """Get crash statistics for all models with recent crashes."""
    from app.services.vram import get_crash_tracker

    if not settings.VRAM_CIRCUIT_BREAKER_ENABLED:
        return {
            "status": "disabled",
            "message": "Circuit breaker is disabled"
        }

    crash_tracker = get_crash_tracker()
    models_with_crashes = crash_tracker.get_all_models_with_crashes()

    crash_data = []
    for model_id in models_with_crashes:
        stats = crash_tracker.get_crash_stats(model_id)
        history_status = crash_tracker.check_crash_history(model_id)

        crash_data.append({
            "model_id": model_id,
            "crash_count": stats['crash_count'],
            "last_crash_ago_seconds": stats['last_crash_seconds_ago'],
            "needs_protection": history_status['needs_protection'],
            "crashes": stats['crashes']
        })

    return {
        "circuit_breaker_enabled": settings.VRAM_CIRCUIT_BREAKER_ENABLED,
        "crash_threshold": settings.VRAM_CRASH_THRESHOLD,
        "crash_window_seconds": settings.VRAM_CRASH_WINDOW_SECONDS,
        "models_with_crashes": crash_data,
        "total_models": len(crash_data)
    }


@app.get("/vram/health")
async def vram_health_check():
    """
    Dedicated VRAM orchestrator health check.

    Returns detailed health status including circuit breaker state.
    Useful for load balancers and monitoring systems.
    """
    from app.services.vram import get_orchestrator, get_crash_tracker

    try:
        orchestrator = get_orchestrator()
        status = await orchestrator.get_status()

        # Determine health status
        usage_pct = status['memory']['usage_pct']
        psi_full = status['memory']['psi_full_avg10']

        # Health thresholds
        healthy = (
            usage_pct < 90.0 and  # Below 90% usage
            psi_full < settings.VRAM_PSI_WARNING_THRESHOLD  # PSI below warning
        )

        # Circuit breaker status
        circuit_breaker_status = None
        if settings.VRAM_CIRCUIT_BREAKER_ENABLED:
            crash_tracker = get_crash_tracker()
            models_with_crashes = crash_tracker.get_all_models_with_crashes()

            circuit_breaker_status = {
                "enabled": True,
                "models_with_crashes": len(models_with_crashes),
                "crash_threshold": settings.VRAM_CRASH_THRESHOLD,
                "crash_window_seconds": settings.VRAM_CRASH_WINDOW_SECONDS
            }
        else:
            circuit_breaker_status = {"enabled": False}

        return {
            "status": "healthy" if healthy else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "orchestrator": {
                "enabled": settings.VRAM_ENABLE_ORCHESTRATOR,
                "loaded_models": len(status['loaded_models']),
                "memory_usage_pct": usage_pct,
                "available_gb": status['memory']['available_gb'],
                "psi_full_avg10": psi_full
            },
            "circuit_breaker": circuit_breaker_status,
            "healthy": healthy
        }

    except Exception as e:
        logger.error(f"❌ VRAM health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "healthy": False
        }
