"""Input artifact detection service (Single Responsibility Principle)."""
import sys
sys.path.insert(0, '/shared')

from typing import List, Dict
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')


class InputArtifactDetector:
    """Detects if files are uploaded (Single Responsibility)."""

    def detect(self, file_refs: List[Dict]) -> bool:
        """
        Deterministic check for uploaded files.

        Args:
            file_refs: List of file reference dicts with file metadata

        Returns:
            True if files are uploaded, False otherwise
        """
        has_files = len(file_refs) > 0

        if has_files:
            logger.info(f"📎 INPUT_ARTIFACT detected: {len(file_refs)} file(s) uploaded")

        return has_files
