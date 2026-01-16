"""Content extractor interface and result types."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol


@dataclass
class ExtractionResult:
    """Result from content extraction."""
    text: str
    extractor_name: str
    status: str  # "success" | "error" | "partial"
    error_message: Optional[str] = None
    metadata: Dict = field(default_factory=dict)  # word_count, page_count, etc.


class IContentExtractor(Protocol):
    """Protocol for content extractors.

    Extractors are responsible for extracting text content from files
    of specific MIME types.

    SOLID: Interface Segregation - focused on extraction only.
    """

    @property
    def supported_mimetypes(self) -> List[str]:
        """List of MIME types this extractor handles."""
        ...

    async def extract(self, file_path: str, mimetype: str) -> ExtractionResult:
        """Extract text content from a file.

        Args:
            file_path: Path to the file to extract.
            mimetype: MIME type of the file.

        Returns:
            ExtractionResult with text content and metadata.
        """
        ...
