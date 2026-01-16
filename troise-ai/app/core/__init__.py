"""TROISE AI Core - Plugin Architecture with Skills + Agents."""
from .config import Config, ModelCapabilities, BackendConfig, ModelPriority
from .context import ExecutionContext
from .exceptions import TroiseError, AgentCancelled, RoutingError
from .registry import PluginRegistry
from .container import Container, create_container, ContainerError, ServiceNotFoundError
from .router import Router, RoutingResult
from .tool_factory import ToolFactory, create_simple_tool
from .executor import Executor, ExecutionResult
from .base_agent import BaseAgent
from .streaming import (
    StreamFilter,
    AgentStreamHandler,
    stream_agent_response,
    StreamingConfig,
    StreamingManager,
    get_streaming_manager,
)

__all__ = [
    # Configuration
    "Config",
    "ModelCapabilities",
    "BackendConfig",
    "ModelPriority",
    # Context
    "ExecutionContext",
    # Exceptions
    "TroiseError",
    "AgentCancelled",
    "RoutingError",
    "ContainerError",
    "ServiceNotFoundError",
    # Registry
    "PluginRegistry",
    # Container
    "Container",
    "create_container",
    # Router
    "Router",
    "RoutingResult",
    # Tool Factory
    "ToolFactory",
    "create_simple_tool",
    # Executor
    "Executor",
    "ExecutionResult",
    # Base Agent
    "BaseAgent",
    # Streaming
    "StreamFilter",
    "AgentStreamHandler",
    "stream_agent_response",
    "StreamingConfig",
    "StreamingManager",
    "get_streaming_manager",
]
