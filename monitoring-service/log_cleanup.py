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
    """Handles automatic cleanup of old log directories and database records."""

    def __init__(self, database=None):
        """Initialize log cleanup.

        Args:
            database: Optional HealthDatabase instance for database cleanup
        """
        self.settings = LogSettings()
        self.base_dir = Path(self.settings.LOG_BASE_DIR)
        self.database = database

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

    def cleanup_old_database_records(self) -> dict:
        """
        Delete old database records.

        Returns:
            Dict with cleanup statistics from database.cleanup_old_records()
        """
        if not self.database:
            logger.warning("⚠️  Database not configured for cleanup")
            return {'health_checks_deleted': 0, 'alerts_deleted': 0, 'cutoff_date': None}

        try:
            # Get stats before cleanup
            stats_before = self.database.get_database_stats()

            # Run cleanup
            result = self.database.cleanup_old_records(retention_days=self.settings.LOG_RETENTION_DAYS)

            # Get stats after cleanup
            stats_after = self.database.get_database_stats()

            # Calculate space freed
            space_freed_mb = stats_before['database_size_mb'] - stats_after['database_size_mb']

            logger.info(
                f"🗑️  Database cleanup: "
                f"{result['health_checks_deleted']:,} health checks, "
                f"{result['alerts_deleted']:,} alerts deleted "
                f"(cutoff: {result['cutoff_date'][:10]}), "
                f"{space_freed_mb:.2f} MB freed"
            )

            return result

        except Exception as e:
            logger.error(f"❌ Database cleanup failed: {e}")
            return {'health_checks_deleted': 0, 'alerts_deleted': 0, 'cutoff_date': None}

    async def cleanup_loop(self):
        """
        Background task that periodically cleans up old logs and database records.

        Runs every LOG_CLEANUP_INTERVAL_HOURS (default: 6 hours).
        """
        logger.info(
            f"🧹 Cleanup service started "
            f"(retention: {self.settings.LOG_RETENTION_DAYS} days, "
            f"interval: {self.settings.LOG_CLEANUP_INTERVAL_HOURS} hours)"
        )

        # Wait a bit before first cleanup (let service start up)
        await asyncio.sleep(60)

        while True:
            try:
                # Run log cleanup
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
                    logger.warning(f"⚠️  Log cleanup had {len(result['errors'])} errors")

                # Run database cleanup
                db_result = self.cleanup_old_database_records()

                if db_result['health_checks_deleted'] == 0 and db_result['alerts_deleted'] == 0:
                    logger.debug("🧹 Database cleanup: No old records to delete")

                # Sleep until next cleanup
                sleep_seconds = self.settings.LOG_CLEANUP_INTERVAL_HOURS * 3600
                await asyncio.sleep(sleep_seconds)

            except Exception as e:
                logger.error(f"❌ Error in log cleanup loop: {e}")
                # Sleep 1 hour before retrying on error
                await asyncio.sleep(3600)
