# AWS Strands SDK - Comprehensive Reference Guide

**Version:** 1.20.0 (strands-agents) | 0.2.18 (strands-agents-tools)

This guide documents all major classes, features, and use cases of the AWS Strands SDK for building AI agents.

---

## Table of Contents

1. [Core Classes](#core-classes)
2. [Tool System](#tool-system)
3. [Multi-Agent Orchestration](#multi-agent-orchestration)
4. [Hooks System](#hooks-system)
5. [Session Management](#session-management)
6. [Models & Providers](#models--providers)
7. [Conversation Management](#conversation-management)
8. [MCP Integration](#mcp-integration)
9. [Telemetry & Observability](#telemetry--observability)
10. [Experimental Features](#experimental-features)
11. [Pre-built Tools](#pre-built-tools)

---

## Core Classes

### Agent

**Import:** `from strands import Agent`

**Purpose:** Core agent interface that orchestrates conversation, model inference, and tool execution.

**Constructor Signature:**
```python
Agent(
    model: Union[Model, str, None] = None,
    messages: Optional[Messages] = None,
    tools: Optional[list[Union[str, dict[str, str], ToolProvider, Any]]] = None,
    system_prompt: Optional[str | list[SystemContentBlock]] = None,
    structured_output_model: Optional[Type[BaseModel]] = None,
    callback_handler: Optional[Callable[..., Any]] = None,
    conversation_manager: Optional[ConversationManager] = None,
    record_direct_tool_call: bool = True,
    load_tools_from_directory: bool = False,
    trace_attributes: Optional[Mapping[str, AttributeValue]] = None,
    # Keyword-only parameters
    agent_id: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    state: Optional[Union[AgentState, dict]] = None,
    hooks: Optional[list[HookProvider]] = None,
    session_manager: Optional[SessionManager] = None,
    tool_executor: Optional[ToolExecutor] = None,
)
```

**Use Cases:**

1. **Basic Conversational Agent**
```python
from strands import Agent
from strands.models.bedrock import BedrockModel

model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")
agent = Agent(
    model=model,
    name="Assistant",
    description="A helpful AI assistant"
)

result = agent("What's the weather like?")
print(result.final_message)
```

2. **Agent with Tools**
```python
from strands import Agent, tool

@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"The weather in {city} is sunny"

agent = Agent(
    model=model,
    tools=[get_weather],
    system_prompt="You are a helpful weather assistant"
)

result = agent("What's the weather in Seattle?")
```

3. **Agent with Session Management**
```python
from strands import Agent
from strands.session import FileSessionManager

session_manager = FileSessionManager(
    session_id="user_123",
    base_dir="/tmp/sessions"
)

agent = Agent(
    model=model,
    session_manager=session_manager,
    name="PersistentAgent"
)

# Conversation persists across runs
result = agent("Remember this: my name is Alice")
```

4. **Agent with State**
```python
from strands.agent.state import AgentState

initial_state = AgentState({"user_id": "123", "context": "shopping"})

agent = Agent(
    model=model,
    state=initial_state
)

# Tools can access agent.state.get("user_id")
```

**Key Methods:**
- `agent(prompt)` - Synchronous invocation
- `agent.stream_async(prompt)` - Async streaming
- `agent.structured_output(model_type, prompt)` - Get structured Pydantic output
- `agent.tool.tool_name(**kwargs)` - Direct tool invocation
- `agent.state.get(key)`, `agent.state.set(key, value)` - State management

---

### AgentState

**Import:** `from strands.agent.state import AgentState`

**Purpose:** Cross-tool data storage and sharing within an agent.

**Use Case:**
```python
from strands import Agent, tool, ToolContext
from strands.agent.state import AgentState

@tool(context=True)
def store_data(key: str, value: str, tool_context: ToolContext) -> str:
    """Store data in agent state."""
    tool_context.agent.state.set(key, value)
    return f"Stored {key}={value}"

@tool(context=True)
def retrieve_data(key: str, tool_context: ToolContext) -> str:
    """Retrieve data from agent state."""
    value = tool_context.agent.state.get(key)
    return f"Retrieved: {value}"

agent = Agent(
    model=model,
    tools=[store_data, retrieve_data],
    state=AgentState()
)
```

---

## Tool System

### @tool Decorator

**Import:** `from strands import tool`

**Purpose:** Transform Python functions into agent tools with automatic schema generation.

**Signatures:**
```python
@tool
def my_function(param: str) -> str:
    ...

@tool(
    name="custom_name",
    description="Custom description",
    context=True  # or context="my_context_param"
)
def my_function_with_context(param: str, my_context_param: ToolContext) -> str:
    ...
```

**Use Cases:**

1. **Basic Tool**
```python
from strands import tool

@tool
def calculator(expression: str) -> dict:
    """
    Calculate a mathematical expression.

    Args:
        expression: The math expression to evaluate

    Returns:
        Result of the calculation
    """
    result = eval(expression)  # Note: Use safe evaluation in production
    return {
        "status": "success",
        "content": [{"text": f"Result: {result}"}]
    }
```

2. **Tool with Context Access**
```python
from strands import tool, ToolContext

@tool(context=True)
def personalized_greeting(name: str, tool_context: ToolContext) -> dict:
    """
    Generate a personalized greeting.

    Args:
        name: The person's name
    """
    # Access agent state
    user_id = tool_context.invocation_state.get("user_id", "unknown")

    # Access tool use details
    tool_id = tool_context.tool_use["toolUseId"]

    # Access agent
    agent_name = tool_context.agent.name

    return {
        "status": "success",
        "content": [{"text": f"Hello {name}! (user:{user_id}, agent:{agent_name})"}]
    }
```

3. **Async Tool**
```python
import asyncio
from strands import tool

@tool
async def fetch_data(url: str) -> dict:
    """
    Fetch data from a URL asynchronously.

    Args:
        url: The URL to fetch
    """
    await asyncio.sleep(1)  # Simulate network delay
    return {
        "status": "success",
        "content": [{"text": f"Data from {url}"}]
    }
```

4. **Streaming Tool (Async Generator)**
```python
from strands import tool
from typing import AsyncGenerator

@tool
async def stream_results(query: str) -> AsyncGenerator[dict, None]:
    """
    Stream results incrementally.

    Args:
        query: The search query
    """
    for i in range(5):
        yield {"text": f"Result {i} for '{query}'"}
        await asyncio.sleep(0.5)

    # Final result
    yield {
        "status": "success",
        "content": [{"text": f"Completed search for '{query}'"}]
    }
```

---

### ToolContext

**Import:** `from strands import ToolContext`

**Purpose:** Provides framework-level information to tools.

**Attributes:**
- `tool_use: ToolUse` - The tool invocation details (toolUseId, name, input)
- `agent: Agent` - The agent executing the tool
- `invocation_state: dict[str, Any]` - Caller-provided kwargs from agent invocation

**Use Case:**
```python
from strands import tool, ToolContext

@tool(context=True)
def advanced_tool(param1: str, tool_context: ToolContext) -> dict:
    # Get tool invocation ID
    tool_id = tool_context.tool_use["toolUseId"]

    # Get tool input parameters
    tool_input = tool_context.tool_use["input"]

    # Access agent state
    cached_data = tool_context.agent.state.get("cache")

    # Access invocation state (request-level context)
    request_id = tool_context.invocation_state.get("request_id")

    # Modify agent state
    tool_context.agent.state.set("last_tool", tool_context.tool_use["name"])

    return {
        "status": "success",
        "content": [{"text": f"Processed {param1} (tool_id: {tool_id})"}]
    }
```

---

### Tool Executors

**Import:** `from strands.tools.executors import ConcurrentToolExecutor, SequentialToolExecutor`

**Purpose:** Control how multiple tools are executed (parallel vs sequential).

**Use Case:**
```python
from strands import Agent
from strands.tools.executors import ConcurrentToolExecutor

# Execute tools in parallel (default)
agent = Agent(
    model=model,
    tools=[tool1, tool2, tool3],
    tool_executor=ConcurrentToolExecutor()
)

# Or sequential execution
from strands.tools.executors import SequentialToolExecutor
agent = Agent(
    model=model,
    tools=[tool1, tool2, tool3],
    tool_executor=SequentialToolExecutor()
)
```

---

## Multi-Agent Orchestration

### Swarm

**Import:** `from strands.multiagent import Swarm`

**Purpose:** Self-organizing agent teams with shared context and autonomous coordination.

**Constructor:**
```python
Swarm(
    nodes: list[SwarmNode],
    swarm_id: Optional[str] = None,
    hooks: Optional[list[HookProvider]] = None,
    session_manager: Optional[SessionManager] = None,
    max_node_executions: Optional[int] = 20,
    execution_timeout: Optional[float] = 300.0,
)
```

**Use Case:**
```python
from strands import Agent
from strands.multiagent import Swarm
from strands.multiagent.swarm import SwarmNode

# Create specialized agents
researcher = Agent(
    name="Researcher",
    system_prompt="You are a research specialist. Focus on gathering information.",
    model=model,
    tools=[search_tool, retrieve_tool]
)

writer = Agent(
    name="Writer",
    system_prompt="You are a content writer. Focus on creating engaging content.",
    model=model,
    tools=[file_write_tool]
)

reviewer = Agent(
    name="Reviewer",
    system_prompt="You are a quality reviewer. Focus on improving content.",
    model=model,
    tools=[file_read_tool, file_write_tool]
)

# Create swarm
swarm = Swarm(
    nodes=[
        SwarmNode(node_id="researcher", executor=researcher),
        SwarmNode(node_id="writer", executor=writer),
        SwarmNode(node_id="reviewer", executor=reviewer),
    ],
    swarm_id="content_creation_team",
    max_node_executions=15,
    execution_timeout=600.0
)

# Execute swarm
result = swarm("Create a blog post about AI agents")
print(f"Status: {result.status}")
print(f"Final message: {result.final_message}")
print(f"Nodes executed: {len(result.execution_order)}")
```

**Key Features:**
- Agents autonomously decide when to collaborate
- Shared working memory across all agents
- Built-in coordination tools (`handoff_to_agent`, `complete_swarm_task`)
- Automatic state reset between invocations

---

### Graph

**Import:** `from strands.multiagent import Graph`

**Purpose:** Deterministic graph-based agent orchestration with explicit dependencies.

**Constructor:**
```python
Graph(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    entry_points: list[GraphNode],
    graph_id: Optional[str] = None,
    hooks: Optional[list[HookProvider]] = None,
    session_manager: Optional[SessionManager] = None,
    max_node_executions: Optional[int] = 100,
    execution_timeout: Optional[float] = None,
)
```

**Use Case:**
```python
from strands import Agent
from strands.multiagent import Graph
from strands.multiagent.graph import GraphNode, GraphEdge

# Create agents
ingestion_agent = Agent(name="Ingestion", model=model, tools=[fetch_tool])
processing_agent = Agent(name="Processing", model=model, tools=[process_tool])
storage_agent = Agent(name="Storage", model=model, tools=[store_tool])
notification_agent = Agent(name="Notification", model=model, tools=[notify_tool])

# Define nodes
ingest_node = GraphNode(node_id="ingest", executor=ingestion_agent)
process_node = GraphNode(node_id="process", executor=processing_agent)
store_node = GraphNode(node_id="store", executor=storage_agent)
notify_node = GraphNode(node_id="notify", executor=notification_agent)

# Define edges (dependencies)
edges = [
    GraphEdge(from_node=ingest_node, to_node=process_node),
    GraphEdge(from_node=process_node, to_node=store_node),
    GraphEdge(from_node=store_node, to_node=notify_node),
]

# Conditional edge
def should_notify(state):
    return state.results.get("store", {}).get("success", False)

conditional_edge = GraphEdge(
    from_node=store_node,
    to_node=notify_node,
    condition=should_notify
)

# Create graph
graph = Graph(
    nodes=[ingest_node, process_node, store_node, notify_node],
    edges=edges,
    entry_points=[ingest_node],
    graph_id="data_pipeline"
)

# Execute
result = graph("Process data from source X")
print(f"Execution order: {[node.node_id for node in result.execution_order]}")
print(f"Completed: {result.completed_nodes}/{result.total_nodes}")
```

**Key Features:**
- Deterministic execution order based on dependencies
- Output from one node passed as input to connected nodes
- Support for conditional edges
- Cyclic graphs supported (feedback loops)
- Nested graphs (Graph as a node in another Graph)

---

## Hooks System

### Hook Events

**Import:** `from strands.hooks import *`

**Purpose:** Lifecycle hooks for monitoring and intercepting agent execution.

**Available Hook Events:**

1. **AgentInitializedEvent** - When agent is fully initialized
2. **BeforeInvocationEvent** - Before agent starts processing request
3. **AfterInvocationEvent** - After agent completes request
4. **MessageAddedEvent** - When message is added to conversation
5. **BeforeToolCallEvent** - Before tool execution (can cancel)
6. **AfterToolCallEvent** - After tool execution
7. **BeforeModelCallEvent** - Before model inference
8. **AfterModelCallEvent** - After model inference

**Use Case:**
```python
from strands import Agent
from strands.hooks import (
    HookProvider,
    BeforeToolCallEvent,
    AfterToolCallEvent,
    MessageAddedEvent
)
import logging

logger = logging.getLogger(__name__)

class LoggingHook(HookProvider):
    """Hook provider for logging agent activity."""

    def __init__(self):
        super().__init__()

    @HookProvider.on(BeforeToolCallEvent)
    def log_before_tool(self, event: BeforeToolCallEvent):
        tool_name = event.tool_use.get("name")
        logger.info(f"About to execute tool: {tool_name}")

        # Can modify or cancel tool execution
        if tool_name == "dangerous_tool":
            event.cancel_tool = "Tool execution not allowed"

    @HookProvider.on(AfterToolCallEvent)
    def log_after_tool(self, event: AfterToolCallEvent):
        tool_name = event.tool_use.get("name")
        status = event.result.get("status")
        logger.info(f"Tool {tool_name} completed with status: {status}")

        # Can modify result
        if status == "error":
            event.result["content"] = [{"text": "An error occurred"}]

    @HookProvider.on(MessageAddedEvent)
    def log_message(self, event: MessageAddedEvent):
        role = event.message.get("role")
        logger.info(f"Message added: role={role}")

# Use hook
agent = Agent(
    model=model,
    tools=[my_tool],
    hooks=[LoggingHook()]
)
```

**Advanced Hook: Tool Cancellation**
```python
class SecurityHook(HookProvider):
    """Prevent access to sensitive tools."""

    def __init__(self, allowed_tools: list[str]):
        super().__init__()
        self.allowed_tools = allowed_tools

    @HookProvider.on(BeforeToolCallEvent)
    def validate_tool_access(self, event: BeforeToolCallEvent):
        tool_name = event.tool_use.get("name")

        if tool_name not in self.allowed_tools:
            event.cancel_tool = f"Access denied: {tool_name} is not allowed"
            logger.warning(f"Blocked tool: {tool_name}")

agent = Agent(
    model=model,
    tools=[read_file, write_file, delete_file],
    hooks=[SecurityHook(allowed_tools=["read_file", "write_file"])]
)
```

---

## Session Management

### SessionManager

**Import:** `from strands.session import SessionManager`

**Purpose:** Persist conversation history and agent state across invocations.

**Built-in Implementations:**
- `FileSessionManager` - File-based persistence
- `S3SessionManager` - AWS S3 persistence
- `RepositorySessionManager` - Custom repository pattern

**Use Case 1: File Sessions**
```python
from strands import Agent
from strands.session import FileSessionManager

session_manager = FileSessionManager(
    session_id="user_alice_123",
    base_dir="/tmp/agent_sessions"
)

agent = Agent(
    model=model,
    session_manager=session_manager,
    name="PersistentAssistant"
)

# First conversation
result1 = agent("My name is Alice")
# Session saved to /tmp/agent_sessions/user_alice_123/

# Later conversation (in new process)
agent2 = Agent(
    model=model,
    session_manager=FileSessionManager(
        session_id="user_alice_123",
        base_dir="/tmp/agent_sessions"
    ),
    name="PersistentAssistant"
)

result2 = agent2("What's my name?")
# Agent remembers: "Your name is Alice"
```

**Use Case 2: S3 Sessions**
```python
from strands.session import S3SessionManager

session_manager = S3SessionManager(
    session_id="user_bob_456",
    bucket_name="my-agent-sessions",
    prefix="sessions/"
)

agent = Agent(
    model=model,
    session_manager=session_manager
)
```

**Use Case 3: Custom Repository**
```python
from strands.session import SessionRepository, RepositorySessionManager
from strands.types.session import Session, SessionAgent, SessionMessage
from typing import Optional

class DynamoDBSessionRepository(SessionRepository):
    """Custom DynamoDB implementation."""

    def __init__(self, table_name: str):
        self.table_name = table_name
        # Initialize DynamoDB client

    def create_session(self, session: Session, **kwargs) -> Session:
        # Store in DynamoDB
        pass

    def read_session(self, session_id: str, **kwargs) -> Optional[Session]:
        # Load from DynamoDB
        pass

    def create_message(self, session_id: str, agent_id: str,
                       session_message: SessionMessage, **kwargs) -> None:
        # Add message to DynamoDB
        pass

    def list_messages(self, session_id: str, agent_id: str,
                      limit: Optional[int] = None, offset: int = 0,
                      **kwargs) -> list[SessionMessage]:
        # List messages with pagination
        pass

    # Implement other abstract methods...

# Use custom repository
repository = DynamoDBSessionRepository(table_name="agent-sessions")
session_manager = RepositorySessionManager(
    session_id="user_123",
    repository=repository
)

agent = Agent(
    model=model,
    session_manager=session_manager
)
```

---

## Models & Providers

### Supported Model Providers

**Import:** `from strands.models import *`

**Available Providers:**
- `BedrockModel` - AWS Bedrock (Claude, Llama, Titan, etc.)
- `AnthropicModel` - Anthropic API (Claude)
- `OpenAIModel` - OpenAI API (GPT-4, GPT-3.5)
- `GeminiModel` - Google Gemini
- `OllamaModel` - Ollama (local models)
- `MistralModel` - Mistral AI
- `LiteLLMModel` - LiteLLM (unified interface)
- `SageMakerModel` - AWS SageMaker
- `LlamaCppModel` - llama.cpp
- `LlamaAPIModel` - Llama API
- `WriterModel` - Writer AI

**Use Case: Bedrock**
```python
from strands import Agent
from strands.models.bedrock import BedrockModel

model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    region_name="us-east-1"
)

agent = Agent(model=model)
```

**Use Case: OpenAI**
```python
from strands.models.openai import OpenAIModel

model = OpenAIModel(
    model_id="gpt-4o",
    api_key="your-api-key"
)

agent = Agent(model=model)
```

**Use Case: Multiple Models**
```python
# Different models for different agents
claude_agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
    name="Claude"
)

gpt_agent = Agent(
    model=OpenAIModel(model_id="gpt-4o"),
    name="GPT"
)

gemini_agent = Agent(
    model=GeminiModel(model_id="gemini-pro"),
    name="Gemini"
)
```

---

## Conversation Management

### ConversationManager

**Import:** `from strands.agent.conversation_manager import *`

**Purpose:** Control conversation history size and context length.

**Built-in Strategies:**
- `NullConversationManager` - No management (unlimited history)
- `SlidingWindowConversationManager` - Keep last N messages
- `SummarizingConversationManager` - Summarize old context

**Use Case 1: Sliding Window**
```python
from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager

conversation_manager = SlidingWindowConversationManager(
    max_messages=20  # Keep only last 20 messages
)

agent = Agent(
    model=model,
    conversation_manager=conversation_manager
)

# Long conversation automatically pruned
for i in range(100):
    agent(f"Message {i}")
# Only last 20 messages retained
```

**Use Case 2: Summarizing**
```python
from strands.agent.conversation_manager import SummarizingConversationManager

conversation_manager = SummarizingConversationManager(
    max_messages=50,
    summary_threshold=40  # Summarize when reaching 40 messages
)

agent = Agent(
    model=model,
    conversation_manager=conversation_manager
)

# Old messages automatically summarized
```

**Use Case 3: Custom Strategy**
```python
from strands.agent.conversation_manager import ConversationManager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from strands import Agent

class ImportanceBasedManager(ConversationManager):
    """Keep messages based on importance scores."""

    def __init__(self, max_messages: int):
        super().__init__()
        self.max_messages = max_messages

    def apply_management(self, agent: "Agent", **kwargs):
        if len(agent.messages) > self.max_messages:
            # Score messages by importance
            scored = [(i, self._score(msg)) for i, msg in enumerate(agent.messages)]
            scored.sort(key=lambda x: x[1], reverse=True)

            # Keep top N messages
            keep_indices = set(idx for idx, _ in scored[:self.max_messages])
            agent.messages = [msg for i, msg in enumerate(agent.messages) if i in keep_indices]

            self.removed_message_count += len(agent.messages) - self.max_messages

    def reduce_context(self, agent: "Agent", e: Optional[Exception] = None, **kwargs):
        # Remove lowest importance messages
        if len(agent.messages) > 0:
            scored = [(i, self._score(msg)) for i, msg in enumerate(agent.messages)]
            scored.sort(key=lambda x: x[1])
            # Remove bottom 25%
            remove_count = len(agent.messages) // 4
            remove_indices = set(idx for idx, _ in scored[:remove_count])
            agent.messages = [msg for i, msg in enumerate(agent.messages) if i not in remove_indices]

    def _score(self, message):
        # Custom importance scoring logic
        role = message.get("role")
        if role == "user":
            return 10
        elif role == "assistant":
            content = message.get("content", [])
            # Higher score for longer responses
            return len(str(content))
        return 1

agent = Agent(
    model=model,
    conversation_manager=ImportanceBasedManager(max_messages=30)
)
```

---

## MCP Integration

### MCPClient

**Import:** `from strands.tools.mcp import MCPClient`

**Purpose:** Connect to Model Context Protocol (MCP) servers to access external tools.

**Use Case 1: HTTP MCP Server**
```python
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from datetime import timedelta

# Create MCP client
def create_transport():
    return streamablehttp_client(
        url="https://mcp-server.example.com",
        timeout=timedelta(seconds=30)
    )

mcp_client = MCPClient(create_transport)

# Use as tool provider
with mcp_client:
    agent = Agent(
        model=model,
        tools=[mcp_client]
    )

    result = agent("Search the knowledge base for 'AWS Lambda'")
```

**Use Case 2: Stdio MCP Server**
```python
from mcp.client.stdio import stdio_client
from strands.tools.mcp import MCPClient

def create_stdio_transport():
    return stdio_client(
        command="node",
        args=["path/to/mcp-server.js"]
    )

mcp_client = MCPClient(create_stdio_transport)

with mcp_client:
    agent = Agent(model=model, tools=[mcp_client])
```

**Use Case 3: Tool Filtering**
```python
from strands.tools.mcp import MCPClient, ToolFilters
import re

# Only allow specific tools
filters = ToolFilters(
    allowed=[
        "search",  # Exact match
        re.compile("^query_.*"),  # Regex pattern
        lambda tool: "read" in tool.tool_name  # Custom filter
    ],
    rejected=[
        "delete",
        "drop_database"
    ]
)

mcp_client = MCPClient(
    create_transport,
    tool_filters=filters,
    prefix="mcp_"  # Prefix all tool names
)
```

---

## Telemetry & Observability

### StrandsTelemetry

**Import:** `from strands.telemetry.config import StrandsTelemetry`

**Purpose:** OpenTelemetry integration for distributed tracing and observability.

**Use Case 1: Datadog LLM Observability**
```python
import os
from strands import Agent
from strands.telemetry.config import StrandsTelemetry
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

# Configure environment
os.environ["OTEL_SERVICE_NAME"] = "my-agent-service"
os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"] = "gen_ai_latest_experimental"
os.environ["OTEL_EXPORTER_OTLP_TRACES_PROTOCOL"] = "http/protobuf"
os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = "https://otlp.datadoghq.com/v1/traces"
os.environ["OTEL_EXPORTER_OTLP_TRACES_HEADERS"] = f"dd-api-key={DD_API_KEY},dd-otlp-source=datadog"

# Initialize telemetry
resource = Resource.create()
tracer_provider = TracerProvider(resource=resource)
telemetry = StrandsTelemetry(tracer_provider=tracer_provider)
telemetry.setup_otlp_exporter()

# Create agent (automatically traced)
agent = Agent(model=model, tools=[my_tool])
```

**Use Case 2: Custom Tracing**
```python
from opentelemetry import trace
from opentelemetry.trace import Tracer

tracer: Tracer = trace.get_tracer(__name__)

@tool(context=True)
def traced_tool(param: str, tool_context: ToolContext) -> dict:
    """Tool with custom tracing."""
    with tracer.start_as_current_span("custom_operation") as span:
        span.set_attribute("param", param)
        span.set_attribute("user_id", tool_context.invocation_state.get("user_id"))

        # Do work
        result = process_data(param)

        span.set_attribute("result_size", len(result))

    return {"status": "success", "content": [{"text": result}]}
```

**Use Case 3: Custom Attributes**
```python
agent = Agent(
    model=model,
    trace_attributes={
        "environment": "production",
        "region": "us-east-1",
        "version": "1.2.3"
    }
)
```

---

## Experimental Features

### Bidirectional Agent (Bidi)

**Import:** `from strands.experimental.bidi import BidiAgent`

**Purpose:** Real-time bidirectional communication with streaming models (voice, etc.).

**Supported Models:**
- Gemini Live
- OpenAI Realtime
- AWS Nova Sonic

**Use Case:**
```python
from strands.experimental.bidi import BidiAgent
from strands.experimental.bidi.models import GeminiLiveModel
from strands.experimental.bidi.io import TextIO

model = GeminiLiveModel(
    model_id="gemini-2.0-flash-live-exp",
    api_key=api_key
)

async def main():
    agent = BidiAgent(
        model=model,
        io=TextIO(),
        system_prompt="You are a helpful assistant"
    )

    async with agent:
        await agent.run()

# Run with asyncio
import asyncio
asyncio.run(main())
```

---

### Steering

**Import:** `from strands.experimental.steering import *`

**Purpose:** Dynamic routing and action handling based on context.

**Use Case:**
```python
from strands.experimental.steering.core import Action, Context, Handler
from strands.experimental.steering.handlers.llm import LLMHandler

# Define custom actions
class SendEmailAction(Action):
    to: str
    subject: str
    body: str

class CreateTaskAction(Action):
    title: str
    description: str

# Create LLM-based handler
handler = LLMHandler(
    model=model,
    actions=[SendEmailAction, CreateTaskAction]
)

# Execute with context
context = Context(
    prompt="Send email to alice@example.com about project update"
)

result = handler.handle(context)
if isinstance(result, SendEmailAction):
    # Handle email sending
    send_email(result.to, result.subject, result.body)
elif isinstance(result, CreateTaskAction):
    # Handle task creation
    create_task(result.title, result.description)
```

---

## Pre-built Tools (strands-agents-tools)

### Available Tools

**Import:** `from strands_tools import *`

**Tool Categories:**

#### 1. **Multi-Agent Orchestration**
- `swarm` - Create custom agent swarms
- `agent_graph` - Graph-based agent workflows
- `use_agent` - Use another agent as a tool
- `a2a_client` - Agent-to-agent communication

#### 2. **File Operations**
- `file_read` - Read files
- `file_write` - Write files
- `editor` - Interactive file editing

#### 3. **Code Execution**
- `python_repl` - Python REPL
- `code_interpreter` - Safe code execution
- `shell` - Shell command execution

#### 4. **Web & Search**
- `tavily` - Tavily search API
- `exa` - Exa search API
- `http_request` - HTTP requests
- `browser` - Browser automation

#### 5. **Memory & State**
- `memory` - Simple memory storage
- `agent_core_memory` - AgentCore memory
- `mem0_memory` - Mem0 integration
- `mongodb_memory` - MongoDB storage
- `elasticsearch_memory` - Elasticsearch storage
- `journal` - Persistent journal

#### 6. **AI/ML**
- `generate_image` - Image generation
- `generate_image_stability` - Stability AI images
- `nova_reels` - AWS Nova video generation
- `use_llm` - Call another LLM
- `use_computer` - Computer use (Anthropic)

#### 7. **Utilities**
- `calculator` - Math calculations
- `current_time` - Current date/time
- `sleep` - Add delays
- `think` - Structured thinking
- `speak` - Text-to-speech
- `stop` - Stop execution

#### 8. **Communication**
- `slack` - Slack integration
- `handoff_to_user` - Hand off to human

#### 9. **Data & Retrieval**
- `retrieve` - Vector retrieval
- `mcp_client` - MCP client tool
- `load_tool` - Dynamic tool loading

#### 10. **Visualization**
- `diagram` - Generate diagrams
- `graph` - Generate graphs

#### 11. **Scheduling & Workflow**
- `cron` - Scheduled execution
- `workflow` - Workflow orchestration
- `batch` - Batch processing

#### 12. **Media**
- `image_reader` - Read images
- `chat_video` - Video chat
- `search_video` - Video search

#### 13. **Cloud Services**
- `use_aws` - AWS operations
- `bright_data` - Bright Data proxies
- `rss` - RSS feed reader

**Example Usage:**
```python
from strands import Agent
from strands_tools import calculator, current_time, file_write, http_request

agent = Agent(
    model=model,
    tools=[calculator, current_time, file_write, http_request],
    system_prompt="You are a helpful assistant with access to various tools"
)

result = agent("What's 25 * 17, and what time is it now?")
```

---

## Advanced Patterns

### Pattern 1: Agent with Custom Tool Provider

```python
from strands.experimental.tools import ToolProvider
from typing import AsyncGenerator

class MyToolProvider(ToolProvider):
    """Custom tool provider that dynamically loads tools."""

    async def get_tools(self) -> list[AgentTool]:
        # Load tools dynamically
        return [tool1, tool2, tool3]

    async def refresh_tools(self) -> None:
        # Refresh tool list
        pass

agent = Agent(
    model=model,
    tools=[MyToolProvider()]
)
```

### Pattern 2: Structured Output

```python
from pydantic import BaseModel
from strands import Agent

class WeatherResponse(BaseModel):
    temperature: float
    conditions: str
    humidity: int

agent = Agent(
    model=model,
    structured_output_model=WeatherResponse
)

# Returns typed Pydantic object
weather: WeatherResponse = agent("What's the weather in Seattle?")
print(f"Temperature: {weather.temperature}°F")
```

### Pattern 3: Multi-Agent Pipeline

```python
# Create specialized agents
data_agent = Agent(
    name="DataCollector",
    system_prompt="Collect and structure data",
    model=model,
    tools=[fetch_data, parse_data]
)

analysis_agent = Agent(
    name="Analyzer",
    system_prompt="Analyze data and extract insights",
    model=model,
    tools=[calculate, correlate]
)

report_agent = Agent(
    name="Reporter",
    system_prompt="Generate comprehensive reports",
    model=model,
    tools=[file_write, generate_chart]
)

# Pipeline execution
data_result = data_agent("Collect sales data for Q4")
analysis_result = analysis_agent(f"Analyze this data: {data_result.final_message}")
report_result = report_agent(f"Create report from analysis: {analysis_result.final_message}")
```

### Pattern 4: Error Recovery Hook

```python
from strands.hooks import HookProvider, AfterToolCallEvent

class ErrorRecoveryHook(HookProvider):
    """Automatically retry failed tools."""

    def __init__(self, max_retries: int = 3):
        super().__init__()
        self.max_retries = max_retries
        self.retry_counts = {}

    @HookProvider.on(AfterToolCallEvent)
    def handle_error(self, event: AfterToolCallEvent):
        if event.result["status"] == "error":
            tool_id = event.tool_use["toolUseId"]
            tool_name = event.tool_use["name"]

            # Track retries
            retry_count = self.retry_counts.get(tool_id, 0)

            if retry_count < self.max_retries:
                self.retry_counts[tool_id] = retry_count + 1
                logger.info(f"Retrying {tool_name} (attempt {retry_count + 1})")
                # Modify result to trigger retry
                event.result["content"] = [{
                    "text": f"Tool failed, retrying ({retry_count + 1}/{self.max_retries})"
                }]

agent = Agent(
    model=model,
    tools=[unreliable_tool],
    hooks=[ErrorRecoveryHook(max_retries=3)]
)
```

---

## Summary of Key Features

### 1. Tool Hooks
- **Before/After Tool Execution**
- **Tool Cancellation**
- **Result Modification**
- See: [Hooks System](#hooks-system)

### 2. Swarms
- **Self-organizing Agent Teams**
- **Shared Context**
- **Autonomous Coordination**
- See: [Swarm](#swarm)

### 3. Graphs
- **Deterministic Agent Workflows**
- **Explicit Dependencies**
- **Conditional Edges**
- See: [Graph](#graph)

### 4. Advanced Tool Features
- **ToolContext Access**
- **Async/Streaming Tools**
- **Custom Validation**
- See: [Tool System](#tool-system)

### 5. Session Management
- **Custom Repositories**
- **File/S3 Storage**
- **State Persistence**
- See: [Session Management](#session-management)

### 6. Conversation Management
- **Sliding Window**
- **Summarization**
- **Custom Strategies**
- See: [Conversation Management](#conversation-management)

### 7. MCP Integration
- **External Tool Servers**
- **Tool Filtering**
- **Multiple Protocols**
- See: [MCP Integration](#mcp-integration)

### 8. Observability
- **OpenTelemetry**
- **Datadog LLM Observability**
- **Custom Tracing**
- See: [Telemetry & Observability](#telemetry--observability)

---

## Quick Reference: Common Imports

```python
# Core
from strands import Agent, tool, ToolContext

# Models
from strands.models.bedrock import BedrockModel
from strands.models.openai import OpenAIModel
from strands.models.anthropic import AnthropicModel

# Multi-Agent
from strands.multiagent import Swarm, Graph
from strands.multiagent.swarm import SwarmNode
from strands.multiagent.graph import GraphNode, GraphEdge

# Hooks
from strands.hooks import HookProvider
from strands.hooks import (
    BeforeToolCallEvent,
    AfterToolCallEvent,
    MessageAddedEvent
)

# Session
from strands.session import (
    FileSessionManager,
    S3SessionManager,
    RepositorySessionManager,
    SessionRepository
)

# Conversation
from strands.agent.conversation_manager import (
    SlidingWindowConversationManager,
    SummarizingConversationManager
)

# MCP
from strands.tools.mcp import MCPClient

# Telemetry
from strands.telemetry.config import StrandsTelemetry

# State
from strands.agent.state import AgentState

# Tools
from strands_tools import (
    calculator,
    current_time,
    file_read,
    file_write,
    swarm,
    use_agent
)
```

---

## Package Versions

- **strands-agents**: 1.20.0
- **strands-agents-tools**: 0.2.18
- **Python**: 3.12+

---

## Additional Resources

- **Documentation**: https://strandsagents.com/
- **GitHub**: https://github.com/awslabs/strands
- **MCP Protocol**: https://modelcontextprotocol.io/

---

*Generated from AWS Strands SDK v1.20.0 (2025-10-29)*