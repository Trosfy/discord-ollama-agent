"""Log cleanup background task."""
import asyncio
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/shared')
import logging_client
from log_config import LogSettings

logger = logging_client.setup_logger('monitoring-service')


class LogCleanup:
    """Handles automatic cleanup of old log directories."""

    def __init__(self):
        """Initialize log cleanup."""
        self.settings = LogSettings()
        self.base_dir = Path(self.settings.LOG_BASE_DIR)

    def get_old_log_directories(self) -> list[Path]:
        """
        Get list of log directories older than retention period.

        Returns:
            List of directories to delete (e.g., [Path('/app/logs/2025-12-08'), ...])
        """
        if not self.base_dir.exists():
            logger.warning(f"Log base directory does not exist: {self.base_dir}")
            return []

        # Calculate cutoff date (e.g., if retention is 2 days, cutoff is 2 days ago)
        cutoff_date = datetime.now() - timedelta(days=self.settings.LOG_RETENTION_DAYS)

        old_dirs = []

        # Iterate through date directories
        for dir_path in self.base_dir.iterdir():
            if not dir_path.is_dir():
                continue

            # Try to parse directory name as date
            try:
                dir_date = datetime.strptime(dir_path.name, self.settings.LOG_DATE_FORMAT)

                # Check if older than retention period
                if dir_date < cutoff_date:
                    old_dirs.append(dir_path)

            except ValueError:
                # Not a date directory - skip (e.g., "temp", "backup")
                logger.warning(f"Skipping non-date directory: {dir_path.name}")
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
                'errors': list[str]
            }
        """
        old_dirs = self.get_old_log_directories()

        deleted_count = 0
        deleted_bytes = 0
        errors = []

        for dir_path in old_dirs:
            try:
                # Calculate size before deletion (for metrics)
                dir_size = sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file())

                # Delete directory recursively
                shutil.rmtree(dir_path)

                deleted_count += 1
                deleted_bytes += dir_size

                logger.info(
                    f"🗑️  Deleted old log directory: {dir_path.name} "
                    f"({dir_size / 1024 / 1024:.2f} MB)"
                )

            except Exception as e:
                error_msg = f"Failed to delete {dir_path.name}: {e}"
                errors.append(error_msg)
                logger.error(f"❌ {error_msg}")

        return {
            'deleted_count': deleted_count,
            'deleted_bytes': deleted_bytes,
            'errors': errors
        }

    async def cleanup_loop(self):
        """
        Background task that periodically cleans up old logs.

        Runs every LOG_CLEANUP_INTERVAL_HOURS (default: 6 hours).
        """
        logger.info(
            f"🧹 Log cleanup started "
            f"(retention: {self.settings.LOG_RETENTION_DAYS} days, "
            f"interval: {self.settings.LOG_CLEANUP_INTERVAL_HOURS} hours)"
        )

        # Wait a bit before first cleanup (let service start up)
        await asyncio.sleep(60)

        while True:
            try:
                # Run cleanup
                result = self.cleanup_old_logs()

                if result['deleted_count'] > 0:
                    logger.info(
                        f"🧹 Log cleanup complete: "
                        f"{result['deleted_count']} directories deleted, "
                        f"{result['deleted_bytes'] / 1024 / 1024:.2f} MB freed"
                    )
                else:
                    logger.debug("🧹 Log cleanup: No old directories to delete")

                if result['errors']:
                    logger.warning(f"⚠️  Cleanup had {len(result['errors'])} errors")

                # Sleep until next cleanup
                sleep_seconds = self.settings.LOG_CLEANUP_INTERVAL_HOURS * 3600
                await asyncio.sleep(sleep_seconds)

            except Exception as e:
                logger.error(f"❌ Error in log cleanup loop: {e}")
                # Sleep 1 hour before retrying on error
                await asyncio.sleep(3600)
