"""Image content extractor using OCR (Ollama vision model)."""
import sys
sys.path.insert(0, '/shared')

from typing import Dict, Set
from app.services.extractors.interface import IContentExtractor
import logging_client

logger = logging_client.setup_logger('image-extractor')


class ImageExtractor(IContentExtractor):
    """
    Extract text from images using OCR.

    Depends on OCRService abstraction (could be swapped with different OCR provider).

    SOLID Principles:
    - Single Responsibility: Only handles image extraction
    - Open/Closed: Can add new image formats without modification
    - Dependency Inversion: Depends on OCRService abstraction
    """

    def __init__(self, ocr_service):
        """
        Initialize with OCR service dependency.

        Args:
            ocr_service: OCRService instance for image processing
        """
        self.ocr_service = ocr_service
        logger.info("✅ ImageExtractor initialized")

    def supported_extensions(self) -> Set[str]:
        """Supported image extensions."""
        return {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp'}

    def supported_mime_types(self) -> Set[str]:
        """Supported image MIME types."""
        return {
            'image/png', 'image/jpeg', 'image/gif',
            'image/bmp', 'image/tiff', 'image/webp'
        }

    async def extract(self, file_path: str, filename: str) -> Dict[str, str]:
        """Extract text from image using OCR."""
        logger.info(f"🖼️  Extracting from image: {filename}")

        try:
            result = await self.ocr_service.extract_text_from_image(file_path)
            logger.info(f"✅ OCR extracted {len(result['text'])} chars from {filename}")

            return {
                'text': result['text'],
                'extractor': 'image_ocr',
                'status': 'success'
            }
        except Exception as e:
            logger.error(f"❌ OCR failed for {filename}: {e}")
            return {
                'text': f'[OCR processing failed: {str(e)}]',
                'extractor': 'image_ocr',
                'status': 'error'
            }
