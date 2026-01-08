"""File service for managing temporary file storage and processing."""
import sys
sys.path.insert(0, '/shared')

import os
import uuid
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')


class FileService:
    """Manage temporary file storage, processing, and cleanup."""

    def __init__(self, extraction_router=None):
        """
        Initialize file service with SOLID extraction router.

        Args:
            extraction_router: FileExtractionRouter instance for content extraction
        """
        from app.config import settings
        self.extraction_router = extraction_router
        self.temp_upload_dir = Path(settings.TEMP_UPLOAD_DIR)
        self.temp_artifact_dir = Path(settings.TEMP_ARTIFACT_DIR)

        # Create directories if they don't exist
        self.temp_upload_dir.mkdir(exist_ok=True, parents=True)
        self.temp_artifact_dir.mkdir(exist_ok=True, parents=True)

        logger.info(f"✅ FileService initialized with extraction router")
        logger.info(f"   Upload directory: {self.temp_upload_dir}")
        logger.info(f"   Artifact directory: {self.temp_artifact_dir}")

    async def save_temp_file(
        self,
        file_data: bytes,
        filename: str,
        content_type: str,
        user_id: str
    ) -> Dict:
        """
        Save file to temp storage and process it (OCR for images, direct read for text).

        Args:
            file_data: Binary file content
            filename: Original filename
            content_type: MIME type
            user_id: User ID who uploaded the file

        Returns:
            Dict with file_id, filename, content_type, size, storage_path, extracted_content
        """
        file_id = str(uuid.uuid4())
        ext = Path(filename).suffix or '.bin'
        storage_path = self.temp_upload_dir / f"{file_id}{ext}"

        try:
            # Save file to disk
            with open(storage_path, 'wb') as f:
                f.write(file_data)

            logger.info(f"💾 Saved temp file: {filename} ({len(file_data)} bytes) → {file_id}{ext}")

            # Extract content using SOLID router (Strategy Pattern)
            extracted_content = None
            try:
                if self.extraction_router is None:
                    logger.warning("⚠️  Extraction router not available")
                    extracted_content = "[Extraction router not available]"
                else:
                    result = await self.extraction_router.extract_content(
                        str(storage_path),
                        content_type
                    )
                    extracted_content = result['text']
                    extractor = result['extractor']
                    logger.info(f"✅ Extracted content from {filename}: {len(extracted_content)} chars ({extractor})")

            except Exception as e:
                logger.error(f"❌ Failed to extract content from {file_id}: {e}")
                extracted_content = "[Extraction failed]"

            return {
                'file_id': file_id,
                'filename': filename,
                'content_type': content_type,
                'size': len(file_data),
                'storage_path': str(storage_path),
                'extracted_content': extracted_content,
                'user_id': user_id
            }

        except Exception as e:
            logger.error(f"❌ Failed to save temp file {filename}: {e}")
            raise

    async def delete_file(self, storage_path: str):
        """
        Delete temporary file.

        Args:
            storage_path: Path to file to delete
        """
        try:
            file_path = Path(storage_path)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"🗑️  Deleted temp file: {file_path.name}")
            else:
                logger.warning(f"⚠️  File not found for deletion: {storage_path}")

        except Exception as e:
            logger.warning(f"⚠️  Failed to delete {storage_path}: {e}")

    async def save_artifact(
        self,
        artifact_id: str,
        content: str,
        filename: str
    ) -> str:
        """
        Save artifact to temp storage (12 hours TTL).

        Args:
            artifact_id: Unique artifact identifier
            content: Artifact content (text)
            filename: Desired filename

        Returns:
            storage_path: Full path to saved artifact
        """
        # Sanitize filename to prevent path traversal
        safe_filename = Path(filename).name  # Remove any path components
        storage_path = self.temp_artifact_dir / f"{artifact_id}_{safe_filename}"

        try:
            with open(storage_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"📦 Saved artifact: {safe_filename} ({len(content)} bytes) → {storage_path.name}")

            return str(storage_path)

        except Exception as e:
            logger.error(f"❌ Failed to save artifact {filename}: {e}")
            raise

    async def cleanup_old_artifacts(self, max_age_hours: int = 12):
        """
        Delete artifacts older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours before deletion (default: 12)

        Returns:
            int: Number of files cleaned up
        """
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        cleaned_count = 0

        try:
            for file_path in self.temp_artifact_dir.glob('*'):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    cleaned_count += 1
                    logger.info(f"🧹 Cleaned up old artifact: {file_path.name}")

            if cleaned_count > 0:
                logger.info(f"✅ Cleanup complete: {cleaned_count} old artifact(s) removed")
            else:
                logger.info("✅ Cleanup complete: No old artifacts to remove")

            return cleaned_count

        except Exception as e:
            logger.error(f"❌ Artifact cleanup failed: {e}")
            return cleaned_count

    async def cleanup_old_uploads(self, max_age_hours: int = 1):
        """
        Delete stale upload files (should normally be deleted immediately).

        This is a safety mechanism for files that weren't deleted due to errors.

        Args:
            max_age_hours: Maximum age in hours before deletion (default: 1)

        Returns:
            int: Number of files cleaned up
        """
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        cleaned_count = 0

        try:
            for file_path in self.temp_upload_dir.glob('*'):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    cleaned_count += 1
                    logger.warning(f"🧹 Cleaned up stale upload: {file_path.name}")

            if cleaned_count > 0:
                logger.warning(f"⚠️  Upload cleanup: {cleaned_count} stale file(s) removed")

            return cleaned_count

        except Exception as e:
            logger.error(f"❌ Upload cleanup failed: {e}")
            return cleaned_count
