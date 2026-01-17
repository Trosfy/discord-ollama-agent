---
name: aws-strands
description: Build AI agents using AWS Strands Agents SDK - a model-driven framework for single and multi-agent systems. Use when creating AI agents with tools, multi-agent orchestration (graphs, swarms, workflows), MCP integration, or deploying agents to AWS. Triggers on Strands, agentic AI, agent orchestration, multi-agent patterns, agent-as-tool, swarm agents, agent graphs, agent workflows.
---

# AWS Strands Agents SDK

Strands is AWS's open-source, model-driven SDK for building AI agents. Unlike workflow-heavy frameworks, Strands leverages LLM reasoning capabilities to handle planning and tool selection autonomously.

## Core Concepts

### Basic Agent Creation
```python
from strands import Agent

# Minimal agent with defaults (uses Amazon Bedrock Claude)
agent = Agent()
response = agent("Tell me about AI agents")

# Agent with system prompt and tools
from strands_tools import calculator, file_read
agent = Agent(
    system_prompt="You are a helpful assistant.",
    tools=[calculator, file_read]
)
```

### Custom Tools
```python
from strands import Agent, tool

@tool
def my_tool(param: str, count: int = 1) -> dict:
    """Tool description for the LLM.
    
    Args:
        param: What this parameter does.
        count: Number of iterations (default: 1).
    
    Returns:
        Result dictionary with status and content.
    """
    return {"status": "success", "content": [{"text": f"Processed {param}"}]}

agent = Agent(tools=[my_tool])
```

## Pattern Selection Guide

Choose the right multi-agent pattern based on your requirements:

| Pattern | Execution Path | Best For | Complexity |
|---------|---------------|----------|------------|
| **Single Agent** | Model-driven | Simple tasks, direct tool use | Low |
| **Agent-as-Tool** | Hierarchical delegation | Expert consultation, specialized subtasks | Low-Medium |
| **Swarm** | Emergent (agents decide) | Collaborative, exploratory tasks | Medium |
| **Graph** | Developer-defined with conditions | Deterministic workflows, approval gates | Medium-High |
| **Workflow** | Fixed dependencies | Repeatable processes, parallel execution | Medium |

### Decision Flow

1. **Can a single agent with tools solve it?** → Use single agent
2. **Need expert consultation without losing control?** → Agent-as-Tool
3. **Need agents to collaborate dynamically?** → Swarm
4. **Need deterministic routing with conditions?** → Graph  
5. **Need repeatable process with parallelization?** → Workflow

For detailed implementation guidance on each pattern, see [references/patterns.md](references/patterns.md).

## MCP Integration

Strands natively supports Model Context Protocol for accessing external tool servers:

```python
from mcp import stdio_client, StdioServerParameters
from strands import Agent
from strands.tools.mcp import MCPClient

mcp_client = MCPClient(lambda: stdio_client(
    StdioServerParameters(
        command="uvx",
        args=["awslabs.aws-documentation-mcp-server@latest"]
    )
))

with mcp_client:
    tools = mcp_client.list_tools_sync()
    agent = Agent(tools=tools)
    agent("What is AWS Lambda?")
```

## Installation

```bash
pip install strands-agents strands-agents-tools
```

For TypeScript:
```bash
npm install @strands-agents/sdk
```

## Model Providers

Default is Amazon Bedrock (Claude). Configure alternatives:

```python
from strands import Agent
from strands.models.anthropic import AnthropicModel
from strands.models.openai import OpenAIModel

# Anthropic direct
agent = Agent(model=AnthropicModel(model_id="claude-sonnet-4-20250514"))

# OpenAI
agent = Agent(model=OpenAIModel(model_id="gpt-4o"))
```

## Resources

- **Tools guide**: [references/tools.md](references/tools.md) - @tool decorator, MCP, strands_tools
- **Patterns guide**: [references/patterns.md](references/patterns.md) - Graph, Swarm, Workflow, Agent-as-Tool
- **Deployment guide**: [references/deployment.md](references/deployment.md) - AWS deployment options
