# Multi-Agent Patterns Reference

This guide covers the four primary orchestration patterns in Strands: Agent-as-Tool, Swarm, Graph, and Workflow.

## Table of Contents
1. [Agent-as-Tool Pattern](#agent-as-tool-pattern)
2. [Swarm Pattern](#swarm-pattern)
3. [Graph Pattern](#graph-pattern)
4. [Workflow Pattern](#workflow-pattern)
5. [Combining Patterns](#combining-patterns)
6. [Shared State](#shared-state)

---

## Agent-as-Tool Pattern

Transforms specialized agents into tools that an orchestrator agent can invoke. Best for hierarchical delegation.

### When to Use
- Need expert consultation without losing orchestrator control
- Subtasks require specialized knowledge or tools
- Want clear separation of concerns between agents

### Implementation

```python
from strands import Agent, tool
from strands_tools import calculator, python_repl

# Create specialist agent
data_analyst = Agent(
    name="analyst",
    system_prompt="You are a data analyst expert.",
    tools=[calculator, python_repl]
)

# Wrap as tool
@tool
def consult_analyst(query: str) -> str:
    """Consult the data analyst for statistical analysis.
    
    Args:
        query: The analysis question or task.
    
    Returns:
        Analysis results from the specialist.
    """
    return str(data_analyst(query))

# Orchestrator uses specialist as tool
orchestrator = Agent(
    system_prompt="You coordinate tasks. Use consult_analyst for data questions.",
    tools=[consult_analyst]
)

result = orchestrator("Analyze sales trends and recommend pricing strategy")
```

### Best Practices
- Give specialists focused system prompts
- Orchestrator should not need specialist's tools directly
- Use descriptive tool docstrings so orchestrator knows when to delegate

---

## Swarm Pattern

Autonomous collaboration where agents hand off tasks to each other. The path is emergent—agents decide the flow.

### When to Use
- Tasks require dynamic collaboration between specialists
- Optimal sequence isn't known upfront
- Problem benefits from iterative refinement between agents

### Implementation

```python
from strands import Agent
from strands.multiagent import Swarm

# Create specialized agents with handoff capabilities
researcher = Agent(
    name="researcher",
    system_prompt="""You research topics thoroughly. 
    Hand off to 'writer' when research is complete."""
)

writer = Agent(
    name="writer", 
    system_prompt="""You write content based on research.
    Hand off to 'editor' when draft is ready."""
)

editor = Agent(
    name="editor",
    system_prompt="""You polish and finalize content.
    Complete the task when editing is done."""
)

# Create swarm - agents coordinate autonomously
swarm = Swarm(
    [researcher, writer, editor],
    entry_point="researcher"  # Optional: specify starting agent
)

result = swarm("Create a blog post about quantum computing")
```

### Built-in Handoff Tools
Swarm agents automatically receive:
- `handoff`: Transfer control to another agent
- `complete`: Signal task completion

### Streaming Events

```python
async for event in swarm.stream_async("Design a REST API"):
    if event.get("type") == "handoff":
        print(f"Handoff: {event['from_agent']} → {event['to_agent']}")
```

### Configuration Options

```python
swarm = Swarm(
    agents,
    entry_point="coordinator",
    repetitive_handoff_detection_window=5,  # Detect ping-pong
    repetitive_handoff_min_unique_agents=2   # Min unique agents in window
)
```

---

## Graph Pattern

Deterministic directed graph where execution follows developer-defined edges and conditions.

### When to Use
- Need predictable, auditable execution paths
- Routing depends on input characteristics or agent output
- Require approval gates or human-in-the-loop points
- Want conditional branching based on results

### Implementation

```python
from strands import Agent
from strands.multiagent import GraphBuilder

# Create specialized agents
analyzer = Agent(
    name="analyzer",
    system_prompt="Analyze requests and determine complexity."
)

simple_handler = Agent(
    name="simple_handler",
    system_prompt="Handle simple, routine requests."
)

complex_handler = Agent(
    name="complex_handler", 
    system_prompt="Handle complex requests requiring deep analysis."
)

# Build graph with conditional routing
builder = GraphBuilder()
builder.add_node(analyzer, "analyze")
builder.add_node(simple_handler, "simple")
builder.add_node(complex_handler, "complex")

# Conditional edges based on analyzer output
def is_complex(state):
    return "complex" in state.get("last_output", "").lower()

builder.add_edge("analyze", "complex", condition=is_complex)
builder.add_edge("analyze", "simple", condition=lambda s: not is_complex(s))

builder.set_entry_point("analyze")
graph = builder.build()

result = graph("Process this customer request...")
```

### Cyclic Graphs (Feedback Loops)

```python
builder = GraphBuilder()
builder.add_node(writer, "draft")
builder.add_node(reviewer, "review")
builder.add_node(finalizer, "finalize")

# Create feedback loop
def needs_revision(state):
    return "revise" in state.get("last_output", "").lower()

builder.add_edge("draft", "review")
builder.add_edge("review", "draft", condition=needs_revision)  # Loop back
builder.add_edge("review", "finalize", condition=lambda s: not needs_revision(s))

graph = builder.build()
```

### Multimodal Input

```python
from strands.types.content import ContentBlock

content_blocks = [
    ContentBlock(text="Analyze this image:"),
    ContentBlock(image={"format": "png", "source": {"bytes": image_bytes}})
]

result = graph(content_blocks)
```

---

## Workflow Pattern

Fixed task dependencies with automatic parallelization. Developer defines tasks and dependencies explicitly.

### When to Use
- Process is repeatable and well-defined
- Independent tasks can run in parallel
- Need deterministic execution order
- Want to encapsulate multi-step processes as reusable tools

### Implementation

```python
from strands import Agent
from strands_tools import workflow

# Define agents for each task
loader = Agent(name="loader", system_prompt="Load and validate data")
processor_a = Agent(name="processor_a", system_prompt="Process segment A")
processor_b = Agent(name="processor_b", system_prompt="Process segment B")
aggregator = Agent(name="aggregator", system_prompt="Aggregate results")

# Use workflow tool - lets agent create workflows dynamically
orchestrator = Agent(
    tools=[workflow],
    system_prompt="""Create workflows to solve complex tasks.
    Define tasks and their dependencies."""
)

orchestrator("""
Create a data pipeline workflow:
1. load_data - Load the CSV file
2. process_segment_a - Process first half (depends on load_data)
3. process_segment_b - Process second half (depends on load_data)  
4. aggregate - Combine results (depends on both processors)
""")
```

### Direct Workflow Creation

```python
# Alternative: Create workflow programmatically
from strands.multiagent import Workflow

workflow = Workflow()
workflow.add_task("load", loader)
workflow.add_task("process_a", processor_a)
workflow.add_task("process_b", processor_b)
workflow.add_task("aggregate", aggregator)

# Define dependencies (process_a and process_b run in parallel after load)
workflow.add_dependency("process_a", "load")
workflow.add_dependency("process_b", "load")
workflow.add_dependency("aggregate", "process_a")
workflow.add_dependency("aggregate", "process_b")

result = workflow("Process the quarterly report")
```

---

## Combining Patterns

Patterns can be nested and composed:

```python
from strands import Agent, tool
from strands.multiagent import GraphBuilder, Swarm

# Swarm as a graph node
research_swarm = Swarm([
    Agent(name="medical", system_prompt="Medical research expert"),
    Agent(name="tech", system_prompt="Technology research expert"),
    Agent(name="econ", system_prompt="Economic research expert")
])

analyst = Agent(system_prompt="Synthesize research findings")

# Graph that uses swarm as a node
builder = GraphBuilder()
builder.add_node(research_swarm, "research_team")
builder.add_node(analyst, "analysis")
builder.add_edge("research_team", "analysis")

graph = builder.build()
result = graph("Research AI impact on healthcare")
```

### Graph Inside Agent-as-Tool

```python
# Wrap complex graph as a tool
approval_graph = build_approval_graph()  # Your graph

@tool
def run_approval_process(request: str) -> str:
    """Run the multi-step approval workflow."""
    return str(approval_graph(request))

agent = Agent(tools=[run_approval_process])
```

---

## Shared State

All multi-agent patterns support shared state via `invocation_state`:

```python
# Pass shared context to all agents
shared_context = {
    "user_id": "12345",
    "preferences": {"language": "en"},
    "session_data": {}
}

result = swarm(
    "Process user request",
    invocation_state=shared_context
)

# Or with graphs
result = graph(
    "Handle request",
    invocation_state=shared_context
)
```

### Accessing State in Tools

```python
@tool
def stateful_tool(query: str, tool_context: dict) -> str:
    """Tool that accesses shared state.
    
    Args:
        query: The user query.
        tool_context: Automatically injected context.
    """
    user_id = tool_context.get("invocation_state", {}).get("user_id")
    return f"Processing for user {user_id}: {query}"
```
