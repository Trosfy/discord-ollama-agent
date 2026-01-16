"""File extraction router for preprocessing.

Routes files to appropriate extractors and stores content
for tool access. Uses session-scoped storage to prevent
data collision between WebSocket sessions.
"""
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

from .extractors.interface import IContentExtractor, ExtractionResult

logger = logging.getLogger(__name__)


@dataclass
class FileRef:
    """Reference to an uploaded file."""
    file_id: str
    filename: str
    mimetype: str
    word_count: int = 0
    status: str = "pending"  # "pending", "success", "error", "partial"
    error_message: Optional[str] = None


@dataclass
class FileContent:
    """Stored file content with metadata."""
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class FileExtractionRouter:
    """Routes files to extractors, stores content for tool access.

    SOLID: Open/Closed - add new extractors without modifying router.

    Stores extracted content in a session-scoped file store passed
    from ExecutionContext to prevent data collision between sessions.

    Example:
        router = FileExtractionRouter()
        router.register(TextExtractor())
        router.register(PDFExtractor())

        # Process file with session-scoped storage
        ref = await router.process_file(
            "document.pdf",
            "application/pdf",
            context.file_store
        )

        # Access content via file_store
        content = context.file_store[ref.file_id]["content"]
    """

    def __init__(self):
        self._extractors: Dict[str, IContentExtractor] = {}

    def register(self, extractor: IContentExtractor) -> None:
        """Register an extractor for its supported MIME types.

        Args:
            extractor: Content extractor to register.
        """
        for mimetype in extractor.supported_mimetypes:
            self._extractors[mimetype] = extractor
            logger.debug(f"Registered extractor for {mimetype}")

    def get_extractor(self, mimetype: str) -> Optional[IContentExtractor]:
        """Get extractor for a MIME type.

        Args:
            mimetype: MIME type to find extractor for.

        Returns:
            Extractor if found, None otherwise.
        """
        # Try exact match first
        if mimetype in self._extractors:
            return self._extractors[mimetype]

        # Try wildcard match (e.g., text/* for text/plain)
        base_type = mimetype.split("/")[0] + "/*"
        return self._extractors.get(base_type)

    async def process_file(
        self,
        file_path: str,
        mimetype: str,
        file_store: Dict[str, Dict[str, Any]],
    ) -> FileRef:
        """Extract content from file and store for tool access.

        Args:
            file_path: Path to the file to process.
            mimetype: MIME type of the file.
            file_store: Session-scoped storage (from ExecutionContext).

        Returns:
            FileRef with file_id for later access.
        """
        file_id = str(uuid.uuid4())
        filename = Path(file_path).name

        extractor = self.get_extractor(mimetype)
        if not extractor:
            logger.warning(f"No extractor for {mimetype}, storing empty content")
            file_store[file_id] = {
                "content": "",
                "metadata": {"mimetype": mimetype, "filename": filename},
            }
            return FileRef(
                file_id=file_id,
                filename=filename,
                mimetype=mimetype,
                word_count=0,
                status="error",
                error_message=f"No extractor for MIME type: {mimetype}",
            )

        try:
            result = await extractor.extract(file_path, mimetype)

            # Store in session-scoped file store
            file_store[file_id] = {
                "content": result.text,
                "metadata": {
                    **result.metadata,
                    "mimetype": mimetype,
                    "filename": filename,
                    "extractor": result.extractor_name,
                },
            }

            word_count = len(result.text.split()) if result.text else 0

            return FileRef(
                file_id=file_id,
                filename=filename,
                mimetype=mimetype,
                word_count=word_count,
                status=result.status,
                error_message=result.error_message,
            )

        except Exception as e:
            logger.error(f"Extraction failed for {file_path}: {e}")
            file_store[file_id] = {
                "content": "",
                "metadata": {"mimetype": mimetype, "filename": filename, "error": str(e)},
            }
            return FileRef(
                file_id=file_id,
                filename=filename,
                mimetype=mimetype,
                word_count=0,
                status="error",
                error_message=str(e),
            )

    async def process_files(
        self,
        files: List[Dict[str, str]],
        file_store: Dict[str, Dict[str, Any]],
    ) -> List[FileRef]:
        """Process multiple files.

        Args:
            files: List of dicts with "path" and "mimetype" keys.
            file_store: Session-scoped storage.

        Returns:
            List of FileRef objects.
        """
        refs = []
        for file_info in files:
            ref = await self.process_file(
                file_info["path"],
                file_info["mimetype"],
                file_store,
            )
            refs.append(ref)
        return refs

    def get_content(
        self,
        file_id: str,
        file_store: Dict[str, Dict[str, Any]],
    ) -> Optional[str]:
        """Get content for a file ID from session storage.

        Called by read_file tool.

        Args:
            file_id: File ID to retrieve.
            file_store: Session-scoped storage.

        Returns:
            File content if found, None otherwise.
        """
        stored = file_store.get(file_id)
        return stored.get("content") if stored else None
