"""Extended OpenAI model that extracts reasoning tokens.

The base Strands OpenAIModel only extracts prompt_tokens, completion_tokens,
and total_tokens from the usage metadata. This extended version also extracts
completion_tokens_details.reasoning_tokens when available (SGLang/OpenAI
extended thinking models).

This allows the frontend to display visible output tokens separately from
internal reasoning tokens.
"""

from typing import Any

from strands.models.openai import OpenAIModel
from strands.types.streaming import StreamEvent


class ExtendedOpenAIModel(OpenAIModel):
    """OpenAI model that extracts completion_tokens_details.reasoning_tokens."""

    def format_chunk(self, event: dict[str, Any]) -> StreamEvent:
        """Override to include reasoning_tokens in metadata.

        For metadata events, extracts the reasoning_tokens field from
        completion_tokens_details if available. This allows distinguishing
        between visible output tokens and internal reasoning tokens.

        Args:
            event: Raw chunk event from the stream.

        Returns:
            Formatted StreamEvent with extended metadata.
        """
        if event.get("chunk_type") == "metadata":
            usage = event["data"]
            result: StreamEvent = {
                "metadata": {
                    "usage": {
                        "inputTokens": usage.prompt_tokens,
                        "outputTokens": usage.completion_tokens,
                        "totalTokens": usage.total_tokens,
                    },
                    "metrics": {
                        "latencyMs": 0,
                    },
                },
            }

            # Extract reasoning_tokens if available (SGLang/OpenAI extended thinking)
            if hasattr(usage, "completion_tokens_details") and usage.completion_tokens_details:
                details = usage.completion_tokens_details
                if hasattr(details, "reasoning_tokens") and details.reasoning_tokens:
                    result["metadata"]["usage"]["reasoningTokens"] = details.reasoning_tokens

            return result

        return super().format_chunk(event)
