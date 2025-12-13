"""Strands Agent streaming chunk processor."""
from typing import Any, Optional, Dict
import logging_client

logger = logging_client.setup_logger('fastapi')


class StreamProcessor:
    """
    Processes Strands Agent streaming chunks.

    SOLID: Single Responsibility - chunk parsing and validation only

    Strands Agent emits TWO chunks per text piece:
    1. {'event': {'contentBlockDelta': {'delta': {'text': '...'}}}}
    2. {'data': '...', 'delta': {'text': '...'}, ...}
    We only process chunks with 'data' to avoid duplication.
    """

    def __init__(self):
        """Initialize processor state."""
        self.chunk_count = 0
        self.skipped_count = 0
        self.processed_count = 0

    def extract_content(self, chunk: Any) -> Optional[str]:
        """
        Extract text content from a Strands chunk.

        Args:
            chunk: Raw chunk from agent.stream_async()

        Returns:
            str: Extracted text content
            None: If chunk should be skipped
        """
        self.chunk_count += 1

        # Validate chunk is dict
        if not isinstance(chunk, dict):
            logger.debug(f"⏭️  Chunk #{self.chunk_count}: NOT a dict, type={type(chunk)}")
            self.skipped_count += 1
            return None

        # Log chunk structure (debug only)
        logger.debug(f"🔍 Chunk #{self.chunk_count}: keys={list(chunk.keys())}")

        # Skip event-only chunks (no 'data' key)
        if 'data' not in chunk:
            logger.debug(f"⏭️  Chunk #{self.chunk_count}: No 'data' key, skipping")
            self.skipped_count += 1
            return None

        # Extract text content
        text_content = chunk.get('data')

        # Validate content is string
        if not isinstance(text_content, str):
            logger.debug(f"⏭️  Chunk #{self.chunk_count}: data not string, type={type(text_content)}")
            self.skipped_count += 1
            return None

        logger.debug(f"🔍 Chunk #{self.chunk_count}: len={len(text_content)}, preview={repr(text_content[:100])}")
        self.processed_count += 1
        return text_content

    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        return {
            'total_chunks': self.chunk_count,
            'processed': self.processed_count,
            'skipped': self.skipped_count
        }
