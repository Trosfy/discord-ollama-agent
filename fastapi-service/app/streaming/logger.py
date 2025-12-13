"""Streaming diagnostics and logging."""
import logging_client

logger = logging_client.setup_logger('fastapi')


class StreamLogger:
    """
    Centralized logging for streaming operations.

    SOLID: Single Responsibility - diagnostic logging only
    """

    def __init__(self, debug_enabled: bool = True):
        """
        Initialize logger.

        Args:
            debug_enabled: Enable debug-level logging
        """
        self.debug = debug_enabled
        self.log_count = 0

    def log_chunk(self, original: str, filtered: str):
        """
        Log chunk processing result.

        Args:
            original: Original chunk content
            filtered: Filtered chunk content
        """
        self.log_count += 1

        if not self.debug:
            return

        # Only log if content changed
        if original != filtered:
            logger.debug(
                f"🔍 After filtering: "
                f"len={len(filtered)}, "
                f"stripped_len={len(filtered.strip())}"
            )

        # Log chunk being yielded
        logger.debug(
            f"✅ Yielding chunk: "
            f"len={len(filtered)}, "
            f"stripped_len={len(filtered.strip())}"
        )

    def log_stats(self, stats: dict):
        """
        Log processing statistics.

        Args:
            stats: Statistics dictionary
        """
        logger.info(f"📊 Streaming stats: {stats}")
