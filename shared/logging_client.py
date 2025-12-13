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

    # Create logger
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    logger.handlers = []

    # Add socket handler to send to logging service
    socket_handler = logging.handlers.SocketHandler(log_host, log_port)

    # Add service name to all log records
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.service = service_name
        return record

    logging.setLogRecordFactory(record_factory)

    logger.addHandler(socket_handler)

    # Also add console handler for local debugging
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - [%(service)s] - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger
