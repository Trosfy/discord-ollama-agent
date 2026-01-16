"""Artifact extraction chain of responsibility.

Tries handlers in order until one succeeds:
1. ToolArtifactHandler - Check if tools created files (best)
2. LLMExtractionHandler - Use larger model to extract (fallback)
3. RegexFallbackHandler - Pattern match code blocks (last resort)
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.executor import ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class Artifact:
    """Extracted file artifact."""
    filename: str
    content: str
    source: str  # "tool", "llm_extraction", "regex"
    confidence: float = 1.0  # 1.0 for tool, 0.8 for LLM, 0.5 for regex
    filepath: Optional[str] = None  # Full path if saved
    metadata: Dict[str, Any] = field(default_factory=dict)


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

        Args:
            result: Execution result from skill/agent.
            artifact_requested: Whether user asked for file output.
            expected_filename: Expected filename from preprocessing.

        Returns:
            List of extracted artifacts (may be empty).
        """
        if not artifact_requested:
            return []  # User didn't ask for file output

        for handler in self._handlers:
            if handler.can_handle(result):
                try:
                    artifacts = await handler.handle(result)
                    if artifacts:
                        logger.info(
                            f"Extracted {len(artifacts)} artifact(s) via {handler.__class__.__name__}"
                        )

                        # Apply expected filename if not set
                        if expected_filename and len(artifacts) == 1:
                            if artifacts[0].filename.startswith("output"):
                                artifacts[0].filename = expected_filename

                        return artifacts
                except Exception as e:
                    logger.warning(f"Handler {handler.__class__.__name__} failed: {e}")
                    continue

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
