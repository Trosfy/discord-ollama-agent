"""Content filtering for streaming text."""
import re
from typing import Optional
import logging_client

logger = logging_client.setup_logger('fastapi')


class ThinkTagFilter:
    """
    Stateful filter to remove <think>...</think> tags with partial matching.

    Handles character-by-character streaming where tags may arrive as:
    '<', 't', 'h', 'i', 'n', 'k', '>'

    SOLID: Single Responsibility - think tag filtering only
    """

    OPEN_TAG = '<think>'
    CLOSE_TAG = '</think>'

    def __init__(self):
        """Initialize filter state."""
        self.inside_tag = False       # Currently inside <think>...</think>?
        self.partial_buffer = ""       # Buffers potential tag chars
        self.discard_buffer = ""       # Content discarded (for debugging)

    def process(self, chunk: str) -> str:
        """
        Filter chunk character-by-character with partial tag matching.

        Args:
            chunk: Input text (can be single char or multi-char)

        Returns:
            Filtered text (empty if inside tag or building tag)
        """
        output = []

        for char in chunk:
            self.partial_buffer += char

            if self.inside_tag:
                # Inside <think>, looking for </think>
                if self._matches_partial(self.CLOSE_TAG):
                    if self.partial_buffer == self.CLOSE_TAG:
                        # Complete closing tag!
                        self.inside_tag = False
                        self.partial_buffer = ""
                        output.append(' ')  # Prevent word concatenation
                    # else: Still building closing tag, keep buffering
                else:
                    # Buffer doesn't match closing tag - discard and reset
                    self.discard_buffer += self.partial_buffer
                    self.partial_buffer = ""

            else:
                # Outside tags, looking for <think>
                if self._matches_partial(self.OPEN_TAG):
                    if self.partial_buffer == self.OPEN_TAG:
                        # Complete opening tag!
                        self.inside_tag = True
                        self.partial_buffer = ""
                    # else: Still building opening tag, keep buffering
                else:
                    # Buffer doesn't match opening tag - flush as normal text
                    output.append(self.partial_buffer)
                    self.partial_buffer = ""

        return ''.join(output)

    def _matches_partial(self, tag: str) -> bool:
        """
        Check if partial_buffer is a valid prefix of tag.

        Examples:
            tag = '<think>'
            '<' → True
            '<t' → True
            '<think>' → True
            '<x' → False

        Args:
            tag: Full tag to match

        Returns:
            True if partial_buffer could be the start of this tag
        """
        return tag.startswith(self.partial_buffer)

    def flush(self) -> str:
        """
        Flush any remaining buffered content.

        Call at end of streaming to ensure no data loss.

        Returns:
            Buffered content (if not inside a tag)
        """
        result = ""
        if not self.inside_tag and self.partial_buffer:
            result = self.partial_buffer
            self.partial_buffer = ""
        return result

    def get_stats(self) -> dict:
        """Get filtering statistics."""
        return {
            'inside_tag': self.inside_tag,
            'buffer_size': len(self.partial_buffer),
            'discarded_size': len(self.discard_buffer)
        }


class SpacingFixer:
    """
    Fixes spacing artifacts in streamed content.

    SOLID: Single Responsibility - spacing correction only
    """

    # Compile regex patterns once for performance
    MARKDOWN_LINK_SPACING = re.compile(r'([a-z])(\[)')
    INLINE_CODE_SPACING = re.compile(r'([a-z])(`)')
    MULTIPLE_SPACES = re.compile(r' +')

    def process(self, text: str) -> str:
        """
        Apply spacing fixes to text.

        Args:
            text: Input text

        Returns:
            Text with corrected spacing
        """
        if not text:
            return text

        # Fix spacing before markdown links: word[link] -> word [link]
        text = self.MARKDOWN_LINK_SPACING.sub(r'\1 \2', text)

        # Fix spacing before inline code: word`code` -> word `code`
        text = self.INLINE_CODE_SPACING.sub(r'\1 \2', text)

        # Collapse multiple spaces (preserve newlines)
        text = self.MULTIPLE_SPACES.sub(' ', text)

        return text


class StreamFilter:
    """
    Composite filter that applies multiple transformations.

    SOLID: Composition over inheritance, Open/Closed Principle
    """

    def __init__(
        self,
        enable_think_filter: bool = True,
        enable_spacing_fixer: bool = True
    ):
        """
        Initialize composite filter.

        Args:
            enable_think_filter: Enable <think> tag removal
            enable_spacing_fixer: Enable spacing fixes
        """
        self.think_filter = ThinkTagFilter() if enable_think_filter else None
        self.spacing_fixer = SpacingFixer() if enable_spacing_fixer else None

    def apply(self, text: str) -> str:
        """
        Apply all enabled filters.

        Args:
            text: Input text

        Returns:
            Filtered text
        """
        # Apply think tag filter first
        if self.think_filter:
            text = self.think_filter.process(text)

        # Then apply spacing fixes (only if we have content)
        if text and self.spacing_fixer:
            text = self.spacing_fixer.process(text)

        return text

    def flush(self) -> str:
        """Flush all stateful filters."""
        if self.think_filter:
            return self.think_filter.flush()
        return ""

    def get_stats(self) -> dict:
        """Get statistics from all filters."""
        stats = {}
        if self.think_filter:
            stats['think_filter'] = self.think_filter.get_stats()
        return stats
