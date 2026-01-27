"""Base Agent for TROISE AI.

Provides common functionality for all agents including:
- Streaming support with think tag filtering
- Tool call tracking
- Context-aware prompt building (via PromptComposer)
- Model lifecycle management
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from strands import Agent

from .context import ExecutionContext
from .interfaces.agent import AgentResult

if TYPE_CHECKING:
    from .streaming import AgentStreamHandler
    from .interfaces.services import IVRAMOrchestrator
    from ..prompts import PromptComposer

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all TROISE AI agents.

    Provides:
    - Common streaming loop with stream_handler support
    - Tool call tracking
    - Context-aware prompt building via PromptComposer
    - Model lifecycle management (cleanup)

    Subclasses must define:
    - name: Agent identifier (used to load prompt from prompts/agents/{name}.prompt)
    - category: Agent category (e.g., "code", "productivity")
    - tools: List of tool names to inject

    Prompts are loaded from app/prompts/agents/{name}.prompt with profile variants
    in app/prompts/agents/variants/{profile}/{name}.prompt.

    Example:
        class MyAgent(BaseAgent):
            name = "my_agent"
            category = "custom"
            tools = ["brain_search", "save_note"]

            async def execute(self, input, context, stream_handler=None):
                return await self._execute_with_streaming(
                    input=input,
                    context=context,
                    stream_handler=stream_handler,
                )
    """

    name: str
    category: str
    tools: List[str]

    def __init__(
        self,
        vram_orchestrator: "IVRAMOrchestrator",
        tools: List[Any],
        prompt_composer: "PromptComposer",
        config: Dict[str, Any] = None,
    ):
        """
        Initialize the base agent.

        Args:
            vram_orchestrator: VRAM orchestrator for getting models.
            tools: List of Strands tool instances.
            prompt_composer: PromptComposer for building system prompts.
            config: Agent configuration (model, timeout, max_tokens, etc.).
        """
        self._vram_orchestrator = vram_orchestrator
        self._tools = tools
        self._prompt_composer = prompt_composer
        self._config = config or {}
        # Get model from config, or fall back to profile's model for specified role
        if "model" in self._config:
            self._model_id = self._config["model"]
        else:
            # Use model_role config (default: "agent") to get appropriate profile model
            model_role = self._config.get("model_role", "agent")
            self._model_id = vram_orchestrator.get_profile_model(model_role)
        self._temperature = self._config.get("temperature", 0.7)
        self._max_tokens = self._config.get("max_tokens", 4096)
        self._max_history_turns = self._config.get("max_history_turns", 10)
        # Thinking level override: "low", "medium", "high", or None for model default
        self._thinking_level = self._config.get("thinking_level")

    def set_tools(self, tools: List[Any]) -> None:
        """Set tools at execution time (for graph execution).

        Allows tools to be injected after agent creation, enabling
        shared tool instances across graph nodes.

        Args:
            tools: List of Strands tool instances.
        """
        self._tools = tools

    def _build_system_prompt(self, context: ExecutionContext) -> str:
        """
        Build context-aware system prompt using PromptComposer.

        Loads prompt from app/prompts/agents/{name}.prompt with profile variants
        and composes with interface and personalization layers.

        Args:
            context: Execution context with user profile and interface info.

        Returns:
            Formatted system prompt.
        """
        return self._prompt_composer.compose_agent_prompt(
            agent_name=self.name,
            interface=context.interface,
            user_profile=context.user_profile,
        )

    def _build_input_with_history(
        self,
        input: str,
        context: ExecutionContext,
        max_history_turns: int = None,
    ) -> str:
        """
        Build input string with conversation history prepended.

        Args:
            input: Current user input.
            context: Execution context with conversation_history.
            max_history_turns: Maximum history messages to include (defaults to config).

        Returns:
            Input string with history context prepended.
        """
        if max_history_turns is None:
            max_history_turns = self._max_history_turns

        # No history - return input as-is
        if not context.conversation_history:
            return input

        # Get last N turns (exclude current message which is already in input)
        history = context.conversation_history[:-1][-max_history_turns:]
        if not history:
            return input

        # Format history as XML-tagged context
        history_parts = ["<conversation_history>"]
        for msg in history:
            role_label = "User" if msg.role == "user" else "Assistant"
            history_parts.append(f"{role_label}: {msg.content}")
        history_parts.append("</conversation_history>")
        history_parts.append("")
        history_parts.append(f"Current request: {input}")

        return "\n".join(history_parts)

    async def _execute_with_streaming(
        self,
        input: str,
        context: ExecutionContext,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Execute agent loop with streaming support.

        This is the common execution pattern for all agents.
        Handles:
        - Model acquisition from VRAM orchestrator
        - Strands agent creation
        - Streaming loop with cancellation checks
        - Tool call tracking
        - Stream handler integration
        - Model cleanup

        Args:
            input: User input to process.
            context: Execution context.
            stream_handler: Optional handler for WebSocket streaming.

        Returns:
            AgentResult with content, tool calls, and metadata.
        """
        system_prompt = self._build_system_prompt(context)
        tool_calls: List[Dict[str, Any]] = []
        model = None

        try:
            # Get effective model and temperature from user_config (if provided)
            model_id = self._model_id
            temperature = self._temperature

            if context.user_config:
                if context.user_config.model:
                    model_id = context.user_config.model
                    logger.info(f"Using user-specified model: {model_id}")
                if context.user_config.temperature is not None:
                    temperature = context.user_config.temperature
                    logger.info(f"Using user-specified temperature: {temperature}")

            # Build additional_args for thinking level override
            # Priority: user_config.thinking_enabled > agent's _thinking_level
            additional_args = None
            if context.user_config and context.user_config.thinking_enabled is not None:
                # User explicitly set thinking preference
                if context.user_config.thinking_enabled:
                    additional_args = {"think": self._thinking_level or "medium"}
                # If thinking_enabled=False, leave additional_args=None (disabled)
            elif self._thinking_level:
                # Fall back to agent's default thinking level
                additional_args = {"think": self._thinking_level}

            model = await self._vram_orchestrator.get_model(
                model_id,
                temperature=temperature,
                max_tokens=self._max_tokens,
                additional_args=additional_args,
            )

            # Create hooks for capturing tool results
            from .hooks import SourceCaptureHook, ImageCaptureHook
            source_hook = SourceCaptureHook(context)
            image_hook = ImageCaptureHook(context)

            # Create Strands agent with hooks
            agent = Agent(
                model=model,
                tools=self._tools,
                system_prompt=system_prompt,
                hooks=[source_hook, image_hook],
            )

            logger.info(f"Starting {self.name} agent with model {model_id}")

            # Build input with conversation history
            input_with_history = self._build_input_with_history(input, context)

            # Collect streamed response
            full_response = ""
            event_count = 0
            token_usage = {}  # Capture token metrics from metadata event

            async for event in agent.stream_async(input_with_history):
                event_count += 1
                # Check for cancellation
                await context.check_cancelled()

                # Debug log first few events to understand Strands event format
                if event_count <= 5:
                    logger.debug(f"Event {event_count}: {event}")

                # Unwrap Strands event wrapper (events come as {'event': {...}})
                inner_event = event.get("event", event)

                # Stream to WebSocket if handler provided
                if stream_handler:
                    await stream_handler.stream_event(inner_event)

                # Handle different event types
                if "contentBlockDelta" in inner_event:
                    delta = inner_event["contentBlockDelta"]["delta"]
                    if "text" in delta:
                        full_response += delta["text"]

                elif "contentBlockStart" in inner_event:
                    start = inner_event["contentBlockStart"].get("start", {})
                    if "toolUse" in start:
                        tool_calls.append({
                            "name": start["toolUse"]["name"],
                            "id": start["toolUse"].get("toolUseId"),
                        })

                # Capture metadata event with token counts (normalized by Strands SDK)
                # ExtendedOpenAIModel adds reasoningTokens for thinking models
                elif "metadata" in inner_event:
                    meta = inner_event["metadata"]
                    if "usage" in meta:
                        token_usage = {
                            "input_tokens": meta["usage"].get("inputTokens"),
                            "output_tokens": meta["usage"].get("outputTokens"),
                            "total_tokens": meta["usage"].get("totalTokens"),
                            "reasoning_tokens": meta["usage"].get("reasoningTokens"),
                        }
                        logger.debug(f"Token usage captured: {token_usage}")

            # Finalize streaming
            if stream_handler:
                await stream_handler.finalize()

            logger.info(f"Agent response collected: {len(full_response)} chars from {event_count} events")

            return AgentResult(
                content=full_response,
                tool_calls=tool_calls,
                metadata=self._build_metadata(tool_calls, token_usage),
            )

        except Exception as e:
            logger.error(f"{self.name} agent error: {e}")
            return AgentResult(
                content=f"Error during {self.name} execution: {str(e)}",
                tool_calls=tool_calls,
                metadata={
                    "agent": self.name,
                    "error": str(e),
                },
            )

        finally:
            # Clean up model session if needed
            if model and hasattr(model, 'close'):
                await model.close()

    def _build_metadata(
        self,
        tool_calls: List[Dict[str, Any]],
        token_usage: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build metadata for agent result.

        Can be overridden by subclasses to add custom metadata.

        Args:
            tool_calls: List of tool calls made during execution.
            token_usage: Optional token usage from Strands SDK metadata event.

        Returns:
            Metadata dictionary.
        """
        metadata = {
            "agent": self.name,
            "model": self._model_id,
            "tools_used": [tc["name"] for tc in tool_calls],
        }
        # Merge token usage if captured from metadata event
        if token_usage:
            metadata.update(token_usage)
        return metadata

    @abstractmethod
    async def execute(
        self,
        input: str,
        context: ExecutionContext,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Execute the agent.

        Subclasses should implement this, typically by calling
        _execute_with_streaming with any pre/post processing.

        Args:
            input: User input to process.
            context: Execution context.
            stream_handler: Optional handler for WebSocket streaming.

        Returns:
            AgentResult with content and metadata.
        """
        ...
