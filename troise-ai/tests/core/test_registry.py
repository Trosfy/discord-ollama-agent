"""Unit tests for Plugin Registry."""
import pytest
from pathlib import Path
import tempfile
import os

from app.core.registry import PluginRegistry


# =============================================================================
# Test Plugin Declarations
# =============================================================================

MOCK_SKILL = {
    "type": "skill",
    "name": "test_skill",
    "category": "test",
    "class": object,  # Placeholder
    "description": "A test skill for unit tests",
    "use_when": "Testing purposes",
}

MOCK_AGENT = {
    "type": "agent",
    "name": "test_agent",
    "category": "test",
    "class": object,  # Placeholder
    "description": "A test agent for unit tests",
    "use_when": "Testing agent functionality",
    "config": {
        "tools": ["test_tool", "another_tool"],
        "model": "test:7b",
    },
}

MOCK_TOOL = {
    "type": "tool",
    "name": "test_tool",
    "factory": lambda ctx, container: object(),
    "description": "A test tool for unit tests",
}

ANOTHER_TOOL = {
    "type": "tool",
    "name": "another_tool",
    "factory": lambda ctx, container: object(),
    "description": "Another test tool",
}


# =============================================================================
# Manual Registration Tests (Using internal dicts directly)
# =============================================================================

def test_register_skill_manually():
    """Manually registered skill is retrievable."""
    registry = PluginRegistry()
    registry._skills["test_skill"] = MOCK_SKILL

    skill = registry.get_skill("test_skill")

    assert skill is not None
    assert skill["name"] == "test_skill"
    assert skill["description"] == "A test skill for unit tests"
    assert registry.skill_count == 1


def test_register_agent_manually():
    """Manually registered agent is retrievable."""
    registry = PluginRegistry()
    registry._agents["test_agent"] = MOCK_AGENT

    agent = registry.get_agent("test_agent")

    assert agent is not None
    assert agent["name"] == "test_agent"
    assert agent["config"]["tools"] == ["test_tool", "another_tool"]
    assert registry.agent_count == 1


def test_register_tool_manually():
    """Manually registered tool is retrievable."""
    registry = PluginRegistry()
    registry._tools["test_tool"] = MOCK_TOOL

    tool = registry.get_tool("test_tool")

    assert tool is not None
    assert tool["name"] == "test_tool"
    assert callable(tool["factory"])
    assert registry.tool_count == 1


# =============================================================================
# Get Plugin Tests
# =============================================================================

def test_get_skill_not_found():
    """get_skill returns None for unknown skill."""
    registry = PluginRegistry()

    result = registry.get_skill("nonexistent")

    assert result is None


def test_get_agent_not_found():
    """get_agent returns None for unknown agent."""
    registry = PluginRegistry()

    result = registry.get_agent("nonexistent")

    assert result is None


def test_get_tool_not_found():
    """get_tool returns None for unknown tool."""
    registry = PluginRegistry()

    result = registry.get_tool("nonexistent")

    assert result is None


# =============================================================================
# Routing Table Tests
# =============================================================================

def test_get_compact_routing_table_skills_only():
    """Routing table includes skills with descriptions."""
    registry = PluginRegistry()
    registry._skills["summarize"] = {
        "type": "skill",
        "name": "summarize",
        "description": "Summarize text",
        "use_when": "User wants a summary",
    }

    routing_table = registry.get_compact_routing_table()

    assert "SKILL: summarize - Summarize text (use when: User wants a summary)" in routing_table


def test_get_compact_routing_table_agents():
    """Routing table includes agents."""
    registry = PluginRegistry()
    registry._agents["braindump"] = {
        "type": "agent",
        "name": "braindump",
        "description": "Dump thoughts into notes",
        "use_when": "User wants to capture ideas",
    }

    routing_table = registry.get_compact_routing_table()

    assert "AGENT: braindump" in routing_table
    assert "Dump thoughts into notes" in routing_table


def test_get_compact_routing_table_excludes_tools():
    """Routing table does NOT include tools (they're used by agents)."""
    registry = PluginRegistry()
    registry._tools["brain_search"] = {
        "type": "tool",
        "name": "brain_search",
        "description": "Search knowledge base",
    }

    routing_table = registry.get_compact_routing_table()

    # Tools should not be in routing table
    assert "brain_search" not in routing_table


def test_get_compact_routing_table_sorted():
    """Routing table is sorted alphabetically."""
    registry = PluginRegistry()
    registry._skills["zebra"] = {"type": "skill", "name": "zebra", "description": "Z skill"}
    registry._skills["alpha"] = {"type": "skill", "name": "alpha", "description": "A skill"}
    registry._skills["middle"] = {"type": "skill", "name": "middle", "description": "M skill"}

    routing_table = registry.get_compact_routing_table()

    # Check order: alpha, middle, zebra
    assert routing_table.index("alpha") < routing_table.index("middle")
    assert routing_table.index("middle") < routing_table.index("zebra")


# =============================================================================
# Get Tools for Agent Tests
# =============================================================================

def test_get_tools_for_agent():
    """Resolves agent's configured tools."""
    registry = PluginRegistry()
    registry._agents["test_agent"] = MOCK_AGENT
    registry._tools["test_tool"] = MOCK_TOOL
    registry._tools["another_tool"] = ANOTHER_TOOL

    tools = registry.get_tools_for_agent("test_agent")

    assert len(tools) == 2
    tool_names = [t["name"] for t in tools]
    assert "test_tool" in tool_names
    assert "another_tool" in tool_names


def test_get_tools_for_agent_partial_match():
    """Returns only tools that are registered."""
    registry = PluginRegistry()
    registry._agents["test_agent"] = MOCK_AGENT
    registry._tools["test_tool"] = MOCK_TOOL
    # another_tool is NOT registered

    tools = registry.get_tools_for_agent("test_agent")

    # Only test_tool should be returned
    assert len(tools) == 1
    assert tools[0]["name"] == "test_tool"


def test_get_tools_for_agent_not_found():
    """Returns empty list for unknown agent."""
    registry = PluginRegistry()

    tools = registry.get_tools_for_agent("nonexistent")

    assert tools == []


def test_get_tools_for_agent_no_tools_configured():
    """Returns universal tools when agent has no specific tools."""
    from unittest.mock import MagicMock

    # Create mock config with universal tools
    mock_config = MagicMock()
    mock_config.tools.universal_tools = ["universal1", "universal2"]

    registry = PluginRegistry(config=mock_config)
    registry._agents["no_tools_agent"] = {
        "type": "agent",
        "name": "no_tools_agent",
        "config": {},  # No agent-specific tools
    }
    # Register universal tools
    registry._tools["universal1"] = {"type": "tool", "name": "universal1"}
    registry._tools["universal2"] = {"type": "tool", "name": "universal2"}

    tools = registry.get_tools_for_agent("no_tools_agent")

    # Should get universal tools
    assert len(tools) == 2
    tool_names = [t["name"] for t in tools]
    assert "universal1" in tool_names
    assert "universal2" in tool_names


def test_get_tools_for_agent_merges_universal():
    """Universal tools are merged with agent-specific tools."""
    from unittest.mock import MagicMock

    # Create mock config with universal tools
    mock_config = MagicMock()
    mock_config.tools.universal_tools = ["universal1"]

    registry = PluginRegistry(config=mock_config)
    registry._agents["test_agent"] = {
        "type": "agent",
        "name": "test_agent",
        "config": {"tools": ["specific1", "specific2"]},
    }
    # Register all tools
    registry._tools["universal1"] = {"type": "tool", "name": "universal1"}
    registry._tools["specific1"] = {"type": "tool", "name": "specific1"}
    registry._tools["specific2"] = {"type": "tool", "name": "specific2"}

    tools = registry.get_tools_for_agent("test_agent")

    # Should get universal + agent-specific (3 total)
    assert len(tools) == 3
    tool_names = [t["name"] for t in tools]
    assert "universal1" in tool_names
    assert "specific1" in tool_names
    assert "specific2" in tool_names

    # Universal tools should come first
    assert tool_names[0] == "universal1"


# =============================================================================
# List Methods Tests
# =============================================================================

def test_list_skills():
    """list_skills returns all skill names."""
    registry = PluginRegistry()
    registry._skills["skill1"] = {"type": "skill", "name": "skill1"}
    registry._skills["skill2"] = {"type": "skill", "name": "skill2"}

    names = registry.list_skills()

    assert set(names) == {"skill1", "skill2"}


def test_list_agents():
    """list_agents returns all agent names."""
    registry = PluginRegistry()
    registry._agents["agent1"] = {"type": "agent", "name": "agent1"}
    registry._agents["agent2"] = {"type": "agent", "name": "agent2"}

    names = registry.list_agents()

    assert set(names) == {"agent1", "agent2"}


def test_list_tools():
    """list_tools returns all tool names."""
    registry = PluginRegistry()
    registry._tools["tool1"] = {"type": "tool", "name": "tool1"}
    registry._tools["tool2"] = {"type": "tool", "name": "tool2"}

    names = registry.list_tools()

    assert set(names) == {"tool1", "tool2"}


# =============================================================================
# Get All Plugins Test
# =============================================================================

def test_get_all_plugins():
    """get_all_plugins returns copy of all registrations."""
    registry = PluginRegistry()
    registry._skills["skill1"] = MOCK_SKILL
    registry._agents["agent1"] = MOCK_AGENT
    registry._tools["tool1"] = MOCK_TOOL

    all_plugins = registry.get_all_plugins()

    assert "skills" in all_plugins
    assert "agents" in all_plugins
    assert "tools" in all_plugins
    assert "skill1" in all_plugins["skills"]
    assert "agent1" in all_plugins["agents"]
    assert "tool1" in all_plugins["tools"]


# =============================================================================
# Reload Tests
# =============================================================================

async def test_reload_clears_registrations():
    """Reload clears all registrations before re-discovering."""
    registry = PluginRegistry()
    registry._skills["old_skill"] = MOCK_SKILL
    registry._agents["old_agent"] = MOCK_AGENT
    registry._tools["old_tool"] = MOCK_TOOL

    # Set empty plugin dirs so discover doesn't find anything
    registry._plugin_dirs = []

    await registry.reload()

    # All cleared, nothing re-discovered
    assert registry.skill_count == 0
    assert registry.agent_count == 0
    assert registry.tool_count == 0


# =============================================================================
# Discovery Tests (Integration - creates temp directory)
# =============================================================================

async def test_discover_skill_from_filesystem():
    """Discovers skill plugin from filesystem."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create plugin structure: plugins/skills/test_skill/__init__.py
        plugins_dir = Path(tmpdir) / "plugins"
        skill_dir = plugins_dir / "skills" / "test_skill"
        skill_dir.mkdir(parents=True)

        # Write __init__.py with PLUGIN declaration
        init_file = skill_dir / "__init__.py"
        init_file.write_text('''
PLUGIN = {
    "type": "skill",
    "name": "discovered_skill",
    "category": "test",
    "description": "A discovered skill",
    "use_when": "Testing discovery",
}
''')

        registry = PluginRegistry()
        await registry.discover([plugins_dir])

        assert registry.skill_count == 1
        skill = registry.get_skill("discovered_skill")
        assert skill is not None
        assert skill["description"] == "A discovered skill"


async def test_discover_agent_from_filesystem():
    """Discovers agent plugin from filesystem."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir) / "plugins"
        agent_dir = plugins_dir / "agents" / "test_agent"
        agent_dir.mkdir(parents=True)

        init_file = agent_dir / "__init__.py"
        init_file.write_text('''
PLUGIN = {
    "type": "agent",
    "name": "discovered_agent",
    "category": "test",
    "description": "A discovered agent",
    "config": {"tools": []},
}
''')

        registry = PluginRegistry()
        await registry.discover([plugins_dir])

        assert registry.agent_count == 1
        agent = registry.get_agent("discovered_agent")
        assert agent is not None


async def test_discover_tool_from_filesystem():
    """Discovers tool plugin from filesystem."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir) / "plugins"
        tool_dir = plugins_dir / "tools" / "test_tool"
        tool_dir.mkdir(parents=True)

        init_file = tool_dir / "__init__.py"
        init_file.write_text('''
def dummy_factory(ctx, container):
    return None

PLUGIN = {
    "type": "tool",
    "name": "discovered_tool",
    "factory": dummy_factory,
    "description": "A discovered tool",
}
''')

        registry = PluginRegistry()
        await registry.discover([plugins_dir])

        assert registry.tool_count == 1
        tool = registry.get_tool("discovered_tool")
        assert tool is not None


async def test_discover_skips_nonexistent_dir():
    """Discovery handles missing directories gracefully."""
    registry = PluginRegistry()

    # Should not raise
    await registry.discover([Path("/nonexistent/path")])

    assert registry.skill_count == 0


async def test_discover_skips_modules_without_plugin():
    """Discovery skips modules that don't have PLUGIN."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir) / "plugins"
        skill_dir = plugins_dir / "skills" / "no_plugin"
        skill_dir.mkdir(parents=True)

        # Write __init__.py WITHOUT PLUGIN declaration
        init_file = skill_dir / "__init__.py"
        init_file.write_text("# No PLUGIN here\nx = 1")

        registry = PluginRegistry()
        await registry.discover([plugins_dir])

        # Nothing discovered
        assert registry.skill_count == 0
