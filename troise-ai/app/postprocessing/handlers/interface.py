"""Artifact handler interface."""
from typing import List, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.executor import ExecutionResult
    from app.postprocessing.artifact_chain import Artifact


class IArtifactHandler(Protocol):
    """Single handler in the extraction chain.

    Each handler checks if it can process the result,
    then attempts to extract artifacts.

    Chain order determines priority:
    1. ToolArtifactHandler - Best (tools created files)
    2. LLMExtractionHandler - Good (larger model extracts)
    3. RegexFallbackHandler - Last resort (pattern matching)
    """

    def can_handle(self, result: "ExecutionResult") -> bool:
        """Check if this handler can process the result.

        Args:
            result: Execution result from skill/agent.

        Returns:
            True if handler should attempt extraction.
        """
        ...

    async def handle(self, result: "ExecutionResult") -> List["Artifact"]:
        """Attempt to extract artifacts from result.

        Args:
            result: Execution result from skill/agent.

        Returns:
            List of extracted artifacts (empty if none found).
        """
        ...
