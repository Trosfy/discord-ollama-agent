"""Log cleanup service for Trollama."""
import asyncio
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, '/shared')
import logging_client

from app.config import settings

logger = logging_client.setup_logger('admin-service')


class LogCleanupService:
    """
    Handles automatic cleanup of old log directories.

    Runs on configured interval and deletes log directories older than retention period.
    Database cleanup is not needed since DynamoDB uses automatic TTL.
    """

    LOG_DATE_FORMAT = "%Y-%m-%d"

    def __init__(self):
        """Initialize log cleanup service from settings."""
        self.base_dir = Path(settings.LOG_BASE_DIR)
        self.retention_days = settings.LOG_RETENTION_DAYS
        self.cleanup_interval_hours = settings.LOG_CLEANUP_INTERVAL_HOURS

        self._task: Optional[asyncio.Task] = None
        self._running = False

    def get_old_log_directories(self) -> list[Path]:
        """
        Get list of log directories older than retention period.

        Returns:
            List of directories to delete (e.g., [Path('/app/logs/2025-12-08'), ...])
        """
        if not self.base_dir.exists():
            logger.warning(f"Log base directory does not exist: {self.base_dir}")
            return []

        # Calculate cutoff date (if retention is 2 days, cutoff is 2 days ago)
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        old_dirs = []

        # Iterate through date directories
        for dir_path in self.base_dir.iterdir():
            if not dir_path.is_dir():
                continue

            # Try to parse directory name as date
            try:
                dir_date = datetime.strptime(dir_path.name, self.LOG_DATE_FORMAT)

                # Check if older than retention period
                if dir_date < cutoff_date:
                    old_dirs.append(dir_path)

            except ValueError:
                # Not a date directory - skip (e.g., "temp", "backup")
                logger.debug(f"Skipping non-date directory: {dir_path.name}")
                continue

        return old_dirs

    def cleanup_old_logs(self) -> dict:
        """
        Delete old log directories.

        Returns:
            Dict with cleanup statistics:
            {
                'deleted_count': int,
                'deleted_bytes': int,
                'deleted_dirs': list[str],
                'errors': list[str]
            }
        """
        old_dirs = self.get_old_log_directories()

        deleted_count = 0
        deleted_bytes = 0
        deleted_dirs = []
        errors = []

        for dir_path in old_dirs:
            try:
                # Check if directory is writable before attempting deletion
                if not os.access(dir_path, os.W_OK):
                    error_msg = (
                        f"Cannot delete {dir_path.name}: Permission denied. "
                        f"Fix: Run 'sudo chown -R $USER:$USER {self.base_dir}' on the host"
                    )
                    errors.append(error_msg)
                    logger.warning(f"⏭️  {error_msg}")
                    continue

                # Calculate size before deletion (for metrics)
                dir_size = sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file())

                # Delete directory recursively
                shutil.rmtree(dir_path)

                deleted_count += 1
                deleted_bytes += dir_size
                deleted_dirs.append(dir_path.name)

                logger.info(
                    f"🗑️  Deleted old log directory: {dir_path.name} "
                    f"({dir_size / 1024 / 1024:.2f} MB)"
                )

            except PermissionError as e:
                error_msg = (
                    f"Permission denied deleting {dir_path.name}. "
                    f"Fix: Run 'sudo chown -R $USER:$USER {self.base_dir}' on the host"
                )
                errors.append(error_msg)
                logger.warning(f"⏭️  {error_msg}")
            except Exception as e:
                error_msg = f"Failed to delete {dir_path.name}: {e}"
                errors.append(error_msg)
                logger.error(f"❌ {error_msg}")

        return {
            'deleted_count': deleted_count,
            'deleted_bytes': deleted_bytes,
            'deleted_dirs': deleted_dirs,
            'errors': errors
        }

    async def _cleanup_loop(self):
        """Background task that periodically cleans up old logs."""
        logger.info(
            f"Log cleanup service started "
            f"(retention={self.retention_days}d, interval={self.cleanup_interval_hours}h, dir={self.base_dir})"
        )

        # Wait a bit before first cleanup (let service start up)
        await asyncio.sleep(60)

        while self._running:
            try:
                # Run log cleanup
                result = self.cleanup_old_logs()

                if result['deleted_count'] > 0:
                    logger.info(
                        f"🧹 Log cleanup complete: "
                        f"{result['deleted_count']} directories deleted "
                        f"({', '.join(result['deleted_dirs'])}), "
                        f"{result['deleted_bytes'] / 1024 / 1024:.2f} MB freed"
                    )
                else:
                    logger.debug(f"🧹 Log cleanup: No old directories to delete (cutoff: {self.retention_days} days)")

                if result['errors']:
                    logger.warning(f"⚠️  Log cleanup had {len(result['errors'])} errors")

            except Exception as e:
                logger.error(f"❌ Error in log cleanup loop: {e}", exc_info=True)

            # Sleep until next cleanup
            sleep_seconds = self.cleanup_interval_hours * 3600
            await asyncio.sleep(sleep_seconds)

    async def start(self):
        """Start the log cleanup background task."""
        if self._running:
            logger.warning("Log cleanup service already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())

    async def stop(self):
        """Stop the log cleanup background task."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Log cleanup service stopped")
