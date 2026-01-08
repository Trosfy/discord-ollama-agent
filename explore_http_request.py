"""Explore strands_tools.http_request module."""

import inspect

print("=== Exploring strands_tools.http_request module ===\n")

try:
    import strands_tools.http_request as http_request_module

    print("✅ Successfully imported http_request module\n")

    # List all exported members
    members = [x for x in dir(http_request_module) if not x.startswith('_')]
    print(f"Exported members: {members}\n")

    # Inspect each callable member
    for name in members:
        obj = getattr(http_request_module, name)
        if callable(obj):
            print(f"=== {name} ===")
            print(f"Type: {type(obj)}")

            try:
                sig = inspect.signature(obj)
                print(f"Signature: {sig}")
            except:
                print("No signature available")

            doc = inspect.getdoc(obj)
            if doc:
                print(f"Doc: {doc[:200]}...")

            # Check if it's a Strands tool
            if hasattr(obj, '__strands_tool__'):
                print("✅ This is a Strands tool")

            print()

except ImportError as e:
    print(f"❌ Failed to import: {e}")

print("\n=== Current Implementation ===\n")

# Check current web tools
try:
    from app.tools.web_tools import fetch_webpage

    print("Current fetch_webpage:")
    sig = inspect.signature(fetch_webpage)
    print(f"Signature: {sig}")

    doc = inspect.getdoc(fetch_webpage)
    if doc:
        print(f"Doc: {doc[:300]}...")

    # Show first part of source
    try:
        import app.tools.web_tools
        source = inspect.getsource(app.tools.web_tools)
        lines = source.split('\n')
        # Find fetch_webpage function
        for i, line in enumerate(lines):
            if 'def fetch_webpage' in line or '@tool' in line and i < len(lines) - 1 and 'fetch_webpage' in lines[i+1]:
                # Print ~30 lines starting from here
                print(f"\nSource (lines {i}-{min(i+30, len(lines))}):")
                print('\n'.join(lines[i:min(i+30, len(lines))]))
                break
    except Exception as e:
        print(f"Could not get source: {e}")

except Exception as e:
    print(f"⚠️ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Done ===")
