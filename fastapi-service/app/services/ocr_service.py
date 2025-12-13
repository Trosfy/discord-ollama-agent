"""OCR service for extracting text from images using Ollama deepseek-ocr."""
import sys
sys.path.insert(0, '/shared')

import aiohttp
from pathlib import Path
from typing import Dict
import base64
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')


class OCRService:
    """Extract text from images using Ollama ministral-3:14b model."""

    def __init__(self, ollama_host: str = "http://host.docker.internal:11434", ocr_model: str = None):
        """
        Initialize OCR service with Ollama backend.

        Args:
            ollama_host: URL of Ollama API server
            ocr_model: OCR model to use (defaults to config setting)
        """
        from app.config import settings
        self.ollama_host = ollama_host
        self.ocr_model = ocr_model or settings.OCR_MODEL
        logger.info(f"✅ OCRService initialized with model: {self.ocr_model}")

    async def extract_text_from_image(self, image_path: str) -> Dict[str, str]:
        """
        Extract text from image using Ollama ministral-3 model.

        Args:
            image_path: Path to image file on disk

        Returns:
            Dict with 'text' (extracted content), 'model', and 'status'

        Raises:
            Exception: If OCR processing fails
        """
        logger.info(f"🖼️  OCR: Processing image {Path(image_path).name}")

        try:
            # Read and encode image as base64
            with open(image_path, 'rb') as f:
                image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            # Call Ollama OCR API
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.ocr_model,
                    "prompt": "Describe this image in detail. Include:\n- What objects, scenes, people, or items you see\n- Any charts, diagrams, or visual data\n- Any text visible in the image\n- Colors, layout, and composition\n\nBe thorough and descriptive.",
                    "images": [image_base64],
                    "stream": False
                }

                async with session.post(
                    f"{self.ollama_host}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"Ollama API error {resp.status}: {error_text}")

                    result = await resp.json()

            extracted_text = result.get('response', '')
            logger.info(f"📝 OCR raw response: {extracted_text}")
            logger.info(f"✅ OCR: Extracted {len(extracted_text)} characters from {Path(image_path).name}")

            return {
                'text': extracted_text,
                'model': self.ocr_model,
                'status': 'success'
            }

        except Exception as e:
            logger.error(f"❌ OCR failed for {image_path}: {e}")
            return {
                'text': f'[OCR processing failed: {str(e)}]',
                'model': self.ocr_model,
                'status': 'error'
            }

    async def analyze_document(self, file_path: str, content_type: str) -> Dict[str, str]:
        """
        Analyze any document type.

        For images: Use deepseek-ocr vision model
        For text files: Read directly
        For PDFs: Not yet supported (future enhancement)

        Args:
            file_path: Path to file on disk
            content_type: MIME type of the file

        Returns:
            Dict with 'text' (extracted content), 'model', and 'status'
        """
        logger.info(f"📄 Analyzing document: {Path(file_path).name} ({content_type})")

        # Handle images with OCR
        if content_type.startswith('image/'):
            return await self.extract_text_from_image(file_path)

        # Handle text files with direct read
        elif content_type in ['text/plain', 'text/markdown', 'text/csv']:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                logger.info(f"✅ Read {len(content)} characters from {Path(file_path).name}")

                return {
                    'text': content,
                    'model': 'direct_read',
                    'status': 'success'
                }
            except Exception as e:
                logger.error(f"❌ Failed to read text file {file_path}: {e}")
                return {
                    'text': f'[Failed to read file: {str(e)}]',
                    'model': 'direct_read',
                    'status': 'error'
                }

        # Unsupported file types
        else:
            logger.warning(f"⚠️  Unsupported file type: {content_type}")
            return {
                'text': f'[Unsupported file type: {content_type}]',
                'model': 'none',
                'status': 'unsupported'
            }
