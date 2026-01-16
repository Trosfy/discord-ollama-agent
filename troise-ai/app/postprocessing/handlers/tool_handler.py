"""Tool-based artifact handler.

Checks tool_calls for write_file results.
This is the BEST path - agent used tools correctly.
Works with large models (70B+) reliably.
"""
import logging
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.executor import ExecutionResult

from ..artifact_chain import Artifact

logger = logging.getLogger(__name__)


class ToolArtifactHandler:
    """Check tool_calls for write_file results.

    This is the BEST path - agent used tools correctly.
    Works with large models (70B+) reliably.

    Example:
        handler = ToolArtifactHandler()

        if handler.can_handle(result):
            artifacts = await handler.handle(result)
            # Returns artifacts from write_file tool calls
    """

    def can_handle(self, result: "ExecutionResult") -> bool:
        """Check if result has tool calls.

        Args:
            result: Execution result.

        Returns:
            True if result has tool_calls.
        """
        return bool(result.tool_calls)

    async def handle(self, result: "ExecutionResult") -> List[Artifact]:
        """Extract artifacts from write_file tool calls.

        Args:
            result: Execution result with tool_calls.

        Returns:
            List of artifacts from write_file calls.
        """
        artifacts = []

        for call in result.tool_calls or []:
            tool_name = call.get("tool_name") or call.get("name", "")

            # Check for write_file tool
            if tool_name in ("write_file", "save_file", "create_file"):
                tool_result = call.get("result", {})

                if tool_result.get("success"):
                    filename = tool_result.get("filename", "output.txt")
                    filepath = tool_result.get("filepath")
                    content = tool_result.get("content", "")

                    artifacts.append(Artifact(
                        filename=filename,
                        filepath=filepath,
                        content=content,
                        source="tool",
                        confidence=1.0,
                        metadata={
                            "tool_name": tool_name,
                            "tool_call_id": call.get("id"),
                        },
                    ))

                    logger.debug(f"Extracted artifact from tool: {filename}")

        return artifacts
