"""
Centralized logging service that receives logs from all containers.
Uses a FIFO queue to buffer incoming logs and prevent blocking.
"""
import logging
import os
import pickle
import queue
import socketserver
import struct
import sys
import threading
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Add shared directory to path
sys.path.insert(0, '/shared')
from health_server import HealthCheckServer
from log_config import LogSettings, get_log_file_path

# Global FIFO queue for log records
log_queue = queue.Queue(maxsize=10000)  # Buffer up to 10,000 log records


class QueueHandler(logging.Handler):
    """Handler that puts log records into the FIFO queue."""

    def emit(self, record):
        """Put log record into queue."""
        try:
            # Add service attribute if not present
            if not hasattr(record, 'service'):
                record.service = 'logging-service'
            log_queue.put(record, block=False)
        except queue.Full:
            # Queue full - drop log silently
            pass
        except Exception:
            self.handleError(record)


class LogRecordStreamHandler(socketserver.StreamRequestHandler):
    """Handler for streaming log records via TCP."""

    def handle(self):
        """Handle incoming log records and put them in queue."""
        while True:
            try:
                chunk = self.connection.recv(4)
                if len(chunk) < 4:
                    break
                slen = struct.unpack('>L', chunk)[0]
                chunk = self.connection.recv(slen)
                while len(chunk) < slen:
                    chunk += self.connection.recv(slen - len(chunk))
                obj = pickle.loads(chunk)
                record = logging.makeLogRecord(obj)

                # Put record in FIFO queue (non-blocking to prevent client hangs)
                try:
                    log_queue.put(record, block=False)
                except queue.Full:
                    # Queue full - drop log
                    # Note: Can't easily log here without service_logger reference
                    pass

            except Exception as e:
                # Log errors if they occur
                try:
                    service_logger = logging.getLogger('logging-service')
                    service_logger.error(f"Error receiving log: {e}")
                except:
                    pass
                break


class DailyRotatingFileHandler(RotatingFileHandler):
    """
    File handler that creates new log files in date-based directories.

    Checks on each log write if the date has changed, and if so,
    creates a new directory and switches to a new log file.

    Inherits from RotatingFileHandler to preserve size-based rotation
    (10MB files with 5 backups per date directory).
    """

    def __init__(self, base_dir: str, log_type: str, level: int, formatter):
        """
        Initialize handler.

        Args:
            base_dir: Base directory for logs (e.g., "/app/logs")
            log_type: Type of log ('app', 'debug', 'error')
            level: Logging level (e.g., logging.INFO)
            formatter: Log formatter
        """
        self.base_dir = base_dir
        self.log_type = log_type
        self.current_date = datetime.now().date()

        # Get settings
        settings = LogSettings()

        # Get initial log file path (e.g., "/app/logs/2025-12-11/app.log")
        initial_path = get_log_file_path(base_dir, log_type)

        # Create directory if needed
        initial_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize parent with current path
        super().__init__(
            str(initial_path),
            maxBytes=settings.LOG_MAX_BYTES,
            backupCount=settings.LOG_BACKUP_COUNT
        )

        self.setLevel(level)
        self.setFormatter(formatter)

    def emit(self, record):
        """
        Emit a record, checking if we need to rotate to new date directory.

        This is called for every log message. We check if the date has changed,
        and if so, rotate to a new directory before writing the log.
        """
        try:
            # Check if date has changed
            today = datetime.now().date()
            if today != self.current_date:
                # Date changed - rotate to new directory
                self._rotate_to_new_date(today)

            # Emit normally (parent class handles file I/O)
            super().emit(record)

        except Exception:
            self.handleError(record)

    def _rotate_to_new_date(self, new_date: datetime.date):
        """
        Rotate to a new date directory.

        Called when the date changes (e.g., from 2025-12-11 to 2025-12-12).
        Creates new directory and switches to new log file.
        """
        # Close current file handle
        if self.stream:
            self.stream.close()
            self.stream = None

        # Update current date
        self.current_date = new_date

        # Get new file path (e.g., "/app/logs/2025-12-12/app.log")
        new_path = get_log_file_path(
            self.base_dir,
            self.log_type,
            datetime.combine(new_date, datetime.min.time())
        )

        # Create directory if needed
        new_path.parent.mkdir(parents=True, exist_ok=True)

        # Update base filename (parent class uses this)
        self.baseFilename = str(new_path)

        # Reset stream (will be reopened on next write by parent class)
        self.stream = self._open()


def log_worker():
    """Worker thread that processes logs from FIFO queue and writes to files."""
    # Get root logger which has the file handlers
    root_logger = logging.getLogger()

    while True:
        try:
            # Block until log record available (FIFO order)
            record = log_queue.get(block=True)

            # Write directly to file handlers (skip QueueHandler to avoid loops)
            for handler in root_logger.handlers:
                # Only write to file handlers, not QueueHandler or console
                if isinstance(handler, (RotatingFileHandler, DailyRotatingFileHandler)):
                    if record.levelno >= handler.level:
                        handler.handle(record)

            # Mark task as done
            log_queue.task_done()
        except Exception as e:
            # Last resort: print to stdout (can't use logger here)
            print(f"CRITICAL: Error processing log: {e}")


def setup_logging_server():
    """Setup logging server with date-partitioned rotating file handlers."""
    # Get settings
    settings = LogSettings()

    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - [%(service)s] - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # App log (INFO+) - date-partitioned
    app_handler = DailyRotatingFileHandler(
        base_dir=settings.LOG_BASE_DIR,
        log_type='app',
        level=logging.INFO,
        formatter=formatter
    )
    root_logger.addHandler(app_handler)

    # Error log (ERROR+) - date-partitioned
    error_handler = DailyRotatingFileHandler(
        base_dir=settings.LOG_BASE_DIR,
        log_type='error',
        level=logging.ERROR,
        formatter=formatter
    )
    root_logger.addHandler(error_handler)

    # Debug log (DEBUG+) - date-partitioned
    debug_handler = DailyRotatingFileHandler(
        base_dir=settings.LOG_BASE_DIR,
        log_type='debug',
        level=logging.DEBUG,
        formatter=formatter
    )
    root_logger.addHandler(debug_handler)

    # Console output (optional)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


class ServiceFilter(logging.Filter):
    """Filter that adds service attribute to log records."""

    def filter(self, record):
        """Add service attribute to record."""
        if not hasattr(record, 'service'):
            record.service = 'logging-service'
        return True


def setup_service_logger():
    """Setup logger for logging-service itself (writes to queue)."""
    logger = logging.getLogger('logging-service')
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Don't propagate to root logger to avoid duplicates

    # Add filter to add service attribute to all records
    service_filter = ServiceFilter()
    logger.addFilter(service_filter)

    # Add queue handler so service logs go through the same FIFO queue
    queue_handler = QueueHandler()
    logger.addHandler(queue_handler)

    # Also add console handler for immediate visibility
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - [%(service)s] - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


# Mount health check constants
LOG_DIR = Path('/app/logs')
MOUNT_SENTINEL_FILE = LOG_DIR / '.mount_health'
HEALTH_CHECK_INTERVAL = 60  # seconds


def check_mount_health() -> bool:
    """Check if mount is healthy via write/read test."""
    try:
        test_content = f"health_check_{int(time.time())}"
        MOUNT_SENTINEL_FILE.write_text(test_content)
        read_content = MOUNT_SENTINEL_FILE.read_text()

        if read_content != test_content:
            return False

        # Check device ID
        stat_info = MOUNT_SENTINEL_FILE.stat()
        if not hasattr(check_mount_health, 'initial_device'):
            check_mount_health.initial_device = stat_info.st_dev
        elif check_mount_health.initial_device != stat_info.st_dev:
            return False

        return True
    except Exception:
        return False


def check_queue_health() -> bool:
    """Check if log queue is healthy (not too full)."""
    return log_queue.qsize() < log_queue.maxsize * 0.9


def mount_health_monitor():
    """Background thread that monitors mount health."""
    failure_count = 0
    max_failures = 3

    # Get logger
    logger = logging.getLogger('logging-service')

    while True:
        try:
            is_healthy = check_mount_health()

            if is_healthy:
                failure_count = 0  # Reset on success
                logger.debug("Mount health check passed")
            else:
                failure_count += 1
                logger.error(f"🚨 Mount unhealthy ({failure_count}/{max_failures})")

                if failure_count >= max_failures:
                    logger.error("🚨 MOUNT FAILURE: Exiting to trigger restart")
                    os._exit(1)  # Exit code 1 triggers Docker restart

            time.sleep(HEALTH_CHECK_INTERVAL)

        except Exception as e:
            logger.error(f"Mount monitor error: {e}")
            time.sleep(HEALTH_CHECK_INTERVAL)


if __name__ == '__main__':
    # Setup file handlers first
    setup_logging_server()

    # Setup service logger (logs go to queue)
    service_logger = setup_service_logger()

    # Start log worker thread (processes queue)
    worker_thread = threading.Thread(target=log_worker, daemon=True)
    worker_thread.start()
    service_logger.info("Log worker thread started")

    # Start mount health monitor thread
    monitor_thread = threading.Thread(target=mount_health_monitor, daemon=True)
    monitor_thread.start()
    service_logger.info("Mount health monitor started")

    # Setup and start health check server
    health_server = HealthCheckServer(service_name="logging-service", port=9998)
    health_server.register_check("mount", check_mount_health)
    health_server.register_check("queue", check_queue_health)
    health_server.start()
    service_logger.info("Health check endpoint started on port 9998")

    # Start TCP server on port 9999
    server = socketserver.ThreadingTCPServer(
        ('0.0.0.0', 9999),
        LogRecordStreamHandler
    )

    service_logger.info("Logging service started on port 9999")
    service_logger.info("Receiving logs and processing via FIFO queue")
    server.serve_forever()
