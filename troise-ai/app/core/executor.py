"""Executor for TROISE AI.

Executes skills, agents, and graphs after routing decisions.
Handles dependency injection, tool creation for agents,
graph-scoped tool lifecycle for graphs, and result formatting.
"""
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

from .container import Container
from .context import ExecutionContext
from .declarative_skill import DeclarativeSkill
from .exceptions import PluginNotFoundError, PluginError
from .interfaces.skill import ISkill, SkillResult
from .interfaces.agent import IAgent, AgentResult
from .interfaces.services import IVRAMOrchestrator
from .interfaces.graph import IGraphRegistry, IGraphExecutor, GraphResult
from .interfaces.output_strategy import IOutputStrategy
from .registry import PluginRegistry
from .router import RoutingResult
from .tool_factory import ToolFactory
from .streaming import AgentStreamHandler, get_streaming_manager
from .status import get_status_message
from ..prompts import PromptComposer

if TYPE_CHECKING:
    from .graph import Graph
    from ..strategies import DiscordOutputStrategy, TerminalOutputStrategy

logger = logging.getLogger(__name__)


# Action-specific instructions for response formatting
# These guide agents on HOW to format their response so postprocessing can extract artifacts
ACTION_INSTRUCTIONS = {
    "create": """
**Response Format for File Creation:**
When creating a file, include ONLY the file content in a properly formatted code block.
Use the appropriate language identifier (e.g., ```python, ```javascript, ```yaml).
Do NOT include explanatory text inside the code block.
Put any explanations BEFORE or AFTER the code block, not inside it.
""",
    "modify": """
**Response Format for File Modification:**
When modifying code, include the COMPLETE modified file content in a code block.
Use the appropriate language identifier (e.g., ```python).
Provide the full file, not just the changed parts.
Put explanations of changes OUTSIDE the code block.
""",
    "analyze": """
**Response Format for Analysis:**
Provide clear, structured analysis.
Use markdown formatting for organization.
If showing code snippets, use code blocks with language identifiers.
""",
    "query": """
**Response Format:**
Answer the question directly and concisely.
Use code blocks for any code examples.
""",
}


def get_action_instructions(action_type: str) -> str:
    """Get formatting instructions for an action type.

    Args:
        action_type: The action type (create, modify, analyze, query).

    Returns:
        Formatting instructions for the action.
    """
    return ACTION_INSTRUCTIONS.get(action_type, ACTION_INSTRUCTIONS["query"])


@dataclass
class ExecutionResult:
    """Unified result from skill, agent, or graph execution.

    Supports both text content (code, responses) and binary content (images).
    Designed for future FLUX/image generation integration.

    Attributes:
        content: Text or binary content from execution.
        content_type: MIME type - "text/plain", "image/png", etc.
        source_type: "skill", "agent", or "graph".
        source_name: Name of the plugin that produced this result.
        tool_calls: List of tool calls made during execution.
        metadata: Additional metadata (tokens, timing, etc.).
        success: Whether execution succeeded.
        error: Error message if execution failed.
    """
    content: Union[str, bytes]
    source_type: str  # "skill", "agent", or "graph"
    source_name: str
    content_type: str = "text/plain"  # MIME type
    tool_calls: List[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None
    success: bool = True
    error: Optional[str] = None

    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []
        if self.metadata is None:
            self.metadata = {}

    @property
    def is_binary(self) -> bool:
        """Check if content is binary (e.g., image)."""
        return isinstance(self.content, bytes)

    @property
    def is_image(self) -> bool:
        """Check if content is an image."""
        return self.content_type.startswith("image/")


class Executor:
    """
    Executes skills, agents, and graphs from routing decisions.

    Handles:
    - Plugin resolution from registry
    - Graph resolution from graph registry
    - Dependency injection via container
    - Tool creation for agents
    - Graph-scoped tool lifecycle (tools created once, shared across nodes)
    - Error handling and result formatting

    Example:
        executor = Executor(registry, container, tool_factory)
        result = await executor.execute(routing_result, user_input, context)
    """

    def __init__(
        self,
        registry: PluginRegistry,
        container: Container,
        tool_factory: ToolFactory,
        graph_registry: Optional[IGraphRegistry] = None,
        graph_executor: Optional[IGraphExecutor] = None,
    ):
        """
        Initialize the executor.

        Args:
            registry: Plugin registry with skills and agents.
            container: DI container for dependency resolution.
            tool_factory: Factory for creating agent tools.
            graph_registry: Optional registry for graph definitions.
            graph_executor: Optional executor for graph workflows.
        """
        self._registry = registry
        self._container = container
        self._tool_factory = tool_factory
        self._graph_registry = graph_registry
        self._graph_executor = graph_executor
        # Cache resolved strategies
        self._strategy_cache: Dict[str, IOutputStrategy] = {}

    def _get_output_strategy(self, context: ExecutionContext) -> IOutputStrategy:
        """Get interface-specific output strategy.

        Resolves the appropriate strategy based on context.interface.
        Strategies are cached for efficiency.

        Args:
            context: Execution context with interface info.

        Returns:
            Output strategy for the interface.
        """
        interface = getattr(context, "interface", "discord")

        # Check cache first
        if interface in self._strategy_cache:
            return self._strategy_cache[interface]

        # Resolve strategy from container based on interface
        # Import here to avoid circular imports at module level
        from ..strategies import DiscordOutputStrategy, TerminalOutputStrategy

        if interface in ("discord", "web"):
            strategy = self._container.resolve(DiscordOutputStrategy)
        elif interface in ("cli", "terminal", "tui"):
            strategy = self._container.resolve(TerminalOutputStrategy)
        else:
            # Default to Discord strategy for unknown interfaces
            logger.warning(f"Unknown interface '{interface}', using Discord strategy")
            strategy = self._container.resolve(DiscordOutputStrategy)

        self._strategy_cache[interface] = strategy
        return strategy

    async def execute(
        self,
        routing_result: RoutingResult,
        user_input: str,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """
        Execute the skill, agent, or graph from routing result.

        Args:
            routing_result: Result from Router indicating which plugin to use.
            user_input: The original user input.
            context: Execution context with user info, interface, etc.

        Returns:
            ExecutionResult with content and metadata.

        Raises:
            PluginNotFoundError: If the plugin is not in registry.
            PluginError: If plugin execution fails.
        """
        try:
            if routing_result.type == "skill":
                return await self._execute_skill(
                    routing_result.name,
                    user_input,
                    context,
                )
            elif routing_result.type == "agent":
                return await self._execute_agent(
                    routing_result.name,
                    user_input,
                    context,
                )
            elif routing_result.type == "graph":
                return await self._execute_graph(
                    routing_result.name,
                    user_input,
                    context,
                )
            else:
                raise PluginError(f"Unknown routing type: {routing_result.type}")

        except Exception as e:
            logger.error(f"Execution failed for {routing_result.type}:{routing_result.name}: {e}")
            return ExecutionResult(
                content="",
                source_type=routing_result.type,
                source_name=routing_result.name,
                success=False,
                error=str(e),
            )

    def _build_enhanced_prompt(
        self,
        user_input: str,
        context: ExecutionContext,
    ) -> str:
        """
        Build enhanced prompt with interface-specific preparation and formatting.

        1. Uses IOutputStrategy.prepare_prompt() for interface-specific handling:
           - Discord: Returns clean_intent (removes "give me the file" language)
           - Terminal: Returns raw prompt (agent can handle file creation)

        2. Appends formatting instructions based on context.action_type so that
           postprocessing can reliably extract artifacts from the response.

        Args:
            user_input: Original user input (already enriched with file context).
            context: Execution context with action_type and interface.

        Returns:
            Enhanced prompt with formatting instructions appended.
        """
        # Get interface-specific strategy
        strategy = self._get_output_strategy(context)

        # Prepare prompt (Discord sanitizes, Terminal passes through)
        prepared_prompt = strategy.prepare_prompt(user_input, context)

        # Add action-specific formatting instructions
        action_type = getattr(context, "action_type", "query")
        formatting_instructions = get_action_instructions(action_type)

        # Append formatting instructions to help postprocessing extract artifacts
        enhanced = f"{prepared_prompt}\n\n{formatting_instructions}"

        logger.debug(
            f"Enhanced prompt: interface={context.interface}, "
            f"action_type={action_type}, len={len(enhanced)}"
        )
        return enhanced

    async def _execute_skill(
        self,
        skill_name: str,
        user_input: str,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """
        Execute a skill.

        Args:
            skill_name: Name of the skill to execute.
            user_input: User input to process.
            context: Execution context.

        Returns:
            ExecutionResult from skill execution.
        """
        # Get skill plugin from registry
        plugin = self._registry.get_skill(skill_name)
        if not plugin:
            raise PluginNotFoundError(f"Skill '{skill_name}' not found in registry")

        # Create skill instance
        skill = self._create_skill_instance(plugin, context)

        # Enhance prompt with action-specific formatting instructions
        enhanced_input = self._build_enhanced_prompt(user_input, context)

        # Execute skill
        logger.info(f"Executing skill: {skill_name} (action_type={context.action_type})")
        logger.debug(f"Skill prompt size: {len(enhanced_input)} chars")
        start_time = time.time()
        result = await skill.execute(enhanced_input, context)
        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"Skill complete: {skill_name}, duration={duration_ms:.0f}ms")

        return ExecutionResult(
            content=result.content,
            source_type="skill",
            source_name=skill_name,
            metadata=result.metadata,
            success=True,
        )

    async def _execute_agent(
        self,
        agent_name: str,
        user_input: str,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """
        Execute an agent with streaming support.

        Args:
            agent_name: Name of the agent to execute.
            user_input: User input to process.
            context: Execution context.

        Returns:
            ExecutionResult from agent execution.
        """
        # Get agent plugin from registry
        plugin = self._registry.get_agent(agent_name)
        if not plugin:
            raise PluginNotFoundError(f"Agent '{agent_name}' not found in registry")

        # Set agent name in context for tracking
        context.agent_name = agent_name

        # Create tools for agent
        tools = self._tool_factory.create_tools_for_agent(agent_name, context)

        # Filter tools using interface-specific strategy
        # Discord: Excludes write_file (prevents tool confusion with small models)
        # Terminal: Includes write_file (agent can write files directly)
        strategy = self._get_output_strategy(context)
        tool_names = [t.get("name", "") for t in tools]
        filtered_names = strategy.get_tools(agent_name, tool_names, context)
        tools = [t for t in tools if t.get("name", "") in filtered_names]

        # Create agent instance with filtered tools
        agent = self._create_agent_instance(plugin, context, tools)

        # Enhance prompt with action-specific formatting instructions
        enhanced_input = self._build_enhanced_prompt(user_input, context)

        # Create stream handler for WebSocket streaming
        # Uses global StreamingManager to track failures and auto-disable
        stream_handler = None
        streaming_manager = get_streaming_manager()
        use_streaming = context.websocket and streaming_manager.should_stream()

        if use_streaming:
            stream_handler = AgentStreamHandler(context, enable_think_filter=True)

        # Send status indicator immediately so Discord shows "Thinking..." with animation
        if context.websocket:
            await self._send_status_indicator(context)

        # Execute agent with streaming support
        logger.info(
            f"Executing agent: {agent_name} with {len(tools)} tools "
            f"(interface={context.interface}, action_type={context.action_type}, "
            f"streaming={stream_handler is not None})"
        )
        logger.debug(f"Agent prompt size: {len(enhanced_input)} chars")
        start_time = time.time()

        try:
            result = await agent.execute(enhanced_input, context, stream_handler=stream_handler)

            duration_ms = (time.time() - start_time) * 1000
            duration_sec = duration_ms / 1000
            tool_count = len(result.tool_calls) if result.tool_calls else 0
            logger.info(f"Agent complete: {agent_name}, tool_calls={tool_count}, duration={duration_ms:.0f}ms")

            # Record success with streaming manager
            used_streaming = stream_handler is not None and not (
                stream_handler.had_error if hasattr(stream_handler, 'had_error') else False
            )
            streaming_manager.record_success(used_streaming)

            # Merge duration into metadata for WebSocket completion message
            metadata = {**(result.metadata or {}), "generation_time": duration_sec}

            return ExecutionResult(
                content=result.content,
                source_type="agent",
                source_name=agent_name,
                tool_calls=result.tool_calls,
                metadata=metadata,
                success=True,
            )

        except Exception as e:
            # Record streaming failure if we were streaming
            if stream_handler is not None:
                streaming_manager.record_failure()
            raise

        finally:
            # Cleanup tools regardless of success/failure
            # Closes aiohttp sessions, file handles, etc.
            await self._tool_factory.cleanup()

    async def _execute_graph(
        self,
        graph_name: str,
        user_input: str,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """
        Execute a graph workflow with graph-scoped tool lifecycle.

        Tools are created ONCE for the entire graph (union of all node tools)
        and shared across all nodes. Cleanup happens AFTER the entire graph
        completes, not after each node.

        Args:
            graph_name: Name of the graph to execute.
            user_input: User input to process.
            context: Execution context.

        Returns:
            ExecutionResult from graph execution.
        """
        if not self._graph_registry:
            raise PluginError("Graph registry not configured")
        if not self._graph_executor:
            raise PluginError("Graph executor not configured")

        # Get graph from registry
        graph = self._graph_registry.get(graph_name)
        if not graph:
            raise PluginNotFoundError(f"Graph '{graph_name}' not found in registry")

        # Set graph domain in context for prompt variant selection
        context.graph_domain = graph.domain

        # Note: Tools are created per-node by tool_factory to respect skip_universal_tools

        # Create stream handler for WebSocket streaming
        stream_handler = None
        streaming_manager = get_streaming_manager()
        use_streaming = context.websocket and streaming_manager.should_stream()

        if use_streaming:
            stream_handler = AgentStreamHandler(context, enable_think_filter=True)

        # Send status indicator immediately
        if context.websocket:
            await self._send_status_indicator(context)

        logger.info(
            f"Executing graph: {graph_name} "
            f"(domain={graph.domain}, streaming={stream_handler is not None})"
        )
        start_time = time.time()

        try:
            # Set vram_orchestrator and prompt_composer on context for SwarmNode
            # SwarmNode creates Strands agents at execution time and needs these for:
            # - vram_orchestrator: VRAM-managed model creation
            # - prompt_composer: Context-aware prompt composition (fills template placeholders)
            context.vram_orchestrator = self._container.resolve(IVRAMOrchestrator)
            context.prompt_composer = self._container.resolve(PromptComposer)

            # Execute graph - tools created per-node via tool_factory
            graph_result = await self._graph_executor.execute(
                graph=graph,
                context=context,
                input_text=user_input,
                stream_handler=stream_handler,
                tool_factory=self._tool_factory,
            )

            duration_ms = (time.time() - start_time) * 1000
            duration_sec = duration_ms / 1000
            total_tool_calls = len(graph_result.total_tool_calls)
            nodes_executed = len(graph_result.node_results)
            logger.info(
                f"Graph complete: {graph_name}, nodes={nodes_executed}, "
                f"tool_calls={total_tool_calls}, duration={duration_ms:.0f}ms"
            )

            # Record streaming success
            used_streaming = stream_handler is not None and not (
                stream_handler.had_error if hasattr(stream_handler, 'had_error') else False
            )
            streaming_manager.record_success(used_streaming)

            return self._build_graph_result(graph_result, duration_sec)

        except Exception as e:
            # Record streaming failure if we were streaming
            if stream_handler is not None:
                streaming_manager.record_failure()
            raise

        finally:
            # Cleanup tools AFTER entire graph completes
            await self._tool_factory.cleanup()

    def _build_graph_result(self, graph_result: GraphResult, duration_sec: float) -> ExecutionResult:
        """
        Convert GraphResult to ExecutionResult for API compatibility.

        Args:
            graph_result: Result from graph execution.
            duration_sec: Total graph execution duration in seconds.

        Returns:
            ExecutionResult compatible with existing API.
        """
        # Extract token metrics from final node's state updates
        last_node = graph_result.node_results[-1] if graph_result.node_results else None
        last_node_name = last_node.node_name if last_node else None

        token_metrics = {}
        if last_node_name:
            final_state = graph_result.final_state
            token_metrics = {
                "input_tokens": final_state.get(f"{last_node_name}_input_tokens"),
                "output_tokens": final_state.get(f"{last_node_name}_output_tokens"),
                "total_tokens": final_state.get(f"{last_node_name}_total_tokens"),
                "model": final_state.get(f"{last_node_name}_model"),
            }

        return ExecutionResult(
            content=graph_result.final_content,
            source_type="graph",
            source_name=graph_result.graph_name,
            tool_calls=graph_result.total_tool_calls,
            metadata={
                "graph": graph_result.graph_name,
                "domain": graph_result.domain,
                "nodes_executed": graph_result.nodes_executed,
                "success": graph_result.success,
                "generation_time": duration_sec,
                **token_metrics,
            },
            success=graph_result.success,
        )

    async def _send_status_indicator(self, context: ExecutionContext) -> None:
        """Send interface-appropriate status indicator.

        Discord: "*Thinking...*\n\n" → triggers AnimationManager dot cycling
        Streamlit: "Thinking...\n\n" → plain text (future: st.spinner)

        Args:
            context: Execution context with websocket and interface info.
        """
        if not context.websocket:
            return

        status = get_status_message(
            interface=getattr(context, "interface", "discord"),
            status_type="thinking"
        )

        msg = {
            "type": "early_status",
            "content": status,
        }

        # Add Discord-specific context
        if context.request_id:
            msg["request_id"] = context.request_id
        if getattr(context, "discord_channel_id", None):
            msg["channel_id"] = context.discord_channel_id
        if getattr(context, "discord_message_channel_id", None):
            msg["message_channel_id"] = context.discord_message_channel_id
        if getattr(context, "discord_message_id", None):
            msg["message_id"] = context.discord_message_id

        try:
            await context.websocket.send_json(msg)
            logger.info(f"Sent status indicator: {msg}")
        except Exception as e:
            logger.warning(f"Failed to send status indicator: {e}")

    def _create_skill_instance(
        self,
        plugin: Dict[str, Any],
        context: ExecutionContext,
    ) -> ISkill:
        """
        Create a skill instance from plugin definition.

        For declarative skills (skill.md), creates a DeclarativeSkill instance.
        For Python skills, creates an instance of the plugin class.

        Args:
            plugin: Plugin definition from registry.
            context: Execution context.

        Returns:
            Skill instance implementing ISkill.
        """
        # Check if this is a declarative skill (from skill.md)
        if plugin.get("declarative"):
            skill_def = plugin.get("skill_def")
            if not skill_def:
                raise PluginError(
                    f"Declarative skill '{plugin.get('name')}' missing skill_def"
                )

            vram_orchestrator = self._container.resolve(IVRAMOrchestrator)
            prompt_composer = self._container.resolve(PromptComposer)
            return DeclarativeSkill(
                skill_def=skill_def,
                vram_orchestrator=vram_orchestrator,
                prompt_composer=prompt_composer,
                container=self._container,
            )

        # Python skill - use the class
        skill_class = plugin.get("class")
        if not skill_class:
            raise PluginError(f"Skill plugin missing 'class' key")

        # Inject dependencies from container
        # Skills typically need: IVRAMOrchestrator
        vram_orchestrator = self._container.resolve(IVRAMOrchestrator)

        return skill_class(
            vram_orchestrator=vram_orchestrator,
            container=self._container,
        )

    def _create_agent_instance(
        self,
        plugin: Dict[str, Any],
        context: ExecutionContext,
        tools: List[Dict[str, Any]],
    ) -> IAgent:
        """
        Create an agent instance from plugin definition.

        The plugin must have:
        - class: The agent class implementing IAgent
        - config: Agent configuration (model, timeout, etc.)

        Args:
            plugin: Plugin definition from registry.
            context: Execution context.
            tools: List of Strands tool definitions.

        Returns:
            Agent instance.
        """
        agent_class = plugin.get("class")
        if not agent_class:
            raise PluginError(f"Agent plugin missing 'class' key")

        config = plugin.get("config", {})

        # Inject dependencies from container
        # Agents use VRAMOrchestrator for model access and PromptComposer for prompts
        vram_orchestrator = self._container.resolve(IVRAMOrchestrator)
        prompt_composer = self._container.resolve(PromptComposer)

        return agent_class(
            vram_orchestrator=vram_orchestrator,
            tools=tools,
            prompt_composer=prompt_composer,
            config=config,
        )

    async def execute_skill_directly(
        self,
        skill_name: str,
        user_input: str,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """
        Execute a skill directly without routing.

        Useful for internal skill invocations.

        Args:
            skill_name: Name of the skill.
            user_input: Input to process.
            context: Execution context.

        Returns:
            ExecutionResult.
        """
        return await self._execute_skill(skill_name, user_input, context)

    async def execute_agent_directly(
        self,
        agent_name: str,
        user_input: str,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """
        Execute an agent directly without routing.

        Useful for internal agent invocations.

        Args:
            agent_name: Name of the agent.
            user_input: Input to process.
            context: Execution context.

        Returns:
            ExecutionResult.
        """
        return await self._execute_agent(agent_name, user_input, context)
