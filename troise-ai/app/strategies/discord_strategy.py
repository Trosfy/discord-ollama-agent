"""Discord output strategy - sanitized flow for small/medium models.

Discord workflow:
1. Sanitize prompt (removes file/artifact language)
2. Exclude write_file tool (prevents tool confusion with small models)
3. Postprocessing chain extracts artifacts from response

This keeps small/medium models focused on the task without confusion
about file creation - the postprocessing handles artifact extraction.
"""
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.context import ExecutionContext
    from app.core.executor import ExecutionResult
    from app.services.response_handler import ResponseHandler


class DiscordOutputStrategy:
    """Sanitized flow for Discord with small/medium models.

    - Sanitizes prompt (removes file artifact language)
    - Excludes write_file tool (prevents tool confusion)
    - Uses postprocessing chain to extract artifacts

    Example:
        strategy = DiscordOutputStrategy(response_handler)

        # Prepare prompt (sanitizes)
        prepared = strategy.prepare_prompt(raw_prompt, context)

        # Get tools (excludes write_file)
        tools = strategy.get_tools("agentic_code", base_tools, context)

        # Execute agent...

        # Handle output (extracts artifacts via postprocessing)
        await strategy.handle_output(result, context, True, "output.cpp")
    """

    # Tools to exclude for Discord (prevents small model confusion)
    EXCLUDED_TOOLS = {"write_file"}

    def __init__(self, response_handler: "ResponseHandler"):
        """Initialize Discord strategy.

        Args:
            response_handler: Handler for response formatting and delivery.
        """
        self._response_handler = response_handler

    def prepare_prompt(
        self,
        raw_prompt: str,
        context: "ExecutionContext",
    ) -> str:
        """Sanitize prompt - use clean intent from preprocessing.

        For Discord, the agent shouldn't see "give me the .cpp file" -
        it confuses small/medium models. Instead, agent sees the clean
        intent: "create merge sort in c++".

        The clean_intent is set by PromptSanitizer during preprocessing.

        Args:
            raw_prompt: Raw user prompt.
            context: Execution context with preprocessing results.

        Returns:
            Clean intent from preprocessing, or raw prompt if not available.
        """
        # Use clean intent from preprocessing if available
        if context.clean_intent:
            return context.clean_intent
        return raw_prompt

    def get_tools(
        self,
        agent_name: str,
        base_tools: List[str],
        context: "ExecutionContext",
    ) -> List[str]:
        """Exclude write_file - agent outputs code, postprocess extracts.

        For Discord, we don't give agents the write_file tool because:
        1. Small/medium models get confused about when to use it
        2. Postprocessing extracts artifacts more reliably
        3. Keeps agent focused on generating quality code

        Args:
            agent_name: Name of the agent being executed.
            base_tools: Base tools defined for the agent.
            context: Execution context.

        Returns:
            Filtered tool list without write_file.
        """
        return [t for t in base_tools if t not in self.EXCLUDED_TOOLS]

    async def handle_output(
        self,
        result: "ExecutionResult",
        context: "ExecutionContext",
        artifact_requested: bool,
        expected_filename: str | None,
    ) -> None:
        """Extract artifacts via postprocessing chain.

        Discord workflow:
        1. ResponseHandler runs artifact extraction chain
        2. Chain tries: ToolArtifactHandler → LLMExtractionHandler → RegexFallbackHandler
        3. Extracted artifacts sent as file attachments

        Args:
            result: Execution result from agent.
            context: Execution context with WebSocket.
            artifact_requested: Whether user wants file output.
            expected_filename: Expected output filename from preprocessing.
        """
        # Determine if content was streamed (text already sent)
        streamed = getattr(context, "was_streamed", False)

        await self._response_handler.send_response(
            result=result,
            context=context,
            artifact_requested=artifact_requested,
            expected_filename=expected_filename,
            streamed=streamed,
        )
