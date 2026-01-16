"""MinIO adapter for file storage.

Provides S3-compatible file storage using aioboto3.
Implements IFileStorage interface for dependency inversion.

File ID Format:
    Composite ID: "{session_id}:{uuid}"
    Example: "abc-123:def-456-ghi"

    This allows O(1) lookups by parsing session from file_id.
"""
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Optional, Tuple

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Separator for composite file IDs
FILE_ID_SEPARATOR = ":"


@dataclass
class MinIOConfig:
    """Configuration for MinIO storage."""
    endpoint: str = "minio:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    secure: bool = False
    bucket: str = "troise-uploads"
    retention_days: int = 1

    @classmethod
    def from_env(cls) -> "MinIOConfig":
        """Create config from environment variables."""
        return cls(
            endpoint=os.getenv("MINIO_ENDPOINT", "minio:9000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
            bucket=os.getenv("MINIO_BUCKET", "troise-uploads"),
            retention_days=int(os.getenv("MINIO_RETENTION_DAYS", "1")),
        )


class MinIOAdapter:
    """S3-compatible storage adapter using aioboto3.

    Implements IFileStorage interface for MinIO/S3.

    File ID Format:
        Uses composite IDs: "{session_id}:{uuid}"
        This enables O(1) lookups without caching or scanning.

    Features:
    - Async upload/download/delete operations
    - Automatic bucket creation with lifecycle policy
    - Session-scoped file organization
    - O(1) file lookups via composite IDs

    Example:
        adapter = MinIOAdapter(config)
        await adapter.initialize()

        # Upload returns composite file_id
        file_id = await adapter.upload(
            file_id="temp-uuid",  # Will be replaced with composite
            content=file_bytes,
            mimetype="application/pdf",
            session_id="session-456"
        )
        # file_id = "session-456:abc-123-def"

        content = await adapter.download(file_id)
    """

    def __init__(self, config: Optional[MinIOConfig] = None):
        """Initialize MinIO adapter.

        Args:
            config: MinIO configuration (uses env vars if None).
        """
        self._config = config or MinIOConfig.from_env()
        self._session = aioboto3.Session()
        self._initialized = False

        # Determine protocol
        protocol = "https" if self._config.secure else "http"
        self._endpoint_url = f"{protocol}://{self._config.endpoint}"

        # Configure retries and timeouts
        self._boto_config = Config(
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            connect_timeout=10,
            read_timeout=60,
            signature_version='s3v4',
        )

        logger.debug(f"MinIO adapter configured for {self._endpoint_url}")

    @property
    def _client_config(self) -> dict:
        """Get configuration dict for S3 client creation."""
        return {
            'endpoint_url': self._endpoint_url,
            'aws_access_key_id': self._config.access_key,
            'aws_secret_access_key': self._config.secret_key,
            'config': self._boto_config,
        }

    @staticmethod
    def make_file_id(session_id: str, uuid_part: str) -> str:
        """Create composite file ID from session and UUID.

        Args:
            session_id: Session identifier.
            uuid_part: UUID portion of the file ID.

        Returns:
            Composite file ID: "{session_id}:{uuid_part}"
        """
        return f"{session_id}{FILE_ID_SEPARATOR}{uuid_part}"

    @staticmethod
    def parse_file_id(file_id: str) -> Tuple[str, str]:
        """Parse composite file ID into session and UUID.

        Args:
            file_id: Composite file ID.

        Returns:
            Tuple of (session_id, uuid_part).

        Raises:
            ValueError: If file_id format is invalid.
        """
        if FILE_ID_SEPARATOR not in file_id:
            raise ValueError(
                f"Invalid file_id format: '{file_id}'. "
                f"Expected '{FILE_ID_SEPARATOR}' separator."
            )
        parts = file_id.split(FILE_ID_SEPARATOR, 1)
        return parts[0], parts[1]

    async def initialize(self) -> None:
        """Create bucket and set lifecycle policy.

        Should be called once at startup.
        """
        if self._initialized:
            return

        async with self._session.client('s3', **self._client_config) as s3:
            # Create bucket if it doesn't exist
            try:
                await s3.head_bucket(Bucket=self._config.bucket)
                logger.debug(f"Bucket '{self._config.bucket}' already exists")
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code in ('404', 'NoSuchBucket'):
                    await s3.create_bucket(Bucket=self._config.bucket)
                    logger.info(f"Created bucket '{self._config.bucket}'")
                else:
                    raise

            # Set lifecycle policy for automatic cleanup
            lifecycle_config = {
                "Rules": [{
                    "ID": f"expire-after-{self._config.retention_days}-days",
                    "Status": "Enabled",
                    "Filter": {"Prefix": ""},
                    "Expiration": {"Days": self._config.retention_days}
                }]
            }

            try:
                await s3.put_bucket_lifecycle_configuration(
                    Bucket=self._config.bucket,
                    LifecycleConfiguration=lifecycle_config
                )
                logger.info(
                    f"Set lifecycle policy: {self._config.retention_days} day retention"
                )
            except ClientError as e:
                logger.warning(f"Failed to set lifecycle policy: {e}")

        self._initialized = True

    async def upload(
        self,
        file_id: str,
        content: bytes,
        mimetype: str,
        session_id: str,
    ) -> str:
        """Upload file to storage.

        Args:
            file_id: UUID portion of the file identifier.
            content: Raw file bytes.
            mimetype: MIME type of the file.
            session_id: Session identifier for namespacing.

        Returns:
            Composite file_id: "{session_id}:{uuid}" for O(1) lookups.
        """
        if not self._initialized:
            await self.initialize()

        # Determine file extension from mimetype
        ext = self._get_extension(mimetype)

        # Storage key uses / for S3 path
        key = f"{session_id}/{file_id}{ext}"

        async with self._session.client('s3', **self._client_config) as s3:
            await s3.put_object(
                Bucket=self._config.bucket,
                Key=key,
                Body=content,
                ContentType=mimetype,
            )

        # Return composite file_id for O(1) lookups
        composite_id = self.make_file_id(session_id, file_id)
        logger.debug(f"Uploaded {composite_id} to {key} ({len(content)} bytes)")
        return composite_id

    def _build_key_prefix(self, file_id: str) -> str:
        """Build S3 key prefix from composite file_id.

        Args:
            file_id: Composite file ID.

        Returns:
            S3 key prefix (without extension).
        """
        session_id, uuid_part = self.parse_file_id(file_id)
        return f"{session_id}/{uuid_part}"

    async def download(self, file_id: str) -> bytes:
        """Download file from storage.

        Args:
            file_id: Composite file ID "{session_id}:{uuid}".

        Returns:
            Raw file bytes.

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file_id format is invalid.
        """
        if not self._initialized:
            await self.initialize()

        key_prefix = self._build_key_prefix(file_id)

        async with self._session.client('s3', **self._client_config) as s3:
            # List objects with prefix to find exact key (handles extension)
            response = await s3.list_objects_v2(
                Bucket=self._config.bucket,
                Prefix=key_prefix,
                MaxKeys=1,
            )

            contents = response.get('Contents', [])
            if not contents:
                raise FileNotFoundError(f"File not found: {file_id}")

            key = contents[0]['Key']

            try:
                response = await s3.get_object(
                    Bucket=self._config.bucket,
                    Key=key,
                )
                content = await response['Body'].read()
                logger.debug(f"Downloaded {file_id} ({len(content)} bytes)")
                return content
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == 'NoSuchKey':
                    raise FileNotFoundError(f"File not found: {file_id}")
                raise

    async def delete(self, file_id: str) -> bool:
        """Delete file from storage.

        Args:
            file_id: Composite file ID "{session_id}:{uuid}".

        Returns:
            True if file was deleted, False if not found.
        """
        if not self._initialized:
            await self.initialize()

        try:
            key_prefix = self._build_key_prefix(file_id)
        except ValueError:
            return False

        async with self._session.client('s3', **self._client_config) as s3:
            # List objects with prefix to find exact key
            response = await s3.list_objects_v2(
                Bucket=self._config.bucket,
                Prefix=key_prefix,
                MaxKeys=1,
            )

            contents = response.get('Contents', [])
            if not contents:
                return False

            key = contents[0]['Key']

            try:
                await s3.delete_object(
                    Bucket=self._config.bucket,
                    Key=key,
                )
                logger.debug(f"Deleted {file_id}")
                return True
            except ClientError:
                return False

    async def exists(self, file_id: str) -> bool:
        """Check if file exists in storage.

        Args:
            file_id: Composite file ID "{session_id}:{uuid}".

        Returns:
            True if file exists.
        """
        if not self._initialized:
            await self.initialize()

        try:
            key_prefix = self._build_key_prefix(file_id)
        except ValueError:
            return False

        async with self._session.client('s3', **self._client_config) as s3:
            response = await s3.list_objects_v2(
                Bucket=self._config.bucket,
                Prefix=key_prefix,
                MaxKeys=1,
            )
            return len(response.get('Contents', [])) > 0

    async def cleanup_session(self, session_id: str) -> int:
        """Delete all files for a session.

        Args:
            session_id: Session identifier to clean up.

        Returns:
            Number of files deleted.
        """
        if not self._initialized:
            await self.initialize()

        deleted = 0
        prefix = f"{session_id}/"

        async with self._session.client('s3', **self._client_config) as s3:
            # List objects with prefix
            paginator = s3.get_paginator('list_objects_v2')
            async for page in paginator.paginate(
                Bucket=self._config.bucket,
                Prefix=prefix,
            ):
                contents = page.get('Contents', [])
                if not contents:
                    continue

                # Delete in batches
                objects = [{'Key': obj['Key']} for obj in contents]
                await s3.delete_objects(
                    Bucket=self._config.bucket,
                    Delete={'Objects': objects}
                )
                deleted += len(objects)

        logger.info(f"Cleaned up session {session_id}: {deleted} files deleted")
        return deleted

    async def health_check(self) -> bool:
        """Check if MinIO is accessible.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            async with self._session.client('s3', **self._client_config) as s3:
                await s3.list_buckets()
            return True
        except Exception as e:
            logger.warning(f"MinIO health check failed: {e}")
            return False

    @staticmethod
    def _get_extension(mimetype: str) -> str:
        """Get file extension from MIME type.

        Args:
            mimetype: MIME type string.

        Returns:
            File extension including dot (e.g., ".pdf").
        """
        mime_to_ext = {
            'application/pdf': '.pdf',
            'text/plain': '.txt',
            'text/markdown': '.md',
            'text/csv': '.csv',
            'image/png': '.png',
            'image/jpeg': '.jpg',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'application/json': '.json',
            'application/xml': '.xml',
            'text/html': '.html',
        }
        return mime_to_ext.get(mimetype, '')

    def __repr__(self) -> str:
        return f"MinIOAdapter(endpoint={self._endpoint_url}, bucket={self._config.bucket})"
