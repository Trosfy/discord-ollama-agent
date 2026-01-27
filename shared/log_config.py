"""Shared logging configuration."""
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from datetime import datetime


class LogSettings(BaseSettings):
    """Logging configuration with environment variable support."""

    # Log directory structure
    LOG_BASE_DIR: str = "/app/logs"
    LOG_DATE_FORMAT: str = "%Y-%m-%d"  # Format for date directories (e.g., "2025-12-11")

    # Retention settings
    LOG_RETENTION_DAYS: int = 2  # Delete logs and database records older than this
    LOG_CLEANUP_INTERVAL_HOURS: int = 6  # How often to run cleanup (every 6 hours)

    # Rotation settings (per-file within each date directory)
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB per file (before rotation)
    LOG_BACKUP_COUNT: int = 5  # Keep 5 rotated files per log type (e.g., app.log.1, app.log.2, ...)

    # Log levels
    APP_LOG_LEVEL: str = "INFO"
    DEBUG_LOG_LEVEL: str = "DEBUG"
    ERROR_LOG_LEVEL: str = "ERROR"

    # Third-party loggers to silence (set to WARNING level)
    # Can be overridden via NOISY_LOGGERS env var (comma-separated)
    NOISY_LOGGERS: str = "botocore,boto3,aioboto3,aiobotocore,urllib3,httpx,httpcore,asyncio,websockets,sse_starlette"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )


def get_log_directory_for_date(base_dir: str, date: datetime = None) -> Path:
    """
    Get log directory path for a specific date.

    Args:
        base_dir: Base log directory (e.g., "/app/logs")
        date: Date to get directory for (defaults to today)

    Returns:
        Path to date-specific log directory (e.g., "/app/logs/2025-12-11")
    """
    if date is None:
        date = datetime.now()

    settings = LogSettings()
    date_str = date.strftime(settings.LOG_DATE_FORMAT)
    return Path(base_dir) / date_str


def get_log_file_path(base_dir: str, log_type: str, date: datetime = None) -> Path:
    """
    Get full path for a log file.

    Args:
        base_dir: Base log directory (e.g., "/app/logs")
        log_type: Type of log ('app', 'debug', 'error')
        date: Date for log (defaults to today)

    Returns:
        Full path to log file (e.g., "/app/logs/2025-12-11/app.log")
    """
    log_dir = get_log_directory_for_date(base_dir, date)
    return log_dir / f"{log_type}.log"
