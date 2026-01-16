"""
Logging client configuration for sending logs to centralized service.
"""
import logging
import logging.handlers
import os


def setup_logger(service_name: str) -> logging.Logger:
    """
    Setup logger that sends logs to centralized logging service.

    Args:
        service_name: Name of service ('fastapi' or 'discord-bot')

    Returns:
        Configured logger
    """
    # Get logging service host and port from environment
    log_host = os.getenv('LOGGING_HOST', 'logging-service')
    log_port = int(os.getenv('LOGGING_PORT', 9999))

    # Add service name to all log records (must be done before creating handlers)
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.service = service_name
        return record

    logging.setLogRecordFactory(record_factory)

    # Create handlers
    # Socket handler sends DEBUG+ to centralized logging service
    socket_handler = logging.handlers.SocketHandler(log_host, log_port)
    socket_handler.setLevel(logging.DEBUG)

    # Console handler shows INFO+ only (less verbose)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - [%(service)s] - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)

    # Configure root logger so all module loggers (using __name__) inherit handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Allow DEBUG through, handlers filter
    root_logger.handlers = []  # Clear existing handlers
    root_logger.addHandler(socket_handler)
    root_logger.addHandler(console_handler)

    # Also create the named service logger for direct use
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.DEBUG)

    return logger
