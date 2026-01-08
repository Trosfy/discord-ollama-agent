"""
Content extractors for SOLID file processing architecture.

This package contains:
- IContentExtractor: Abstract interface (SOLID abstraction)
- ImageExtractor: Extract text from images using OCR
- PDFExtractor: Extract text from PDFs using Strands
- TextExtractor: Extract text from text/code files using Strands

Strategy Pattern: FileExtractionRouter uses these extractors.
Open/Closed Principle: New file types added by creating new extractors.
"""

from app.services.extractors.interface import IContentExtractor
from app.services.extractors.image_extractor import ImageExtractor
from app.services.extractors.pdf_extractor import PDFExtractor
from app.services.extractors.text_extractor import TextExtractor

__all__ = [
    'IContentExtractor',
    'ImageExtractor',
    'PDFExtractor',
    'TextExtractor',
]
