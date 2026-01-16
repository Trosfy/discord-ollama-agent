"""Tool Factory for TROISE AI.

Creates Strands-compatible tools with ExecutionContext injected.
Handles the bridge between plugin-defined tools and the Strands agent runtime.

Each tool in the registry has a factory function that receives:
- ExecutionContext: For user interaction, cancellation, etc.
- Container: For resolving service dependencies (brain, vault, etc.)

The ToolFactory wraps these into Strands tool format using the @tool decorator.
"""
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from strands import tool as strands_tool
from strands.types.tools import ToolContext

from .container import Container
from .context import ExecutionContext
from .registry import PluginRegistry
from .interfaces.tool import ITool, ToolResult, ICloseable

logger = logging.getLogger(__name__)


class ToolFactory:
    """
    Creates tools for agent execution.

    Resolves tool plugins from registry, injects dependencies via container,
    and wraps them in Strands-compatible format.

    Example:
        factory = ToolFactory(registry, container)
        tools = factory.create_tools_for_agent("braindump", context)
        # tools is a list of Strands tool definitions
        # After execution:
        await factory.cleanup()  # Close tool resources
    """

    def __init__(self, registry: PluginRegistry, container: Container):
        """
        Initialize the tool factory.

        Args:
            registry: Plugin registry with tool definitions.
            container: DI container for service resolution.
        """
        self._registry = registry
        self._container = container
        self._created_tools: List[ITool] = []  # Track for cleanup

    def create_tools_for_agent(
        self,
        agent_name: str,
        context: ExecutionContext,
    ) -> List[Any]:
        """
        Create Strands-compatible tools for an agent.

        Resolves the agent's configured tools from registry,
        creates instances with context injected, and returns
        as Strands decorated tools.

        Args:
            agent_name: Name of the agent to create tools for.
            context: Execution context to inject into tools.

        Returns:
            List of Strands tools (decorated functions).
        """
        # Clear previous tools (new execution context)
        self._created_tools = []

        tool_plugins = self._registry.get_tools_for_agent(agent_name)

        if not tool_plugins:
            logger.debug(f"No tools configured for agent '{agent_name}'")
            return []

        tools = []
        tool_names = []
        for plugin in tool_plugins:
            tool = self._create_tool(plugin, context)
            if tool:
                tools.append(tool)
                tool_names.append(plugin.get('name', 'unknown'))

        logger.info(f"Created {len(tools)} tools for agent '{agent_name}': {tool_names}")
        return tools

    def create_tool(
        self,
        tool_name: str,
        context: ExecutionContext,
    ) -> Optional[Any]:
        """
        Create a single Strands-compatible tool.

        Args:
            tool_name: Name of the tool to create.
            context: Execution context to inject.

        Returns:
            Strands tool (decorated function), or None if tool not found.
        """
        plugin = self._registry.get_tool(tool_name)
        if not plugin:
            logger.warning(f"Tool '{tool_name}' not found in registry")
            return None

        return self._create_tool(plugin, context)

    def _create_tool(
        self,
        plugin: Dict[str, Any],
        context: ExecutionContext,
    ) -> Optional[Any]:
        """
        Create a Strands tool from a plugin definition.

        The plugin must have:
        - name: Tool name
        - description: Tool description
        - factory: Callable(context, container) -> ITool

        Alternatively, the plugin may have:
        - class: Tool class that implements ITool

        Args:
            plugin: Plugin definition from registry.
            context: Execution context to inject.

        Returns:
            Strands tool (decorated function), or None on error.
        """
        try:
            tool_name = plugin.get("name", "unknown")

            # Get or create tool instance
            if "factory" in plugin:
                # Factory function pattern
                factory = plugin["factory"]
                tool_instance = factory(context, self._container)
            elif "class" in plugin:
                # Class pattern - instantiate with context and container
                tool_class = plugin["class"]
                tool_instance = tool_class(context=context, container=self._container)
            else:
                logger.error(f"Tool '{tool_name}' missing factory or class")
                return None

            # Track for cleanup
            self._created_tools.append(tool_instance)

            # Build Strands tool definition
            return self._to_strands_tool(tool_instance, context)

        except Exception as e:
            tool_name = plugin.get("name", "unknown")
            logger.error(f"Failed to create tool '{tool_name}': {e}")
            return None

    def _to_strands_tool(
        self,
        tool: ITool,
        context: ExecutionContext,
    ) -> Any:
        """
        Convert ITool to Strands tool using the @tool decorator.

        Args:
            tool: The tool instance.
            context: Execution context (captured in closure).

        Returns:
            Strands-compatible tool (decorated function).
        """
        def truncate(s: str, max_len: int = 500) -> str:
            """Truncate string for logging."""
            return s[:max_len] + "..." if len(s) > max_len else s

        async def handler(tool_context: ToolContext) -> str:
            """Execute tool and return JSON result.

            Uses ToolContext to get raw input params, bypassing Strands' signature-based validation.
            This allows dynamic tools with arbitrary parameter schemas.
            """
            # Check for cancellation before execution
            await context.check_cancelled()

            # Extract params from tool_context (Strands injects this)
            kwargs = tool_context.tool_use.get("input", {})

            # Log invocation with truncated params
            params_str = json.dumps(kwargs, default=str)
            logger.info(f"[TOOL] Invoking '{tool.name}' | params={truncate(params_str, 200)}")
            start_time = time.time()

            try:
                result = await tool.execute(kwargs, context)
                duration_ms = (time.time() - start_time) * 1000

                # Log result with truncation
                result_preview = truncate(result.content, 300) if result.content else "(empty)"
                logger.info(
                    f"[TOOL] Completed '{tool.name}' | "
                    f"success={result.success} | "
                    f"duration={duration_ms:.0f}ms | "
                    f"result={result_preview}"
                )

                # Return as JSON for agent consumption
                return json.dumps({
                    "success": result.success,
                    "content": result.content,
                    "error": result.error,
                })

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"[TOOL] Failed '{tool.name}' | "
                    f"duration={duration_ms:.0f}ms | "
                    f"error={str(e)}",
                    exc_info=True
                )
                # Return error as JSON (let agent decide how to proceed)
                return json.dumps({
                    "success": False,
                    "content": "",
                    "error": str(e),
                })

        # Use Strands @tool decorator with context=True to get ToolContext
        return strands_tool(
            name=tool.name,
            description=tool.description,
            inputSchema=tool.parameters,
            context=True,
        )(handler)

    def list_available_tools(self) -> List[str]:
        """
        List all available tools in the registry.

        Returns:
            List of tool names.
        """
        return self._registry.list_tools()

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            Tool plugin definition, or None if not found.
        """
        return self._registry.get_tool(tool_name)

    async def cleanup(self) -> None:
        """
        Close all tracked tools that implement ICloseable.

        Should be called after agent execution to release resources
        like network sessions, file handles, etc.
        """
        for tool in self._created_tools:
            if isinstance(tool, ICloseable):
                try:
                    await tool.close()
                    logger.debug(f"Closed tool: {getattr(tool, 'name', 'unknown')}")
                except Exception as e:
                    logger.warning(
                        f"Failed to close tool {getattr(tool, 'name', 'unknown')}: {e}"
                    )
        self._created_tools = []


def create_simple_tool(
    name: str,
    description: str,
    parameters: Dict[str, Any],
    handler: Callable[[Dict[str, Any], ExecutionContext], Any],
) -> Callable[[ExecutionContext, Container], ITool]:
    """
    Helper to create a simple tool factory.

    For tools that don't need complex dependency injection,
    this helper creates a factory function from a simple handler.

    Args:
        name: Tool name.
        description: Tool description.
        parameters: JSON Schema for parameters.
        handler: Async function(params, context) -> content.

    Returns:
        Factory function suitable for plugin registration.

    Example:
        def my_handler(params, context):
            return f"Hello, {params['name']}!"

        PLUGIN = {
            "type": "tool",
            "name": "greet",
            "factory": create_simple_tool(
                name="greet",
                description="Greet a user",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name to greet"}
                    },
                    "required": ["name"]
                },
                handler=my_handler
            ),
            "description": "Greet a user by name"
        }
    """
    class SimpleTool:
        def __init__(self, context: ExecutionContext, container: Container):
            self.name = name
            self.description = description
            self.parameters = parameters
            self._handler = handler
            self._context = context
            self._container = container

        async def execute(
            self,
            params: Dict[str, Any],
            context: ExecutionContext
        ) -> ToolResult:
            try:
                result = await self._handler(params, context)
                if isinstance(result, ToolResult):
                    return result
                return ToolResult(content=str(result), success=True)
            except Exception as e:
                return ToolResult(content="", success=False, error=str(e))

        def to_schema(self) -> Dict[str, Any]:
            return {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }

    def factory(context: ExecutionContext, container: Container) -> SimpleTool:
        return SimpleTool(context, container)

    return factory
