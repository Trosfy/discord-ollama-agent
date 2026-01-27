"""Strands hooks for TROISE AI."""
import json
import logging
from typing import TYPE_CHECKING

from strands.hooks import HookProvider, HookRegistry, AfterToolCallEvent

if TYPE_CHECKING:
    from .context import ExecutionContext

logger = logging.getLogger(__name__)


class SourceCaptureHook(HookProvider):
    """Captures URLs from web_fetch tool results ONLY.

    Why only web_fetch (not web_search)?
    - web_search returns search snippets - previews, not actual content
    - web_fetch returns actual page content - the source the LLM consumed
    - Only fetched pages should be cited as sources

    Stores structured source data in ExecutionContext.collected_sources
    for use by citation_formatter and other downstream agents.
    """

    def __init__(self, context: "ExecutionContext"):
        self._context = context

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(AfterToolCallEvent, self._capture_sources)

    def _capture_sources(self, event: AfterToolCallEvent) -> None:
        """Extract URL from web_fetch tool result only."""
        tool_name = event.tool_use.get("name", "")

        # ONLY capture web_fetch - these are actually read sources
        if tool_name != "web_fetch":
            return

        try:
            # Parse tool result JSON
            # web_fetch returns: {"url": ..., "title": ..., "chunks": [...]}
            result_text = event.result.get("content", [{}])[0].get("text", "{}")
            result_data = json.loads(result_text)

            url = result_data.get("url")
            title = result_data.get("title")

            if url:
                self._add_source(url=url, title=title)

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to extract source from web_fetch: {e}")

    def _add_source(self, url: str, title: str = None) -> None:
        """Add a source to collected_sources if not already present."""
        if not url:
            return

        # Dedupe by URL
        existing_urls = {s["url"] for s in self._context.collected_sources}
        if url not in existing_urls:
            self._context.collected_sources.append({
                "url": url,
                "title": title or url,
            })
            logger.debug(f"Captured source: {url}")


class ImageCaptureHook(HookProvider):
    """Captures file_id from generate_image tool results.

    Same pattern as SourceCaptureHook - uses AfterToolCallEvent to
    capture tool results and store in ExecutionContext.

    Stores image metadata in context.generated_images for later
    retrieval by ImageArtifactHandler.
    """

    def __init__(self, context: "ExecutionContext"):
        self._context = context

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(AfterToolCallEvent, self._capture_images)

    def _capture_images(self, event: AfterToolCallEvent) -> None:
        """Extract file_id from generate_image tool result."""
        tool_name = event.tool_use.get("name", "")
        logger.info(f"[HOOK] AfterToolCallEvent received for tool: {tool_name}")

        if tool_name != "generate_image":
            return

        # Log the raw event structure for debugging
        logger.info(f"[HOOK] generate_image event.result keys: {event.result.keys() if hasattr(event.result, 'keys') else type(event.result)}")
        logger.info(f"[HOOK] generate_image event.result: {str(event.result)[:500]}")

        try:
            # Parse tool result JSON (same structure as SourceCaptureHook)
            result_text = event.result.get("content", [{}])[0].get("text", "{}")
            result_data = json.loads(result_text)

            if not result_data.get("success"):
                return

            # Handle double-encoded JSON: outer wrapper has "content" field with inner JSON
            # Structure: {"success": true, "content": "{\"file_id\": \"...\", ...}"}
            inner_content = result_data.get("content")
            if isinstance(inner_content, str):
                # Parse the inner JSON string
                inner_data = json.loads(inner_content)
                file_id = inner_data.get("file_id")
                storage_key = inner_data.get("storage_key")
                # Use inner_data for metadata
                result_data = inner_data
                logger.info(f"[HOOK] Parsed inner content, file_id={file_id}")
            else:
                # Fallback: file_id at top level (direct structure)
                file_id = result_data.get("file_id")
                storage_key = result_data.get("storage_key")

            if file_id:
                self._context.generated_images.append({
                    "file_id": file_id,
                    "storage_key": storage_key,
                    "width": result_data.get("width", 1024),
                    "height": result_data.get("height", 1024),
                    "aspect_ratio": result_data.get("aspect_ratio", "1:1"),
                    "prompt_used": result_data.get("prompt_used", "")[:100],
                })
                logger.info(f"[HOOK] Captured generated image: {file_id}")

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to extract image from generate_image: {e}")
