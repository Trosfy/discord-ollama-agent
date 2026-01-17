# Tools Reference

This guide covers tool creation, the strands_tools package, and MCP integration.

## Table of Contents
1. [The @tool Decorator](#the-tool-decorator)
2. [strands_tools Package](#strands_tools-package)
3. [MCP Integration](#mcp-integration)
4. [Tool Loading Patterns](#tool-loading-patterns)
5. [Advanced Tool Patterns](#advanced-tool-patterns)

---

## The @tool Decorator

Transform any Python function into a Strands tool with automatic schema generation.

### Basic Usage

```python
from strands import Agent, tool

@tool
def weather(city: str, units: str = "celsius") -> dict:
    """Get current weather for a city.
    
    Args:
        city: Name of the city.
        units: Temperature units (celsius or fahrenheit).
    
    Returns:
        Weather data including temperature and conditions.
    """
    # Your implementation
    return {
        "city": city,
        "temperature": 22,
        "units": units,
        "conditions": "sunny"
    }

agent = Agent(tools=[weather])
agent("What's the weather in Tokyo?")
```

### Type Annotations

Strands extracts parameter types and descriptions from docstrings:

```python
from typing import List, Optional

@tool
def search_documents(
    query: str,
    max_results: int = 10,
    filters: Optional[List[str]] = None
) -> dict:
    """Search the document database.
    
    Args:
        query: Search query string.
        max_results: Maximum results to return (default: 10).
        filters: Optional list of filter tags.
    
    Returns:
        Search results with document IDs and snippets.
    """
    # Implementation
    return {"results": [...]}
```

### Returning Tool Results

Standard return format:

```python
@tool
def my_tool(param: str) -> dict:
    """Tool description."""
    return {
        "status": "success",
        "content": [{"text": "Result text here"}]
    }
```

For errors:

```python
@tool
def risky_tool(param: str) -> dict:
    """Tool that might fail."""
    try:
        result = do_something(param)
        return {"status": "success", "content": [{"text": result}]}
    except Exception as e:
        return {"status": "error", "content": [{"text": f"Error: {str(e)}"}]}
```

### Accessing Tool Context

Tools can access invocation context:

```python
@tool
def context_aware_tool(query: str, tool_context: dict) -> str:
    """Tool with context access.
    
    Args:
        query: User query.
        tool_context: Injected automatically by Strands.
    """
    # Access shared state
    state = tool_context.get("invocation_state", {})
    user_id = state.get("user_id")
    
    # Access conversation history
    messages = tool_context.get("messages", [])
    
    return f"Processing for {user_id}"
```

---

## strands_tools Package

Community-maintained tools for common operations.

### Installation

```bash
pip install strands-agents-tools
```

### Available Tools

| Tool | Description | Import |
|------|-------------|--------|
| `calculator` | Mathematical operations | `from strands_tools import calculator` |
| `current_time` | Current time/timezone | `from strands_tools import current_time` |
| `file_read` | Read file contents | `from strands_tools import file_read` |
| `file_write` | Write to files | `from strands_tools import file_write` |
| `editor` | Advanced file editing | `from strands_tools import editor` |
| `http_request` | HTTP client with auth | `from strands_tools import http_request` |
| `python_repl` | Execute Python code | `from strands_tools import python_repl` |
| `shell` | Execute shell commands | `from strands_tools import shell` |
| `memory` | Persistent memory | `from strands_tools import memory` |
| `retrieve` | Bedrock KB retrieval | `from strands_tools import retrieve` |

### Multi-Agent Tools

| Tool | Description | Pattern |
|------|-------------|---------|
| `graph` | Create agent graphs dynamically | Graph |
| `swarm` | Create agent swarms dynamically | Swarm |
| `workflow` | Create workflows dynamically | Workflow |

### Usage Examples

```python
from strands import Agent
from strands_tools import calculator, file_read, http_request, python_repl

agent = Agent(
    system_prompt="You are a helpful coding assistant.",
    tools=[calculator, file_read, http_request, python_repl]
)

# Agent can now calculate, read files, make HTTP requests, run Python
agent("Read config.json and calculate the sum of all numeric values")
```

### Memory Tool

```python
from strands import Agent
from strands_tools import memory

agent = Agent(
    system_prompt="Remember user preferences using the memory tool.",
    tools=[memory]
)

agent("Remember that I prefer dark mode")
agent("What are my preferences?")  # Recalls stored memory
```

---

## MCP Integration

Model Context Protocol enables connecting to external tool servers.

### Stdio Transport (Local Processes)

```python
from mcp import stdio_client, StdioServerParameters
from strands import Agent
from strands.tools.mcp import MCPClient

# Connect to MCP server via stdio
mcp_client = MCPClient(lambda: stdio_client(
    StdioServerParameters(
        command="uvx",
        args=["awslabs.aws-documentation-mcp-server@latest"]
    )
))

# Use with context manager
with mcp_client:
    tools = mcp_client.list_tools_sync()
    agent = Agent(tools=tools)
    agent("Tell me about Amazon S3")
```

### SSE Transport (HTTP)

```python
from mcp.client.sse import sse_client
from strands.tools.mcp import MCPClient

sse_client = MCPClient(lambda: sse_client("http://localhost:8000/sse"))

with sse_client:
    agent = Agent(tools=sse_client.list_tools_sync())
```

### Streamable HTTP Transport

```python
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient

http_client = MCPClient(
    lambda: streamablehttp_client(
        url="https://api.example.com/mcp/",
        headers={"Authorization": f"Bearer {token}"}
    )
)
```

### AWS IAM Authentication

```python
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands.tools.mcp import MCPClient

mcp_client = MCPClient(lambda: aws_iam_streamablehttp_client(
    endpoint="https://your-service.us-east-1.amazonaws.com/mcp",
    aws_region="us-east-1",
    aws_service="bedrock-agentcore"
))
```

### Managed Integration (Experimental)

```python
# Direct usage - lifecycle managed automatically
agent = Agent(tools=[mcp_client])
response = agent("What is AWS Lambda?")
```

### Multiple MCP Servers

```python
with aws_docs_client, github_client:
    combined_tools = (
        aws_docs_client.list_tools_sync() + 
        github_client.list_tools_sync()
    )
    agent = Agent(tools=combined_tools)
```

---

## Tool Loading Patterns

### Automatic Directory Loading

```python
# Enable automatic loading from ./tools/ directory
agent = Agent(load_tools_from_directory=True)
```

⚠️ Security: Only trusted code should be in the tools directory.

### Dynamic Tool Loading

```python
from strands.tools import load_tool

# Load from file path
tool = load_tool("./path/to/my_tool.py")

# Load from module
tool = load_tool("strands_tools.calculator")

# Load specific function from module
tool = load_tool("my_module:specific_tool")
```

### Module-Based Tools

Create a tool as a module file:

```python
# tools/weather.py
from strands.types.tools import ToolResult, ToolUse

TOOL_SPEC = {
    "name": "weather",
    "description": "Get weather for a location",
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name"
                }
            },
            "required": ["location"]
        }
    }
}

def weather(tool_use: ToolUse) -> ToolResult:
    location = tool_use["input"]["location"]
    # Implementation
    return ToolResult(content=[{"text": f"Weather in {location}: Sunny"}])
```

---

## Advanced Tool Patterns

### Batch Tool (Parallel Execution)

```python
from strands_tools import batch

agent = Agent(tools=[batch, tool_a, tool_b])

# Agent can call multiple tools in parallel
agent.tool.batch(invocations=[
    {"name": "tool_a", "arguments": {"param": "value1"}},
    {"name": "tool_b", "arguments": {"param": "value2"}}
])
```

### Tool with Streaming

```python
@tool
def streaming_tool(query: str) -> dict:
    """Tool that yields streaming results."""
    for chunk in process_stream(query):
        yield {"partial": chunk}
    return {"status": "complete"}
```

### Async Tools

```python
import asyncio
from strands import tool

@tool
async def async_tool(query: str) -> dict:
    """Async tool implementation."""
    result = await async_operation(query)
    return {"content": [{"text": result}]}
```

### Tool Validation

```python
@tool
def validated_tool(email: str, count: int) -> dict:
    """Tool with input validation.
    
    Args:
        email: Valid email address.
        count: Positive integer.
    """
    if "@" not in email:
        return {"status": "error", "content": [{"text": "Invalid email"}]}
    if count < 1:
        return {"status": "error", "content": [{"text": "Count must be positive"}]}
    
    return {"status": "success", "content": [{"text": f"Processed {count} for {email}"}]}
```
