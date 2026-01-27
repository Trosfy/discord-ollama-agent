"""Extended Ollama model that fixes token count swap bug.

The base Strands OllamaModel has input/output tokens SWAPPED:
- inputTokens = eval_count (actually OUTPUT)
- outputTokens = prompt_eval_count (actually INPUT)

This extended version fixes the swap and properly reports:
- inputTokens = prompt_eval_count (correct INPUT)
- outputTokens = eval_count (correct OUTPUT)
"""

from typing import Any

from strands.models.ollama import OllamaModel
from strands.types.streaming import StreamEvent


class ExtendedOllamaModel(OllamaModel):
    """Ollama model with fixed token count mapping."""

    def format_chunk(self, event: dict[str, Any]) -> StreamEvent:
        """Override to fix the swapped input/output token counts.

        Strands SDK has them backwards:
        - eval_count is mapped to inputTokens (wrong - it's output)
        - prompt_eval_count is mapped to outputTokens (wrong - it's input)

        This override fixes the mapping.

        Args:
            event: Raw chunk event from the stream.

        Returns:
            Formatted StreamEvent with corrected token counts.
        """
        if event.get("chunk_type") == "metadata":
            data = event["data"]
            # Fix the swap: prompt_eval_count is INPUT, eval_count is OUTPUT
            return {
                "metadata": {
                    "usage": {
                        "inputTokens": data.prompt_eval_count,   # FIXED: prompt = input
                        "outputTokens": data.eval_count,          # FIXED: eval = output
                        "totalTokens": data.eval_count + data.prompt_eval_count,
                    },
                    "metrics": {
                        "latencyMs": data.total_duration / 1e6,
                    },
                },
            }

        return super().format_chunk(event)
