"""Centralized health monitoring service."""
import asyncio
import sys
sys.path.insert(0, '/shared')

import logging_client
from health_checker import HealthChecker
from dashboard import create_app
from database import HealthDatabase
from alerts import AlertManager
from log_cleanup import LogCleanup
import uvicorn

logger = logging_client.setup_logger('monitoring-service')


async def main():
    """Main entry point."""
    logger.info("Starting monitoring service...")

    # Initialize components
    db = HealthDatabase('data/health_history.db')
    alert_manager = AlertManager()
    health_checker = HealthChecker(db, alert_manager)
    log_cleanup = LogCleanup(database=db)

    # Start health checking in background
    check_task = asyncio.create_task(health_checker.monitor_loop())

    # Start log cleanup in background
    cleanup_task = asyncio.create_task(log_cleanup.cleanup_loop())

    # Create FastAPI app with checker
    app = create_app(health_checker, db)

    # Run web server
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )
    server = uvicorn.Server(config)

    try:
        await server.serve()
    finally:
        check_task.cancel()
        cleanup_task.cancel()
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
