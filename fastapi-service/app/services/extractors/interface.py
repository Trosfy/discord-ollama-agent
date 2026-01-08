"""
Content extractor interface for SOLID file extraction architecture.

Follows Open/Closed Principle: New file types can be added by creating new
extractor implementations without modifying existing code.
"""
import sys
sys.path.insert(0, '/shared')

from abc import ABC, abstractmethod
from typing import Dict, Set
import logging_client

logger = logging_client.setup_logger('content-extractors')


class IContentExtractor(ABC):
    """
    Abstract interface for content extractors.

    Each extractor handles specific file types and returns standardized output.

    SOLID Principles:
    - Single Responsibility: Each extractor handles ONE type of content
    - Open/Closed: New extractors can be added without modifying router
    - Liskov Substitution: All extractors are interchangeable via interface
    - Interface Segregation: Single focused interface
    - Dependency Inversion: Router depends on abstraction, not concrete classes
    """

    @abstractmethod
    def supported_extensions(self) -> Set[str]:
        """
        Return set of supported file extensions (e.g., {'.png', '.jpg'}).

        Returns:
            Set of lowercase file extensions with leading dot
        """
        pass

    @abstractmethod
    def supported_mime_types(self) -> Set[str]:
        """
        Return set of supported MIME types (e.g., {'image/png', 'image/jpeg'}).

        Returns:
            Set of MIME type strings
        """
        pass

    @abstractmethod
    async def extract(self, file_path: str, filename: str) -> Dict[str, str]:
        """
        Extract content from file.

        Args:
            file_path: Absolute path to file on disk
            filename: Original filename (for logging)

        Returns:
            Dict with:
            - 'text': Extracted content
            - 'extractor': Name of extractor used
            - 'status': 'success', 'error', or 'unsupported'
        """
        pass
