"""Terminal output strategy - direct flow for TUI with larger models.

Terminal/TUI workflow:
1. Passthrough prompt (keeps file/artifact language)
2. Include write_file tool (agent can write files directly)
3. Confirm with user before filesystem writes

Designed for TUI clients where users expect interactive file operations
with confirmation dialogs and larger model capabilities.
"""
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.context import ExecutionContext
    from app.core.executor import ExecutionResult


class TerminalOutputStrategy:
    """Direct flow for Terminal UI.

    - Passthrough prompt (keeps file artifact language)
    - Includes write_file tool (agent controls files)
    - Confirms before writing to filesystem

    Example:
        strategy = TerminalOutputStrategy()

        # Prepare prompt (passthrough)
        prepared = strategy.prepare_prompt(raw_prompt, context)

        # Get tools (includes write_file)
        tools = strategy.get_tools("agentic_code", base_tools, context)

        # Execute agent (agent can use write_file directly)...

        # Handle output (confirm writes if needed)
        await strategy.handle_output(result, context, True, "output.cpp")
    """

    def prepare_prompt(
        self,
        raw_prompt: str,
        context: "ExecutionContext",
    ) -> str:
        """Passthrough - agent sees full request including file language.

        For Terminal/TUI with larger models, the agent can handle
        requests like "create merge sort and save to mergesort.cpp"
        directly, using the write_file tool.

        Args:
            raw_prompt: Raw user prompt.
            context: Execution context.

        Returns:
            Raw prompt unchanged.
        """
        return raw_prompt

    def get_tools(
        self,
        agent_name: str,
        base_tools: List[str],
        context: "ExecutionContext",
    ) -> List[str]:
        """Include write_file - agent can write to filesystem.

        For Terminal/TUI, larger models can reliably use the write_file
        tool. The agent decides when to write files based on user intent.

        Args:
            agent_name: Name of the agent being executed.
            base_tools: Base tools defined for the agent.
            context: Execution context.

        Returns:
            Base tools plus write_file if not already present.
        """
        if "write_file" not in base_tools:
            return base_tools + ["write_file"]
        return base_tools

    async def handle_output(
        self,
        result: "ExecutionResult",
        context: "ExecutionContext",
        artifact_requested: bool,
        expected_filename: str | None,
    ) -> None:
        """Handle output - confirm writes, display results.

        Terminal workflow:
        1. If agent used write_file, show confirmation
        2. If artifacts extracted, offer to save
        3. Display final results to user

        Args:
            result: Execution result from agent.
            context: Execution context with WebSocket.
            artifact_requested: Whether user wants file output.
            expected_filename: Expected output filename from preprocessing.

        Raises:
            NotImplementedError: Terminal strategy pending TUI implementation.
        """
        # TODO: Implement terminal-specific handling
        # - Check if write_file was called via result.tool_calls
        # - Show write confirmation via context.execute_command callback
        # - If artifacts extracted, offer to save interactively
        raise NotImplementedError("Terminal strategy pending TUI implementation")
