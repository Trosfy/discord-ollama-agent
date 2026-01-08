"""PDF content extractor using pypdf library."""
import sys
sys.path.insert(0, '/shared')

from typing import Dict, Set
from app.services.extractors.interface import IContentExtractor
import logging_client

logger = logging_client.setup_logger('pdf-extractor')


class PDFExtractor(IContentExtractor):
    """
    Extract text from PDFs using pypdf library.

    Uses pypdf (formerly PyPDF2) for reliable PDF text extraction.

    SOLID Principles:
    - Single Responsibility: Only handles PDF extraction
    - Open/Closed: Can be replaced with different PDF extraction method
    - Dependency Inversion: Uses pypdf abstraction
    """

    def supported_extensions(self) -> Set[str]:
        """Supported PDF extensions."""
        return {'.pdf'}

    def supported_mime_types(self) -> Set[str]:
        """Supported PDF MIME types."""
        return {'application/pdf'}

    async def extract(self, file_path: str, filename: str) -> Dict[str, str]:
        """Extract text from PDF using pypdf."""
        logger.info(f"📕 Extracting from PDF: {filename}")

        try:
            from pypdf import PdfReader

            # Read PDF and extract text from all pages
            reader = PdfReader(file_path)
            text_parts = []

            for page_num, page in enumerate(reader.pages):
                try:
                    text = page.extract_text()
                    if text.strip():  # Only add non-empty pages
                        text_parts.append(text)
                except Exception as e:
                    logger.warning(f"⚠️  Failed to extract page {page_num + 1} from {filename}: {e}")
                    continue

            content = '\n\n'.join(text_parts)
            logger.info(f"✅ Extracted {len(content)} chars from {len(reader.pages)} pages in PDF {filename}")

            return {
                'text': content,
                'extractor': 'pypdf',
                'status': 'success'
            }
        except Exception as e:
            logger.error(f"❌ PDF extraction failed for {filename}: {e}")
            return {
                'text': f'[PDF extraction failed: {str(e)}]',
                'extractor': 'pypdf',
                'status': 'error'
            }
