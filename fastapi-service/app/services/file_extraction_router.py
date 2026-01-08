"""
SOLID file extraction router using Strategy Pattern.

Open/Closed Principle: New file types can be added by registering new extractors
without modifying this class.

Dependency Inversion Principle: Depends on IContentExtractor abstraction, not
concrete extractor implementations.
"""
import sys
sys.path.insert(0, '/shared')

from typing import Dict, List
from pathlib import Path
from app.services.extractors.interface import IContentExtractor
import logging_client

logger = logging_client.setup_logger('file-extraction-router')


class FileExtractionRouter:
    """
    Routes files to appropriate content extractors using Strategy Pattern.

    SOLID Compliance:
    - Single Responsibility: Only routes to extractors, doesn't extract content
    - Open/Closed: OPEN for extension (add extractors), CLOSED for modification
    - Liskov Substitution: All IContentExtractor implementations are interchangeable
    - Interface Segregation: Depends on focused IContentExtractor interface
    - Dependency Inversion: Depends on IContentExtractor abstraction

    Usage:
        router = FileExtractionRouter()
        router.register_extractor(ImageExtractor(ocr_service))
        router.register_extractor(PDFExtractor())
        router.register_extractor(TextExtractor())

        result = await router.extract_content('/path/to/file.pdf', 'application/pdf')
    """

    def __init__(self):
        """Initialize router with empty extractor registry."""
        self.extractors: List[IContentExtractor] = []
        logger.info("✅ FileExtractionRouter initialized")

    def register_extractor(self, extractor: IContentExtractor) -> None:
        """
        Register content extractor (Strategy Pattern).

        Open/Closed Principle: Add new extractors WITHOUT modifying router code.

        Args:
            extractor: IContentExtractor implementation
        """
        self.extractors.append(extractor)
        logger.info(
            f"📎 Registered extractor: {extractor.__class__.__name__} "
            f"(extensions: {extractor.supported_extensions()})"
        )

    async def extract_content(
        self,
        file_path: str,
        content_type: str
    ) -> Dict[str, str]:
        """
        Extract content from file by routing to appropriate extractor.

        Args:
            file_path: Path to file on disk
            content_type: MIME type

        Returns:
            Dict with 'text' (extracted content), 'extractor', 'status'
        """
        ext = Path(file_path).suffix.lower()
        filename = Path(file_path).name

        logger.info(f"📄 Routing file: {filename} ({ext}, {content_type})")

        # Find matching extractor (Strategy Pattern)
        for extractor in self.extractors:
            # Check if extractor supports this file type
            if (ext in extractor.supported_extensions() or
                content_type in extractor.supported_mime_types()):

                logger.info(
                    f"✓ Matched extractor: {extractor.__class__.__name__} "
                    f"for {filename}"
                )
                return await extractor.extract(file_path, filename)

        # No extractor found
        logger.warning(f"⚠️  Unsupported file type: {ext} ({content_type})")
        return {
            'text': f'[Unsupported file type: {ext}]',
            'extractor': 'none',
            'status': 'unsupported'
        }
