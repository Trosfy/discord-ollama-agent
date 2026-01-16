"""Discord response formatter.

Handles:
- Message splitting at 2000 char limit
- Code block preservation during splits
- Markdown compatibility
"""
from typing import Any, Dict, List, Optional

from .interface import IResponseFormatter, FormattedResponse


class DiscordResponseFormatter:
    """Format responses for Discord.

    Handles:
    - Message splitting at 2000 char limit
    - Code block preservation during splits
    - Markdown compatibility

    Example:
        formatter = DiscordResponseFormatter()

        formatted = formatter.format(long_content)
        # formatted.messages may be ["Part 1...", "Part 2...", ...]
    """

    MAX_LENGTH = 2000
    SAFE_LENGTH = 1900  # Leave buffer for formatting

    @property
    def interface_name(self) -> str:
        return "discord"

    def format(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FormattedResponse:
        """Format content for Discord.

        Args:
            content: Content to format.
            metadata: Optional metadata.

        Returns:
            FormattedResponse with split messages.
        """
        if len(content) <= self.MAX_LENGTH:
            return FormattedResponse(messages=[content])

        messages = self._split_message(content)
        return FormattedResponse(
            messages=messages,
            metadata={"parts": len(messages)},
        )

    def _split_message(self, content: str) -> List[str]:
        """Smart splitting preserving code blocks.

        Args:
            content: Long content to split.

        Returns:
            List of message parts.
        """
        messages = []
        remaining = content

        while remaining:
            if len(remaining) <= self.SAFE_LENGTH:
                messages.append(remaining)
                break

            # Check if we're inside a code block
            code_block_start = remaining.rfind('```', 0, self.SAFE_LENGTH)
            code_block_end = remaining.rfind('```', code_block_start + 3, self.SAFE_LENGTH) if code_block_start >= 0 else -1

            # If we're inside an unclosed code block, close it before split
            in_code_block = code_block_start >= 0 and code_block_end < 0

            # Find best split point
            split_point = self._find_split_point(remaining, in_code_block)

            if in_code_block:
                # Close code block before split, reopen after
                part = remaining[:split_point] + "\n```"
                messages.append(part)

                # Find the language specifier to reopen
                lang_match = remaining[code_block_start:code_block_start + 50]
                lang_end = lang_match.find('\n')
                lang = lang_match[3:lang_end] if lang_end > 3 else ""

                remaining = f"```{lang}\n" + remaining[split_point:].lstrip()
            else:
                messages.append(remaining[:split_point])
                remaining = remaining[split_point:].lstrip()

        return messages

    def _find_split_point(self, text: str, in_code_block: bool = False) -> int:
        """Find best place to split text.

        Priority: paragraph > line > sentence > word

        Args:
            text: Text to find split point in.
            in_code_block: Whether currently in a code block.

        Returns:
            Split point index.
        """
        limit = self.SAFE_LENGTH

        if in_code_block:
            # In code blocks, prefer line breaks
            line_break = text.rfind('\n', 0, limit)
            if line_break > limit // 2:
                return line_break
            return limit

        # Try paragraph break
        para_break = text.rfind('\n\n', 0, limit)
        if para_break > limit // 2:
            return para_break

        # Try line break
        line_break = text.rfind('\n', 0, limit)
        if line_break > limit // 2:
            return line_break

        # Try sentence
        for punct in ['. ', '! ', '? ']:
            sent_break = text.rfind(punct, 0, limit)
            if sent_break > limit // 2:
                return sent_break + 1

        # Try word
        word_break = text.rfind(' ', 0, limit)
        if word_break > 0:
            return word_break

        # Hard split
        return limit
