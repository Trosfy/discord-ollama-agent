"""MinIO client for fetching generated images.

Used by message_handler to fetch images referenced by storage_key
from TROISE AI's file messages.
"""
import sys
sys.path.insert(0, '/shared')

import logging_client
from minio import Minio
from minio.error import S3Error
from typing import Optional

from bot.config import settings

logger = logging_client.setup_logger('discord-bot')


class MinIOClient:
    """Synchronous MinIO client for Discord bot.

    Note: minio-py is synchronous. For async usage, run in executor.

    Example:
        client = MinIOClient()
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, client.download, storage_key)
    """

    def __init__(self):
        """Initialize MinIO client from settings."""
        self._client: Optional[Minio] = None
        self._bucket = settings.MINIO_BUCKET

        # Only initialize if credentials are configured
        if settings.MINIO_ACCESS_KEY and settings.MINIO_SECRET_KEY:
            try:
                self._client = Minio(
                    settings.MINIO_ENDPOINT,
                    access_key=settings.MINIO_ACCESS_KEY,
                    secret_key=settings.MINIO_SECRET_KEY,
                    secure=settings.MINIO_SECURE,
                )
                logger.info(f"[MINIO] Client initialized: {settings.MINIO_ENDPOINT}")
            except Exception as e:
                logger.error(f"[MINIO] Failed to initialize client: {e}")
                self._client = None
        else:
            logger.warning("[MINIO] Credentials not configured - file fetching disabled")

    @property
    def is_configured(self) -> bool:
        """Check if MinIO client is properly configured."""
        return self._client is not None

    def download(self, storage_key: str) -> Optional[bytes]:
        """Download file from MinIO by storage_key.

        Args:
            storage_key: Object key in MinIO bucket.

        Returns:
            File bytes or None if download failed.
        """
        if not self._client:
            logger.error("[MINIO] Client not configured - cannot download")
            return None

        response = None
        try:
            logger.info(f"[MINIO] Downloading: {storage_key}")
            response = self._client.get_object(self._bucket, storage_key)
            data = response.read()
            logger.info(f"[MINIO] Fetched {len(data)} bytes")
            return data

        except S3Error as e:
            logger.error(f"[MINIO] S3 error downloading {storage_key}: {e}")
            return None

        except Exception as e:
            logger.error(f"[MINIO] Download failed for {storage_key}: {e}")
            return None

        finally:
            if response:
                response.close()
                response.release_conn()
