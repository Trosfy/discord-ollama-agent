"""File storage interface for dependency inversion."""
from typing import Protocol, Optional


class IFileStorage(Protocol):
    """Interface for file storage operations.

    Provides abstraction over object storage backends (MinIO, S3, etc.)
    so components can upload/download files without knowing backend details.

    Follows Interface Segregation - focused on file operations only.

    Example:
        storage = container.resolve(IFileStorage)
        file_id = await storage.upload(
            file_id="abc-123",
            content=file_bytes,
            mimetype="application/pdf",
            session_id="session-456"
        )
        content = await storage.download("abc-123")
    """

    async def upload(
        self,
        file_id: str,
        content: bytes,
        mimetype: str,
        session_id: str,
    ) -> str:
        """Upload file to storage.

        Args:
            file_id: Unique identifier for the file.
            content: Raw file bytes.
            mimetype: MIME type of the file.
            session_id: Session identifier for namespacing.

        Returns:
            Storage key/path where file was stored.
        """
        ...

    async def download(self, file_id: str) -> bytes:
        """Download file from storage.

        Args:
            file_id: File identifier to download.

        Returns:
            Raw file bytes.

        Raises:
            FileNotFoundError: If file does not exist.
        """
        ...

    async def delete(self, file_id: str) -> bool:
        """Delete file from storage.

        Args:
            file_id: File identifier to delete.

        Returns:
            True if file was deleted, False if not found.
        """
        ...

    async def exists(self, file_id: str) -> bool:
        """Check if file exists in storage.

        Args:
            file_id: File identifier to check.

        Returns:
            True if file exists.
        """
        ...
