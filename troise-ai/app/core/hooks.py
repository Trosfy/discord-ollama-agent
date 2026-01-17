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
