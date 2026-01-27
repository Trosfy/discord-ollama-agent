"""Output strategy protocol for interface-specific handling.

Different interfaces (Discord, Terminal, VSCode) need different approaches
to handling agent output and artifact delivery.

This protocol enables:
- Discord: Sanitize prompt, no write_file tool, postprocess extraction
- Terminal: Passthrough prompt, with write_file, confirmation before writes
- VSCode: Passthrough prompt, with write_file, show diff in IDE
"""
from typing import List, Protocol, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.context import ExecutionContext
    from app.core.executor import ExecutionResult


class IOutputStrategy(Protocol):
    """Strategy for interface-specific output handling.

    Different interfaces need different approaches:
    - Discord: Sanitize prompt, no write_file, postprocess extract
    - Terminal: Passthrough prompt, with write_file, confirm writes
    - VSCode: Passthrough prompt, with write_file, show diff in IDE

    Designed to support both TEXT artifacts (code files) and
    BINARY artifacts (images from future FLUX integration).

    Example:
        strategy = container.resolve(IOutputStrategy, key="discord")

        # Prepare prompt (Discord sanitizes, others passthrough)
        prepared = strategy.prepare_prompt(raw_prompt, context)

        # Get tools (Discord excludes write_file)
        tools = strategy.get_tools(agent_name, base_tools, context)

        # Execute agent...

        # Handle output (Discord extracts, Terminal confirms)
        await strategy.handle_output(result, context, artifact_requested, filename)
    """

    def prepare_prompt(
        self,
        raw_prompt: str,
        context: "ExecutionContext",
    ) -> str:
        """Prepare prompt for agent execution.

        Discord: Sanitizes (removes file/image artifact language)
        Terminal/VSCode: Passthrough (keeps artifact language)

        Args:
            raw_prompt: Raw user prompt.
            context: Execution context with preprocessing results.

        Returns:
            Prepared prompt for agent.
        """
        ...

    def get_tools(
        self,
        agent_name: str,
        base_tools: List[str],
        context: "ExecutionContext",
    ) -> List[str]:
        """Get tools for agent.

        Discord: Excludes write_file (prevents tool confusion with small models)
        Terminal/VSCode: Includes write_file (agent controls files directly)

        Args:
            agent_name: Name of the agent being executed.
            base_tools: Base tools defined for the agent.
            context: Execution context.

        Returns:
            List of tool names for the agent.
        """
        ...

    async def handle_output(
        self,
        result: "ExecutionResult",
        context: "ExecutionContext",
        artifact_requested: bool,
        expected_filename: str | None,
    ) -> None:
        """Handle agent output delivery.

        Supports both text and binary artifacts:
        - Text (code): Extract via postprocessing chain
        - Binary (images): Direct delivery (future FLUX support)

        Discord: Extract via postprocessing, send as file attachment
        Terminal: Confirm with user before writing to filesystem
        VSCode: Show diff in IDE, user approves

        Args:
            result: Execution result from agent.
            context: Execution context with WebSocket.
            artifact_requested: Whether user wants file output.
            expected_filename: Expected output filename from preprocessing.
        """
        ...
