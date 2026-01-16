"""Regex-based fallback artifact handler.

Last resort for when:
- Tool didn't work
- LLM extraction failed
- But there's clearly a code block in response

Pattern matches code blocks from response.
"""
import logging
import re
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.executor import ExecutionResult

from ..artifact_chain import Artifact
from ..sanitizer import ContentSanitizer

logger = logging.getLogger(__name__)


class RegexFallbackHandler:
    """Pattern match code blocks when LLM extraction fails.

    Last resort for when:
    - Tool didn't work
    - LLM extraction failed
    - But there's clearly a code block in response

    Lower confidence (0.5) as extraction is less reliable.

    Example:
        handler = RegexFallbackHandler()

        if handler.can_handle(result):
            artifacts = await handler.handle(result)
            # Returns artifacts from code blocks
    """

    CODE_BLOCK_PATTERN = r'```(\w*)\n(.*?)```'

    # Language to file extension mapping
    LANG_TO_EXT = {
        "python": "py",
        "javascript": "js",
        "typescript": "ts",
        "java": "java",
        "cpp": "cpp",
        "c": "c",
        "rust": "rs",
        "go": "go",
        "ruby": "rb",
        "php": "php",
        "sql": "sql",
        "bash": "sh",
        "shell": "sh",
        "sh": "sh",
        "json": "json",
        "yaml": "yml",
        "yml": "yml",
        "xml": "xml",
        "html": "html",
        "css": "css",
        "dockerfile": "Dockerfile",
        "makefile": "Makefile",
    }

    def __init__(self, sanitizer: Optional[ContentSanitizer] = None):
        """Initialize handler.

        Args:
            sanitizer: Content sanitizer for post-processing.
        """
        self._sanitizer = sanitizer or ContentSanitizer()

    def can_handle(self, result: "ExecutionResult") -> bool:
        """Check if result contains code blocks.

        Args:
            result: Execution result.

        Returns:
            True if code blocks are present.
        """
        return '```' in result.content

    async def handle(self, result: "ExecutionResult") -> List[Artifact]:
        """Extract artifacts from code blocks.

        Args:
            result: Execution result with code blocks.

        Returns:
            List of extracted artifacts.
        """
        matches = re.findall(
            self.CODE_BLOCK_PATTERN,
            result.content,
            re.DOTALL
        )

        if not matches:
            return []

        artifacts = []
        for i, (lang, content) in enumerate(matches):
            # Infer filename from language
            ext = self._lang_to_ext(lang or "txt")

            # Generate filename
            if len(matches) > 1:
                filename = f"output_{i + 1}.{ext}"
            else:
                filename = f"output.{ext}"

            # Handle special cases
            if lang.lower() in ("dockerfile", "makefile"):
                filename = lang.capitalize()

            # Sanitize content
            clean_content = self._sanitizer.sanitize(content, "code")

            if not clean_content.strip():
                continue  # Skip empty blocks

            artifacts.append(Artifact(
                filename=filename,
                content=clean_content,
                source="regex",
                confidence=0.5,  # Lower confidence
                metadata={
                    "language": lang or "unknown",
                    "block_index": i,
                },
            ))

            logger.debug(f"Extracted artifact via regex: {filename}")

        return artifacts

    def _lang_to_ext(self, lang: str) -> str:
        """Convert language identifier to file extension.

        Args:
            lang: Language identifier from code block.

        Returns:
            File extension.
        """
        return self.LANG_TO_EXT.get(lang.lower(), lang.lower() or "txt")
