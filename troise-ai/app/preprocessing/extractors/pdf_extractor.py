"""PDF file extractor."""
import logging
from pathlib import Path
from typing import List

from .interface import IContentExtractor, ExtractionResult

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text from PDF documents.

    Uses pypdf for text extraction. Falls back gracefully
    if the library is not available.
    """

    MIMETYPES = [
        "application/pdf",
    ]

    @property
    def supported_mimetypes(self) -> List[str]:
        return self.MIMETYPES

    async def extract(self, file_path: str, mimetype: str) -> ExtractionResult:
        """Extract text from PDF.

        Args:
            file_path: Path to the PDF file.
            mimetype: MIME type (should be application/pdf).

        Returns:
            ExtractionResult with extracted text.
        """
        path = Path(file_path)

        if not path.exists():
            return ExtractionResult(
                text="",
                extractor_name="PDFExtractor",
                status="error",
                error_message=f"File not found: {file_path}",
            )

        try:
            # Try to import pypdf
            try:
                from pypdf import PdfReader
            except ImportError:
                try:
                    from PyPDF2 import PdfReader
                except ImportError:
                    return ExtractionResult(
                        text=f"[PDF: {path.name}]",
                        extractor_name="PDFExtractor",
                        status="error",
                        error_message="PDF library not available (install pypdf)",
                    )

            reader = PdfReader(str(path))
            page_count = len(reader.pages)

            # Extract text from all pages
            text_parts = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"--- Page {i + 1} ---\n{page_text}")

            full_text = "\n\n".join(text_parts)
            word_count = len(full_text.split())

            if not full_text.strip():
                # PDF might be image-based
                return ExtractionResult(
                    text=f"[PDF: {path.name} - {page_count} pages, no extractable text]",
                    extractor_name="PDFExtractor",
                    status="partial",
                    error_message="PDF appears to be image-based, no text extractable",
                    metadata={"page_count": page_count, "filename": path.name},
                )

            return ExtractionResult(
                text=full_text,
                extractor_name="PDFExtractor",
                status="success",
                metadata={
                    "page_count": page_count,
                    "word_count": word_count,
                    "char_count": len(full_text),
                    "filename": path.name,
                },
            )

        except Exception as e:
            logger.error(f"Failed to extract PDF {file_path}: {e}")
            return ExtractionResult(
                text=f"[PDF: {path.name}]",
                extractor_name="PDFExtractor",
                status="error",
                error_message=str(e),
            )
