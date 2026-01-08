"""
Extension orchestrator for managing file operation extensions.

Implements Single Responsibility Principle:
- Only responsible for coordinating extensions
- Doesn't know about Discord/Slack/platform specifics
- Depends on IFileExtension interface (Dependency Inversion)
"""
import sys
sys.path.insert(0, '/shared')

from app.extensions.interface import IFileExtension
from strands.types.tools import ToolResult
from typing import Dict, List
import logging_client

logger = logging_client.setup_logger('extension-orchestrator')


class ExtensionOrchestrator:
    """
    Coordinates POST-PROCESSING extensions only.

    Follows SOLID Principles:
    - Single Responsibility: Only coordinates post-processing extensions
    - Dependency Inversion: Depends on IFileExtension interface
    - Open/Closed: Open for new extensions, closed for modification

    POST-PROCESSING ONLY:
    - Handles file_write results (artifact registration)
    - NO preprocessing (that's FileExtractionRouter's job)
    - NO file_read enrichment (agent shouldn't read files during runtime)

    Extensions are processed in order:
    1. DiscordFileExtension (register artifacts for Discord upload)
    2. Future extensions (Slack, Web, etc.)
    """

    def __init__(self, extensions: List[IFileExtension]):
        """
        Initialize orchestrator with list of POST-PROCESSING extensions.

        Args:
            extensions: List of IFileExtension implementations for post-processing
                       Example: [DiscordFileExtension()]
        """
        self.extensions = extensions
        logger.info(f"🔌 ExtensionOrchestrator initialized with {len(extensions)} extension(s)")

        # Log extension names for debugging
        for i, ext in enumerate(extensions):
            ext_name = ext.__class__.__name__
            logger.info(f"   {i+1}. {ext_name}")

    def handle_file_write(
        self,
        tool_result: ToolResult,
        request_context: Dict
    ) -> None:
        """
        Process file_write through all POST-PROCESSING extensions for artifact registration.

        Extensions handle file_write independently (not chained).
        Each extension can:
        - Register artifacts for platform upload
        - Add platform-specific metadata
        - Trigger platform-specific notifications

        Example:
        1. DiscordFileExtension → Registers artifact in request_context['artifacts_created']

        Args:
            tool_result: Result from Strands file_write
            request_context: Request context dict (modified in-place)

        Returns:
            None (extensions modify request_context in-place)

        Note: If an extension fails, logs error and continues with other extensions
        """
        for extension in self.extensions:
            ext_name = extension.__class__.__name__
            try:
                logger.debug(f"🔄 Processing file_write through {ext_name}")
                extension.on_file_write(tool_result, request_context)
            except Exception as e:
                logger.error(
                    f"❌ Extension error in {ext_name}.on_file_write: {e}",
                    exc_info=True
                )
                # Continue with other extensions despite error

    def get_extension_count(self) -> int:
        """Get number of registered extensions."""
        return len(self.extensions)

    def get_extension_names(self) -> List[str]:
        """Get list of extension class names (for debugging)."""
        return [ext.__class__.__name__ for ext in self.extensions]
