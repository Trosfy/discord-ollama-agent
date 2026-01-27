"""Web interface WebSocket message builder."""
from typing import TYPE_CHECKING, Any, Dict, Optional

from .base_builder import BaseMessageBuilder

if TYPE_CHECKING:
    from app.core.context import ExecutionContext


class WebMessageBuilder(BaseMessageBuilder):
    """Message builder for web interface.

    Provides web-specific message building including completion metrics
    for TPS display in the UI.
    """

    @property
    def interface_name(self) -> str:
        """Interface this builder handles."""
        return "web"

    def build_completion_metrics(
        self,
        metadata: Dict[str, Any],
        context: "ExecutionContext",
    ) -> Optional[Dict[str, Any]]:
        """Build completion metrics for web UI display.

        Web interface displays token counts and TPS after streaming.

        For thinking models (with reasoning_tokens), calculates visible output
        tokens separately from total generated tokens.

        Args:
            metadata: Execution result metadata with token counts, timing, etc.
            context: Execution context.

        Returns:
            Response message with metrics for web-service.
        """
        output_tokens = metadata.get("output_tokens")
        reasoning_tokens = metadata.get("reasoning_tokens")

        # Calculate visible output tokens (subtract reasoning if available)
        visible_tokens = output_tokens
        if reasoning_tokens and output_tokens:
            visible_tokens = output_tokens - reasoning_tokens

        return self.build_message(
            {
                "type": "response",
                "model": metadata.get("model"),
                "generationTime": metadata.get("generation_time"),
                "tokensUsed": metadata.get("input_tokens"),
                "outputTokens": visible_tokens,           # Visible output only
                "totalTokensGenerated": output_tokens,    # Total including reasoning
                "reasoningTokens": reasoning_tokens,      # Expose reasoning count
            },
            context,
        )
