"""Admin Service FastAPI application."""
import sys
sys.path.insert(0, '/shared')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging_client

from app.config import settings

# Initialize logger
logger = logging_client.setup_logger('admin-service')

# Create FastAPI app
app = FastAPI(
    title="Trollama Admin Service",
    version=settings.SERVICE_VERSION,
    description="Admin API for model management, VRAM monitoring, user management, and system control"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,  # Token in URL, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info(f"🚀 Starting {settings.SERVICE_NAME} v{settings.SERVICE_VERSION}")
    logger.info(f"📍 TROISE AI URL: {settings.TROISE_AI_URL}")
    logger.info(f"🔐 JWT authentication enabled")

    if settings.DISCORD_ADMIN_WEBHOOK_URL:
        logger.info(f"🔔 Discord webhook configured")
    else:
        logger.warning("⚠️  Discord webhook not configured - notifications disabled")

    if not settings.INTERNAL_API_KEY:
        logger.warning("⚠️  INTERNAL_API_KEY not set - cannot communicate with TROISE AI")

    # Start health checker service (independent - monitors service health)
    from app.services.health_checker_service import HealthCheckerService
    health_checker = HealthCheckerService()
    await health_checker.start()
    app.state.health_checker = health_checker
    logger.info("🏥 Health checker service started")

    # Start system metrics service (independent - collects VRAM, PSI, queue)
    from app.services.system_metrics_service import SystemMetricsService
    system_metrics = SystemMetricsService()
    await system_metrics.start()
    app.state.system_metrics = system_metrics
    logger.info("📈 System metrics service started")

    # Start metrics writer (depends on both services above)
    from app.services.metrics_writer import MetricsWriter
    metrics_writer = MetricsWriter()
    await metrics_writer.start(
        system_metrics_service=system_metrics,
        health_checker_service=health_checker
    )
    app.state.metrics_writer = metrics_writer

    # Start log cleanup service (independent)
    from app.services.log_cleanup_service import LogCleanupService
    log_cleanup = LogCleanupService()
    await log_cleanup.start()
    app.state.log_cleanup = log_cleanup
    logger.info("🧹 Log cleanup service started")

    logger.info("✅ Admin service ready")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("👋 Shutting down admin service")

    # Stop background services (in reverse order of startup)
    if hasattr(app.state, "log_cleanup"):
        await app.state.log_cleanup.stop()
        logger.info("🧹 Log cleanup service stopped")

    if hasattr(app.state, "metrics_writer"):
        await app.state.metrics_writer.stop()
        logger.info("📊 Metrics writer stopped")

    if hasattr(app.state, "system_metrics"):
        await app.state.system_metrics.stop()
        logger.info("📈 System metrics service stopped")

    if hasattr(app.state, "health_checker"):
        await app.state.health_checker.stop()
        logger.info("🏥 Health checker service stopped")


@app.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION
    }


# Register API routers
from app.api import models, vram, users, system, monitoring, metrics, logs
app.include_router(models.router)
app.include_router(vram.router)
app.include_router(users.router)
app.include_router(system.router)
app.include_router(monitoring.router)
app.include_router(metrics.router)
app.include_router(logs.router)

logger.info("📦 Admin service module loaded")
