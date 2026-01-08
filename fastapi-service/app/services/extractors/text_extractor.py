"""Text and code file content extractor using Strands file_read."""
import sys
sys.path.insert(0, '/shared')

from typing import Dict, Set
from app.services.extractors.interface import IContentExtractor
import logging_client

logger = logging_client.setup_logger('text-extractor')


class TextExtractor(IContentExtractor):
    """
    Extract content from text and code files using Strands file_read.

    Supports: .txt, .md, .csv, .py, .js, .json, etc.

    SOLID Principles:
    - Single Responsibility: Only handles text/code extraction
    - Open/Closed: Can add new text formats to supported_extensions()
    - Dependency Inversion: Uses Strands abstraction
    """

    def supported_extensions(self) -> Set[str]:
        """Supported text/code file extensions."""
        return {
            '.txt', '.md', '.csv', '.log',
            '.py', '.js', '.ts', '.tsx', '.jsx',
            '.json', '.yaml', '.yml', '.toml',
            '.html', '.xml', '.css', '.sql',
            '.sh', '.bash', '.rs', '.go', '.c', '.cpp', '.h'
        }

    def supported_mime_types(self) -> Set[str]:
        """Supported text MIME types."""
        return {
            'text/plain', 'text/markdown', 'text/csv',
            'text/html', 'text/xml', 'text/css',
            'application/json', 'application/javascript',
            'application/x-yaml'
        }

    async def extract(self, file_path: str, filename: str) -> Dict[str, str]:
        """Extract content from text/code files using Strands."""
        logger.info(f"📝 Extracting from text file: {filename}")

        try:
            from app.tools.strands_tools_wrapped import file_read_wrapped

            # Strands file_read handles text files directly
            content = file_read_wrapped(file_path)
            logger.info(f"✅ Extracted {len(content)} chars from text file {filename}")

            return {
                'text': content,
                'extractor': 'strands_text',
                'status': 'success'
            }
        except Exception as e:
            logger.error(f"❌ Text extraction failed for {filename}: {e}")
            return {
                'text': f'[Text extraction failed: {str(e)}]',
                'extractor': 'strands_text',
                'status': 'error'
            }
