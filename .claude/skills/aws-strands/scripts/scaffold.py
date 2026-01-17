#!/usr/bin/env python3
"""
Strands Project Scaffolding Script

Generates starter code for different Strands agent patterns.

Usage:
    python scaffold.py <pattern> <output_dir>
    
Patterns:
    single      - Basic single agent with tools
    agent-tool  - Agent-as-tool hierarchical pattern
    swarm       - Swarm multi-agent pattern
    graph       - Graph-based workflow pattern
    workflow    - Workflow with dependencies
"""

import os
import sys
from pathlib import Path

TEMPLATES = {
    "single": '''"""Basic Strands agent with custom tools."""
from strands import Agent, tool
from strands_tools import calculator

@tool
def greet(name: str) -> str:
    """Greet a user by name.
    
    Args:
        name: The name of the user to greet.
    
    Returns:
        A greeting message.
    """
    return f"Hello, {name}! How can I help you today?"

def main():
    agent = Agent(
        system_prompt="""You are a helpful assistant. 
        Use the greet tool to welcome users and calculator for math.""",
        tools=[greet, calculator]
    )
    
    # Interactive loop
    print("Strands Agent Ready. Type 'quit' to exit.")
    while True:
        user_input = input("\\nYou: ").strip()
        if user_input.lower() == 'quit':
            break
        response = agent(user_input)
        print(f"\\nAgent: {response}")

if __name__ == "__main__":
    main()
''',

    "agent-tool": '''"""Agent-as-tool pattern with specialist delegation."""
from strands import Agent, tool
from strands_tools import calculator, python_repl

# Create specialist agents
math_specialist = Agent(
    name="math_specialist",
    system_prompt="You are a mathematics expert. Solve problems step by step.",
    tools=[calculator]
)

code_specialist = Agent(
    name="code_specialist", 
    system_prompt="You are a Python coding expert. Write clean, efficient code.",
    tools=[python_repl]
)

# Wrap specialists as tools
@tool
def consult_math_expert(problem: str) -> str:
    """Consult the math specialist for complex calculations.
    
    Args:
        problem: Mathematical problem or question.
    
    Returns:
        Solution from the math expert.
    """
    return str(math_specialist(problem))

@tool
def consult_code_expert(task: str) -> str:
    """Consult the coding specialist for programming tasks.
    
    Args:
        task: Programming task or code question.
    
    Returns:
        Solution from the code expert.
    """
    return str(code_specialist(task))

def main():
    # Orchestrator agent uses specialists as tools
    orchestrator = Agent(
        system_prompt="""You are a helpful coordinator.
        Delegate math problems to the math expert.
        Delegate coding tasks to the code expert.
        Synthesize their responses for the user.""",
        tools=[consult_math_expert, consult_code_expert]
    )
    
    print("Orchestrator Agent Ready. Type 'quit' to exit.")
    while True:
        user_input = input("\\nYou: ").strip()
        if user_input.lower() == 'quit':
            break
        response = orchestrator(user_input)
        print(f"\\nOrchestrator: {response}")

if __name__ == "__main__":
    main()
''',

    "swarm": '''"""Swarm pattern with autonomous agent collaboration."""
from strands import Agent
from strands.multiagent import Swarm

def main():
    # Create specialized agents that can hand off to each other
    researcher = Agent(
        name="researcher",
        system_prompt="""You are a research specialist.
        Gather information on topics thoroughly.
        When research is complete, hand off to 'writer' to create content."""
    )
    
    writer = Agent(
        name="writer",
        system_prompt="""You are a content writer.
        Create engaging content based on research.
        When the draft is ready, hand off to 'editor' for review."""
    )
    
    editor = Agent(
        name="editor",
        system_prompt="""You are an editor.
        Review and polish content for clarity and accuracy.
        Complete the task when editing is done."""
    )
    
    # Create swarm - agents coordinate autonomously
    swarm = Swarm(
        [researcher, writer, editor],
        entry_point="researcher"
    )
    
    print("Content Creation Swarm Ready. Type 'quit' to exit.")
    while True:
        user_input = input("\\nTopic: ").strip()
        if user_input.lower() == 'quit':
            break
        
        print("\\nSwarm processing... (agents collaborating)")
        result = swarm(f"Create content about: {user_input}")
        print(f"\\nFinal Output:\\n{result}")

if __name__ == "__main__":
    main()
''',

    "graph": '''"""Graph pattern with conditional routing."""
from strands import Agent
from strands.multiagent import GraphBuilder

def main():
    # Create specialized agents for different paths
    classifier = Agent(
        name="classifier",
        system_prompt="""Classify incoming requests as either:
        - 'technical': For coding, debugging, or technical questions
        - 'creative': For writing, brainstorming, or creative tasks
        
        Always include the classification in your response."""
    )
    
    tech_agent = Agent(
        name="tech_agent",
        system_prompt="You are a technical expert. Provide detailed technical solutions."
    )
    
    creative_agent = Agent(
        name="creative_agent",
        system_prompt="You are a creative writer. Provide imaginative and engaging content."
    )
    
    # Build graph with conditional routing
    builder = GraphBuilder()
    builder.add_node(classifier, "classify")
    builder.add_node(tech_agent, "technical")
    builder.add_node(creative_agent, "creative")
    
    # Define routing conditions
    def is_technical(state):
        output = state.get("last_output", "").lower()
        return "technical" in output
    
    def is_creative(state):
        output = state.get("last_output", "").lower()
        return "creative" in output
    
    builder.add_edge("classify", "technical", condition=is_technical)
    builder.add_edge("classify", "creative", condition=is_creative)
    builder.set_entry_point("classify")
    
    graph = builder.build()
    
    print("Routing Graph Ready. Type 'quit' to exit.")
    while True:
        user_input = input("\\nRequest: ").strip()
        if user_input.lower() == 'quit':
            break
        
        print("\\nProcessing through graph...")
        result = graph(user_input)
        print(f"\\nResult: {result}")

if __name__ == "__main__":
    main()
''',

    "workflow": '''"""Workflow pattern with task dependencies."""
from strands import Agent
from strands_tools import workflow

def main():
    # Agent that can create and execute workflows
    orchestrator = Agent(
        system_prompt="""You create and execute workflows for complex tasks.
        
        When given a multi-step task:
        1. Break it into discrete steps
        2. Identify dependencies between steps
        3. Create a workflow with the workflow tool
        4. Execute and report results
        
        Steps that don't depend on each other can run in parallel.""",
        tools=[workflow]
    )
    
    print("Workflow Orchestrator Ready. Type 'quit' to exit.")
    print("\\nExample: 'Create a report: research AI trends, analyze data, write summary'")
    
    while True:
        user_input = input("\\nTask: ").strip()
        if user_input.lower() == 'quit':
            break
        
        print("\\nCreating and executing workflow...")
        result = orchestrator(user_input)
        print(f"\\nResult: {result}")

if __name__ == "__main__":
    main()
'''
}

REQUIREMENTS = """strands-agents>=1.0.0
strands-agents-tools>=1.0.0
"""

def scaffold(pattern: str, output_dir: str):
    """Generate scaffold files for the given pattern."""
    if pattern not in TEMPLATES:
        print(f"Unknown pattern: {pattern}")
        print(f"Available patterns: {', '.join(TEMPLATES.keys())}")
        sys.exit(1)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Write main file
    main_file = output_path / "main.py"
    main_file.write_text(TEMPLATES[pattern])
    print(f"Created: {main_file}")
    
    # Write requirements
    req_file = output_path / "requirements.txt"
    req_file.write_text(REQUIREMENTS)
    print(f"Created: {req_file}")
    
    print(f"\nScaffold complete! To run:")
    print(f"  cd {output_dir}")
    print(f"  pip install -r requirements.txt")
    print(f"  python main.py")

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    pattern = sys.argv[1]
    output_dir = sys.argv[2]
    scaffold(pattern, output_dir)

if __name__ == "__main__":
    main()
