"""Main FastAPI application entry point."""
import sys
sys.path.insert(0, '/shared')

from fastapi import FastAPI
from contextlib import asynccontextmanager
from datetime import datetime

from app.config import settings

# Import logging client
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')
from app.api import websocket, discord, admin, user
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
    check_ollama_model_loaded
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Discord-Ollama Agent...")

    # Initialize storage
    storage = get_storage()
    await storage.initialize_tables()
    logger.info("DynamoDB tables initialized")

    # Initialize queue
    queue = get_queue()
    await queue.start()
    logger.info("Queue started")

    # Start queue worker
    worker = get_queue_worker()
    await worker.start()
    logger.info("Queue worker started")

    # Health checks
    db_ok = await check_dynamodb()
    ollama_ok = await check_ollama()
    model_ok = await check_ollama_model_loaded()

    if db_ok:
        logger.info("DynamoDB: OK")
    else:
        logger.error("DynamoDB: FAIL")

    if ollama_ok:
        logger.info("Ollama: OK")
    else:
        logger.error("Ollama: FAIL")

    if model_ok:
        logger.info(f"Model ({settings.OLLAMA_DEFAULT_MODEL}): Loaded")
    else:
        logger.warning(f"Model ({settings.OLLAMA_DEFAULT_MODEL}): Not loaded")

    if not all([db_ok, ollama_ok]):
        logger.warning("Some services unavailable, but starting anyway...")

    logger.info(f"FastAPI service ready on {settings.HOST}:{settings.PORT}")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await worker.stop()
    await queue.stop()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Include routers
app.include_router(websocket.router, tags=["websocket"])
app.include_router(discord.router, prefix="/api/discord", tags=["discord"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(user.router, prefix="/api/user", tags=["user"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "dynamodb": await check_dynamodb(),
            "ollama": await check_ollama(),
            "model_loaded": await check_ollama_model_loaded(),
        },
        "queue_size": get_queue().size(),
        "websocket_connections": get_websocket_manager().count_connections(),
        "maintenance_mode": settings.MAINTENANCE_MODE,
        "maintenance_mode_hard": settings.MAINTENANCE_MODE_HARD
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Discord-Ollama Agent API",
        "version": settings.VERSION,
        "health": "/health",
        "docs": "/docs"
    }
