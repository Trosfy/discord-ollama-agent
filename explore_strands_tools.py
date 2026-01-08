"""Explore Strands SDK tools to find web_fetch functionality."""

from strands import Agent, tool, ToolContext
from strands.models.ollama import OllamaModel

# Import strands-agents-tools to explore available tools
try:
    from strands_tools import (
        calculator,
        current_time,
        web_fetch,  # Try importing web_fetch
    )
    print("✅ Successfully imported: calculator, current_time, web_fetch")

    # Inspect web_fetch
    print("\n=== web_fetch Tool Details ===")
    print(f"Type: {type(web_fetch)}")
    print(f"Name: {getattr(web_fetch, '__name__', 'N/A')}")
    print(f"Doc: {getattr(web_fetch, '__doc__', 'No documentation')}")

    # Try to get signature
    import inspect
    if callable(web_fetch):
        sig = inspect.signature(web_fetch)
        print(f"Signature: {sig}")

    # Check if it's a Strands tool
    if hasattr(web_fetch, '__strands_tool__'):
        print("✅ This is a Strands tool!")
        tool_info = web_fetch.__strands_tool__
        print(f"Tool info: {tool_info}")

    # Test web_fetch with a simple URL
    print("\n=== Testing web_fetch ===")
    print("Attempting to fetch: https://example.com")

    # Create a simple agent to test the tool
    model = OllamaModel(
        host="http://localhost:11434",
        model_id="gpt-oss:20b",
        temperature=0.1
    )

    agent = Agent(model=model, tools=[web_fetch])
    print("✅ Agent created with web_fetch tool")

    # Try to call web_fetch directly if possible
    try:
        result = web_fetch("https://example.com")
        print(f"Direct call result: {result}")
    except Exception as e:
        print(f"Direct call failed (expected - may need context): {e}")

except ImportError as e:
    print(f"❌ Failed to import web_fetch: {e}")
    print("\nTrying to list all available tools in strands_tools...")

    import strands_tools
    available = dir(strands_tools)
    print(f"Available in strands_tools: {[x for x in available if not x.startswith('_')]}")

except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Done ===")
