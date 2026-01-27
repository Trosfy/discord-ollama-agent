"""Image artifact handler for generate_image tool results.

Fetches generated images from storage and returns them as artifacts
for delivery to clients (Discord, Web, etc.) via WebSocket.
"""
import logging
from typing import Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.executor import ExecutionResult
    from app.core.context import ExecutionContext
    from app.core.interfaces.storage import IFileStorage

from ..artifact_chain import Artifact

logger = logging.getLogger(__name__)


class ImageArtifactHandler:
    """Extract image artifacts from context.generated_images.

    Images are captured by ImageCaptureHook during agent execution.
    This handler fetches the actual bytes from storage and returns
    them as Artifacts for delivery via WebSocket.

    Example:
        handler = ImageArtifactHandler(storage=minio_client)
        handler.set_context(context)  # Set by ResponseHandler

        if handler.can_handle(result):
            artifacts = await handler.handle(result)
            # Returns image artifacts from context.generated_images
    """

    def __init__(self, storage: "IFileStorage"):
        """Initialize with storage service.

        Args:
            storage: File storage service (MinIO) for fetching images.
        """
        self._storage = storage
        self._context: "ExecutionContext" = None

    def set_context(self, context: "ExecutionContext") -> None:
        """Set context for this extraction (called by ResponseHandler).

        Args:
            context: ExecutionContext with generated_images from ImageCaptureHook.
        """
        self._context = context

    def can_handle(self, result: "ExecutionResult") -> bool:
        """Check if context has generated images.

        Args:
            result: Execution result (not used - we check context instead).

        Returns:
            True if context has generated_images.
        """
        if self._context is None:
            return False
        return bool(self._context.generated_images)

    async def handle(self, result: "ExecutionResult") -> List[Artifact]:
        """Create reference artifacts for generated images.

        Instead of fetching bytes from storage, creates artifacts with
        storage_key references. Each interface fetches the file their own way.

        Args:
            result: Execution result (not used - we read from context).

        Returns:
            List of image reference artifacts.
        """
        if self._context is None or not self._context.generated_images:
            logger.info("[IMG_HANDLER] No context or no generated_images - skipping")
            return []

        artifacts = []

        for img_data in self._context.generated_images:
            file_id = img_data.get("file_id")
            storage_key = img_data.get("storage_key")

            if not storage_key and not file_id:
                continue

            # Generate filename from file_id
            filename = f"generated_{file_id[:8]}.png"

            # Create artifact with REFERENCE only (no bytes)
            # Interface will fetch from MinIO using storage_key
            artifacts.append(Artifact(
                filename=filename,
                content=b"",  # Empty - interface will fetch
                content_type="image/png",
                source="generate_image",
                confidence=1.0,  # Tool-generated = high confidence
                metadata={
                    **img_data,
                    "storage_key": storage_key,  # Interface uses this to fetch
                },
            ))

            logger.info(f"[IMG_HANDLER] Created reference artifact: {filename}, storage_key={storage_key}")

        return artifacts
