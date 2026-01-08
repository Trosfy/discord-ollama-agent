"""
Background Metrics Writer

Continuously writes monitoring snapshots to DynamoDB every 5 seconds.
Implements 2-day TTL retention for automatic data expiration.

Pulls metrics from two sources:
- SystemMetricsService: VRAM, PSI, queue metrics
- HealthCheckerService: Service health status
"""

import asyncio
import logging_client
from datetime import datetime, timedelta
from typing import Optional, Any, Dict
from decimal import Decimal

from app.services.system_metrics_service import SystemMetricsService
from app.services.health_checker_service import HealthCheckerService
from app.services.metrics_storage import MetricsStorage
from app.utils.metrics_transformer import MetricsTransformer
from app.config import settings

logger = logging_client.setup_logger('admin-service')


class MetricsWriter:
    """
    Background service that writes metrics to DynamoDB.

    Pulls data from:
    - SystemMetricsService: VRAM, PSI, queue metrics
    - HealthCheckerService: Service health status

    Writes 4 metric types every 5 seconds with 2-day TTL:
    - vram (system memory stats)
    - psi (pressure stall information)
    - queue (fastapi queue size)
    - health (service health status)
    """

    def __init__(self):
        self.system_metrics_service: Optional[SystemMetricsService] = None
        self.health_checker_service: Optional[HealthCheckerService] = None
        self.storage: Optional[MetricsStorage] = None
        self.interval = settings.METRICS_WRITE_INTERVAL_SECONDS
        self.running = False
        self._task: Optional[asyncio.Task] = None

    async def start(
        self,
        system_metrics_service: SystemMetricsService,
        health_checker_service: HealthCheckerService
    ):
        """
        Start the background metrics writing loop.

        Args:
            system_metrics_service: Service for VRAM, PSI, queue metrics
            health_checker_service: Service for service health metrics

        This creates an async task that runs continuously until stop() is called.
        Metrics are written every 5 seconds with 2-day TTL.
        """
        if self.running:
            logger.warning("MetricsWriter is already running")
            return

        self.system_metrics_service = system_metrics_service
        self.health_checker_service = health_checker_service
        self.running = True
        self.storage = MetricsStorage()

        # Ensure table exists before starting
        table_created = await self.storage.create_table()
        if not table_created:
            logger.error("Failed to create/verify metrics table, continuing anyway...")

        logger.info(f"📊 Metrics writer started (interval={self.interval}s, pulls from health checker + system metrics)")

        # Create background task
        self._task = asyncio.create_task(self._write_loop())

    async def stop(self):
        """
        Stop the background metrics writing loop.

        Gracefully stops the writer and waits for current operation to complete.
        """
        if not self.running:
            logger.warning("MetricsWriter is not running")
            return

        logger.info("Stopping background metrics writer...")
        self.running = False

        # Wait for current write operation to complete
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except asyncio.TimeoutError:
                logger.warning("MetricsWriter stop timed out, cancelling task")
                self._task.cancel()

        logger.info("Background metrics writer stopped")

    async def _write_loop(self):
        """
        Main write loop - runs continuously until stopped.

        Pulls metrics from both services and writes all metric types to DynamoDB.
        Errors are logged but don't stop the loop.
        """
        await asyncio.sleep(10)  # Initial delay to let services stabilize

        write_count = 0
        error_count = 0

        while self.running:
            try:
                # Pull from both services
                system_snapshot = await self.system_metrics_service.get_system_snapshot()
                health_snapshot = self.health_checker_service.get_health_snapshot()

                # Calculate TTL (2 days from now)
                timestamp = datetime.utcnow()
                ttl = int((timestamp + timedelta(days=2)).timestamp())

                # Convert floats to Decimal for DynamoDB compatibility
                vram_data = MetricsTransformer.convert_floats_to_decimal(system_snapshot.get("vram", {}))
                psi_data = MetricsTransformer.convert_floats_to_decimal(system_snapshot.get("psi", {}))
                queue_data = MetricsTransformer.convert_floats_to_decimal({"size": system_snapshot.get("queue_size", 0)})
                health_data = MetricsTransformer.convert_floats_to_decimal(health_snapshot)

                # Write all metric types in parallel
                results = await asyncio.gather(
                    self._write_metric_safe("vram", timestamp, vram_data, ttl),
                    self._write_metric_safe("psi", timestamp, psi_data, ttl),
                    self._write_metric_safe("queue", timestamp, queue_data, ttl),
                    self._write_metric_safe("health", timestamp, health_data, ttl),
                    return_exceptions=True
                )

                # Count successful writes
                successful = sum(1 for r in results if r is True)
                write_count += successful

                if successful < len(results):
                    error_count += (len(results) - successful)
                    logger.warning(
                        f"Only {successful}/{len(results)} metrics written successfully"
                    )

                # Log progress every 100 writes (~8 minutes at 5s interval)
                if write_count % 100 == 0:
                    logger.info(
                        f"Metrics writer: {write_count} successful writes, "
                        f"{error_count} errors"
                    )

                # Wait before next write
                await asyncio.sleep(self.interval)

            except asyncio.CancelledError:
                logger.info("Metrics writer cancelled")
                break

            except Exception as e:
                error_count += 1
                logger.error(f"Error in metrics write loop: {e}", exc_info=True)
                # Continue even on error, wait before retrying
                await asyncio.sleep(5)

        logger.info(
            f"Metrics writer loop ended. "
            f"Total writes: {write_count}, Total errors: {error_count}"
        )

    async def _write_metric_safe(
        self,
        metric_type: str,
        timestamp: datetime,
        data: dict,
        ttl: int
    ) -> bool:
        """
        Write a single metric with error handling.

        Args:
            metric_type: Type of metric (vram, health, psi, queue)
            timestamp: When the metric was collected
            data: The metric payload
            ttl: TTL as Unix timestamp

        Returns:
            True if write was successful, False otherwise
        """
        try:
            success = await self.storage.write_metric(
                metric_type, timestamp, data, ttl
            )

            if not success:
                logger.warning(f"Failed to write {metric_type} metric")

            return success

        except Exception as e:
            logger.error(
                f"Exception writing {metric_type} metric: {e}",
                exc_info=True
            )
            return False

    async def write_now(self) -> dict:
        """
        Manually trigger an immediate metrics write.

        Useful for testing or on-demand snapshots.

        Returns:
            Dictionary with write results:
                - timestamp: When write occurred
                - success: List of successfully written metric types
                - failed: List of failed metric types

        Example:
            result = await writer.write_now()
            # {
            #     "timestamp": "2025-01-25T10:30:45Z",
            #     "success": ["vram", "health", "psi", "queue"],
            #     "failed": []
            # }
        """
        try:
            # Pull from both services
            system_snapshot = await self.system_metrics_service.get_system_snapshot()
            health_snapshot = self.health_checker_service.get_health_snapshot()

            timestamp = datetime.utcnow()
            ttl = int((timestamp + timedelta(days=2)).timestamp())

            # Convert floats to Decimal for DynamoDB compatibility
            vram_data = MetricsTransformer.convert_floats_to_decimal(system_snapshot.get("vram", {}))
            psi_data = MetricsTransformer.convert_floats_to_decimal(system_snapshot.get("psi", {}))
            queue_data = MetricsTransformer.convert_floats_to_decimal({"size": system_snapshot.get("queue_size", 0)})
            health_data = MetricsTransformer.convert_floats_to_decimal(health_snapshot)

            results = await asyncio.gather(
                self._write_metric_safe("vram", timestamp, vram_data, ttl),
                self._write_metric_safe("psi", timestamp, psi_data, ttl),
                self._write_metric_safe("queue", timestamp, queue_data, ttl),
                self._write_metric_safe("health", timestamp, health_data, ttl),
                return_exceptions=True
            )

            metric_types = ["vram", "psi", "queue", "health"]
            success = [mt for mt, r in zip(metric_types, results) if r is True]
            failed = [mt for mt, r in zip(metric_types, results) if r is not True]

            return {
                "timestamp": timestamp.isoformat() + "Z",
                "success": success,
                "failed": failed
            }

        except Exception as e:
            logger.error(f"Error in manual metrics write: {e}", exc_info=True)
            return {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "success": [],
                "failed": ["vram", "psi", "queue", "health"]
            }
