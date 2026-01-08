"""File context builder for message enrichment."""
from typing import List, Dict
import logging_client

logger = logging_client.setup_logger('fastapi')


class FileContextBuilder:
    """
    Builds file context for message enrichment.

    SOLID: Single Responsibility - format file references for LLM context

    This class is the preprocessing equivalent of StreamProcessor - it takes
    file references and formats them into a message that includes all file
    content that's already been extracted (OCR, transcription, etc).
    """

    def append_to_message(self, message: str, file_refs: List[Dict]) -> str:
        """
        Append file references and their extracted content to message.

        This creates the COMPLETE message that the router and LLM will see,
        including all file content that was extracted during upload.

        Args:
            message: Original user message (e.g., "what is this")
            file_refs: List of file reference dicts with:
                - filename: str
                - content_type: str (MIME type)
                - extracted_content: str (already extracted via OCR/etc)
                - file_id: str
                - storage_path: str

        Returns:
            Enriched message with file context (e.g., "what is this\n\n[Image: ...]")

        Example:
            Input:
                message="explain this code"
                file_refs=[{
                    'filename': 'screenshot.png',
                    'content_type': 'image/png',
                    'extracted_content': 'function quicksort(arr) { ... }'
                }]

            Output:
                "explain this code

                [Attached file: screenshot.png (image/png)]
                Content:
                function quicksort(arr) { ... }"
        """
        if not file_refs:
            return message

        logger.info(f"📎 Building context for {len(file_refs)} file(s)")

        file_summaries = [
            self._format_file_reference(ref)
            for ref in file_refs
        ]

        enriched_message = message + '\n'.join(file_summaries)

        logger.debug(
            f"📝 Enriched message: {len(message)} → {len(enriched_message)} chars "
            f"({len(enriched_message) - len(message)} added from files)"
        )

        return enriched_message

    def _format_file_reference(self, file_ref: Dict) -> str:
        """
        Format single file reference for message context.

        Args:
            file_ref: Dict with filename, content_type, extracted_content

        Returns:
            Formatted file summary string
        """
        filename = file_ref.get('filename', 'unknown')
        content_type = file_ref.get('content_type', 'unknown')

        summary = f"\n\n[Attached file: {filename} ({content_type})]"

        # Append extracted content if available
        extracted = file_ref.get('extracted_content')
        if extracted and self._is_valid_content(extracted):
            summary += f"\nContent:\n{extracted}"
        else:
            summary += "\n[Content extraction failed or unavailable]"

        return summary

    def _is_valid_content(self, content: str) -> bool:
        """
        Check if extracted content is valid (not error message).

        Args:
            content: Extracted content string

        Returns:
            True if content is valid, False if error message
        """
        if not content:
            return False

        error_messages = [
            '[OCR service not available]',
            '[Processing failed]',
            '[Content extraction failed or unavailable]'
        ]

        return content not in error_messages

    def get_file_summary(self, file_refs: List[Dict]) -> str:
        """
        Get human-readable summary of files for logging.

        Args:
            file_refs: List of file reference dicts

        Returns:
            Summary string (e.g., "2 images, 1 PDF")
        """
        if not file_refs:
            return "No files"

        type_counts = {}
        for ref in file_refs:
            content_type = ref.get('content_type', 'unknown')
            category = self._categorize_type(content_type)
            type_counts[category] = type_counts.get(category, 0) + 1

        parts = [f"{count} {category}" for category, count in type_counts.items()]
        return ", ".join(parts)

    def _categorize_type(self, content_type: str) -> str:
        """Categorize MIME type for human readability."""
        if content_type.startswith('image/'):
            return 'image'
        elif content_type.startswith('audio/'):
            return 'audio'
        elif content_type.startswith('video/'):
            return 'video'
        elif content_type == 'application/pdf':
            return 'PDF'
        elif content_type.startswith('text/'):
            return 'text file'
        else:
            return 'file'
