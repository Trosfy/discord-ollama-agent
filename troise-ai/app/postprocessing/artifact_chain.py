"""Artifact extraction chain of responsibility.

Tries handlers in order until one succeeds:
1. ToolArtifactHandler - Check if tools created files (best)
2. LLMExtractionHandler - Use larger model to extract (fallback)
3. RegexFallbackHandler - Pattern match code blocks (last resort)
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.executor import ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class Artifact:
    """Extracted file artifact - supports text and binary.

    Designed to support both text artifacts (code files) and
    binary artifacts (images from future FLUX integration).

    Attributes:
        filename: Output filename (e.g., "output.cpp", "generated.png").
        content: Text or binary content.
        content_type: MIME type - "text/plain", "image/png", etc.
        source: Extraction method - "tool", "llm_extraction", "regex", "flux".
        confidence: Extraction confidence (1.0=tool, 0.8=LLM, 0.5=regex).
        filepath: Full filesystem path if saved.
        metadata: Additional metadata (language, dimensions, etc.).
    """
    filename: str
    content: Union[str, bytes]
    source: str  # "tool", "llm_extraction", "regex", "flux" (future)
    content_type: str = "text/plain"  # MIME type
    confidence: float = 1.0  # 1.0 for tool, 0.8 for LLM, 0.5 for regex
    filepath: Optional[str] = None  # Full path if saved
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_binary(self) -> bool:
        """Check if content is binary (e.g., image)."""
        return isinstance(self.content, bytes)


class IArtifactHandler(Protocol):
    """Single handler in the extraction chain."""

    def can_handle(self, result: "ExecutionResult") -> bool:
        """Check if this handler can process the result."""
        ...

    async def handle(self, result: "ExecutionResult") -> List[Artifact]:
        """Attempt to extract artifacts from result."""
        ...


class ArtifactExtractionChain:
    """Try handlers in order until one succeeds.

    Chain order:
    1. ToolArtifactHandler - Check if tools created files (best)
    2. LLMExtractionHandler - Use larger model to extract (fallback)
    3. RegexFallbackHandler - Pattern match code blocks (last resort)

    Example:
        chain = ArtifactExtractionChain([
            ToolArtifactHandler(),
            LLMExtractionHandler(llm_provider),
            RegexFallbackHandler(),
        ])

        artifacts = await chain.extract(result, artifact_requested=True)
    """

    def __init__(self, handlers: List[IArtifactHandler]):
        """Initialize chain with handlers.

        Args:
            handlers: List of handlers in priority order.
        """
        self._handlers = handlers

    async def extract(
        self,
        result: "ExecutionResult",
        artifact_requested: bool,
        expected_filename: Optional[str] = None,
    ) -> List[Artifact]:
        """Extract artifacts, trying each handler in order.

        Special handling for image artifacts:
        - ImageArtifactHandler always runs (images from generate_image tool)
        - Other handlers only run if artifact_requested is True

        Args:
            result: Execution result from skill/agent.
            artifact_requested: Whether user asked for file output.
            expected_filename: Expected filename from preprocessing.

        Returns:
            List of extracted artifacts (may be empty).
        """
        all_artifacts = []

        for handler in self._handlers:
            handler_name = handler.__class__.__name__

            # ImageArtifactHandler always runs - generated images should always be delivered
            # Other handlers only run if artifact_requested is True
            is_image_handler = handler_name == "ImageArtifactHandler"
            if not is_image_handler and not artifact_requested:
                continue

            if handler.can_handle(result):
                try:
                    artifacts = await handler.handle(result)
                    if artifacts:
                        logger.info(
                            f"Extracted {len(artifacts)} artifact(s) via {handler_name}"
                        )

                        # Apply expected filename if not set (for non-image artifacts)
                        if expected_filename and len(artifacts) == 1 and not is_image_handler:
                            if artifacts[0].filename.startswith("output"):
                                artifacts[0].filename = expected_filename

                        # For image handler, collect and continue (may have other artifacts)
                        if is_image_handler:
                            all_artifacts.extend(artifacts)
                            continue

                        # For other handlers, return immediately (chain of responsibility)
                        all_artifacts.extend(artifacts)
                        return all_artifacts
                except Exception as e:
                    logger.warning(f"Handler {handler_name} failed: {e}")
                    continue

        if all_artifacts:
            return all_artifacts

        logger.debug("No artifacts extracted from response")
        return []  # No artifacts found

    def add_handler(self, handler: IArtifactHandler, index: int = None):
        """Add a handler to the chain.

        Args:
            handler: Handler to add.
            index: Position in chain (default: end).
        """
        if index is None:
            self._handlers.append(handler)
        else:
            self._handlers.insert(index, handler)
