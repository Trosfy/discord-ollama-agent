"""Plugin Registry for TROISE AI.

Provides auto-discovery and registration of plugins (skills, agents, tools).
Plugins declare themselves via a PLUGIN dict in their __init__.py.

Example plugin declaration:

    # plugins/skills/summarize/__init__.py
    from .skill import SummarizeSkill

    PLUGIN = {
        "type": "skill",
        "name": "summarize",
        "category": "think",
        "class": SummarizeSkill,
        "description": "Condense long text into a brief summary",
        "use_when": "User wants to shorten, summarize, or get the gist of text"
    }
"""
import importlib
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

from .skill_loader import SkillLoader

logger = logging.getLogger(__name__)


# Default skills that any agent can call via use_skill tool
class SkillPlugin(TypedDict, total=False):
    """Type definition for skill plugin declaration."""
    type: str  # "skill"
    name: str
    category: str
    class_: type  # The skill class
    description: str
    use_when: str


class AgentPlugin(TypedDict, total=False):
    """Type definition for agent plugin declaration."""
    type: str  # "agent"
    name: str
    category: str
    class_: type  # The agent class
    description: str
    use_when: str
    config: Dict[str, Any]  # model, tools, max_tool_calls, timeout_seconds


class ToolPlugin(TypedDict, total=False):
    """Type definition for tool plugin declaration."""
    type: str  # "tool"
    name: str
    factory: Callable  # Factory function that creates tool with context
    description: str


class PluginRegistry:
    """
    Scans plugin directories and auto-registers all plugins.

    Features:
    - Auto-discovery: No manual registration needed
    - Plugin types: skills, agents, tools
    - Routing table: Generates compact routing table for LLM classifier
    - Hot reload: Reload all plugins without restart

    Example:
        registry = PluginRegistry()
        await registry.discover([Path("app/plugins")])

        # Get routing table for LLM
        routing_table = registry.get_compact_routing_table()

        # Get specific plugin
        skill = registry.get_skill("summarize")
        agent = registry.get_agent("braindump")
        tool = registry.get_tool("brain_search")
    """

    def __init__(self, config: "Config" = None):
        """
        Initialize an empty registry.

        Args:
            config: Optional Config instance for skill settings.
                    If not provided, uses DEFAULT_UNIVERSAL_SKILLS.
        """
        self._skills: Dict[str, Dict[str, Any]] = {}
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._plugin_dirs: List[Path] = []
        self._skill_loader = SkillLoader()
        self._config = config

    @property
    def skill_count(self) -> int:
        """Get number of registered skills."""
        return len(self._skills)

    @property
    def agent_count(self) -> int:
        """Get number of registered agents."""
        return len(self._agents)

    @property
    def tool_count(self) -> int:
        """Get number of registered tools."""
        return len(self._tools)

    async def discover(self, plugin_dirs: List[Path]) -> None:
        """
        Scan directories for PLUGIN dicts and register.

        Directory structure expected:
            plugins/
                skills/
                    general/              # skill category
                        chat/
                            SKILL.md      # Claude format (preferred)
                        explain/
                            skill.md      # Legacy format (supported)
                    think/                # skill category
                        summarize/
                            SKILL.md
                        analyze/
                            SKILL.md
                agents/
                    braindump/
                        __init__.py
                        agent.py
                tools/
                    brain_search/
                        __init__.py
                        tool.py

        Skills support:
        - Nested category directories (general/, think/, etc.)
        - SKILL.md (Claude format) - checked first
        - skill.md (legacy format) - fallback

        Args:
            plugin_dirs: List of plugin directories to scan.
        """
        self._plugin_dirs = plugin_dirs

        for plugin_dir in plugin_dirs:
            if not plugin_dir.exists():
                logger.warning(f"Plugin directory not found: {plugin_dir}")
                continue

            # Scan each type (skills, agents, tools)
            for type_dir in plugin_dir.iterdir():
                if not type_dir.is_dir():
                    continue

                if type_dir.name.startswith('_'):
                    continue  # Skip __pycache__, etc.

                if type_dir.name == "skills":
                    # Skills support nested category directories
                    await self._discover_skills(type_dir, plugin_dir)
                else:
                    # Agents and tools are flat
                    await self._discover_flat(type_dir, plugin_dir)

        logger.info(
            f"Discovered {self.skill_count} skills, "
            f"{self.agent_count} agents, {self.tool_count} tools"
        )

    async def _load_plugin(self, plugin_path: Path, base_dir: Path) -> None:
        """
        Import module, extract PLUGIN dict, and register.

        Args:
            plugin_path: Path to the plugin directory.
            base_dir: Base plugins directory for module name calculation.
        """
        try:
            # Calculate module name relative to base directory
            rel_path = plugin_path.relative_to(base_dir.parent)
            module_name = str(rel_path).replace("/", ".").replace("\\", ".")

            # Ensure parent directory is in sys.path
            parent_dir = str(base_dir.parent)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)

            # Import the module
            if module_name in sys.modules:
                # Reload for hot-reload support
                module = importlib.reload(sys.modules[module_name])
            else:
                module = importlib.import_module(module_name)

            # Check for PLUGIN declaration
            if not hasattr(module, 'PLUGIN'):
                logger.debug(f"No PLUGIN in {module_name}, skipping")
                return

            plugin = module.PLUGIN
            plugin_type = plugin.get('type')
            plugin_name = plugin.get('name')

            if not plugin_type or not plugin_name:
                logger.warning(f"Invalid PLUGIN in {module_name}: missing type or name")
                return

            # Register based on type
            if plugin_type == 'skill':
                self._skills[plugin_name] = plugin
                logger.debug(f"Registered skill: {plugin_name}")

            elif plugin_type == 'agent':
                self._agents[plugin_name] = plugin
                logger.debug(f"Registered agent: {plugin_name}")

            elif plugin_type == 'tool':
                self._tools[plugin_name] = plugin
                logger.info(f"Registered tool: {plugin_name}")

            else:
                logger.warning(f"Unknown plugin type '{plugin_type}' in {module_name}")

        except Exception as e:
            logger.error(f"Failed to load plugin from {plugin_path}: {e}")

    async def _discover_skills(self, skills_dir: Path, plugin_dir: Path) -> None:
        """
        Discover skills with category subdirectory support.

        Supports both flat structure (skills/summarize/) and nested
        category structure (skills/general/summarize/).

        Supports two declarative formats (checked in this order):
        - SKILL.md (Claude format): Minimal frontmatter, config in body
        - skill.md (legacy format): Full config in frontmatter

        Args:
            skills_dir: Path to the skills directory.
            plugin_dir: Base plugins directory for module name calculation.
        """
        for item in skills_dir.iterdir():
            if not item.is_dir() or item.name.startswith('_'):
                continue

            # Check if this is a skill directory
            # Priority: SKILL.md > skill.md > __init__.py
            skill_file = self._find_skill_file(item)
            if skill_file:
                self._load_declarative_skill(skill_file)
            elif (item / "__init__.py").exists():
                await self._load_plugin(item, plugin_dir)
            else:
                # This is a category directory, scan one level deeper
                for skill_path in item.iterdir():
                    if not skill_path.is_dir() or skill_path.name.startswith('_'):
                        continue
                    skill_file = self._find_skill_file(skill_path)
                    if skill_file:
                        self._load_declarative_skill(skill_file)
                    elif (skill_path / "__init__.py").exists():
                        await self._load_plugin(skill_path, plugin_dir)

    def _find_skill_file(self, skill_dir: Path) -> Optional[Path]:
        """
        Find the skill file in a directory.

        Checks for SKILL.md (Claude format) first, then skill.md (legacy).

        Args:
            skill_dir: Path to the skill directory.

        Returns:
            Path to the skill file, or None if not found.
        """
        # Check SKILL.md first (Claude format)
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            return skill_file

        # Fall back to skill.md (legacy format)
        skill_file = skill_dir / "skill.md"
        if skill_file.exists():
            return skill_file

        return None

    async def _discover_flat(self, type_dir: Path, plugin_dir: Path) -> None:
        """
        Discover plugins in flat directory structure (agents, tools).

        Args:
            type_dir: Path to the type directory (e.g., agents/, tools/).
            plugin_dir: Base plugins directory for module name calculation.
        """
        for plugin_path in type_dir.iterdir():
            if not plugin_path.is_dir() or plugin_path.name.startswith('_'):
                continue
            if (plugin_path / "__init__.py").exists():
                await self._load_plugin(plugin_path, plugin_dir)

    def _load_declarative_skill(self, skill_path: Path) -> None:
        """
        Load a declarative skill from a SKILL.md or skill.md file.

        Supports:
        - SKILL.md (Claude format): Minimal frontmatter, config in body
        - skill.md (legacy format): Full config in frontmatter

        Args:
            skill_path: Path to the skill file (SKILL.md or skill.md).
        """
        skill_def = self._skill_loader.load_skill(skill_path)
        if skill_def:
            self._skills[skill_def.name] = {
                "type": "skill",
                "name": skill_def.name,
                "category": skill_def.category,
                "description": skill_def.description,
                "use_when": skill_def.use_when,
                "declarative": True,
                "skill_def": skill_def,
            }
            logger.debug(f"Registered declarative skill: {skill_def.name}")

    def get_compact_routing_table(self) -> str:
        """
        Generate compact routing table for LLM classifier.

        Returns a string with one line per routable plugin (skills and agents).
        Tools are not included as they're used by agents, not routed to directly.
        Skills with routable=False are excluded (e.g., internal-only skills).

        Returns:
            Multiline string with plugin descriptions for LLM routing.
        """
        lines = []

        for name, plugin in sorted(self._skills.items()):
            # Check routable flag for declarative skills
            skill_def = plugin.get('skill_def')
            if skill_def and not getattr(skill_def, 'routable', True):
                continue  # Skip non-routable skills

            desc = plugin.get('description', 'No description')
            use_when = plugin.get('use_when', '')
            if use_when:
                lines.append(f"SKILL: {name} - {desc} (use when: {use_when})")
            else:
                lines.append(f"SKILL: {name} - {desc}")

        for name, plugin in sorted(self._agents.items()):
            desc = plugin.get('description', 'No description')
            use_when = plugin.get('use_when', '')
            if use_when:
                lines.append(f"AGENT: {name} - {desc} (use when: {use_when})")
            else:
                lines.append(f"AGENT: {name} - {desc}")

        return "\n".join(lines)

    async def reload(self) -> None:
        """
        Hot reload all plugins without restart.

        Clears all registrations and re-discovers from saved directories.
        """
        logger.info("Reloading plugins...")
        self._skills.clear()
        self._agents.clear()
        self._tools.clear()
        await self.discover(self._plugin_dirs)

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a skill plugin by name.

        Args:
            name: The skill name.

        Returns:
            The skill plugin dict, or None if not found.
        """
        return self._skills.get(name)

    def get_agent(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get an agent plugin by name.

        Args:
            name: The agent name.

        Returns:
            The agent plugin dict, or None if not found.
        """
        return self._agents.get(name)

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a tool plugin by name.

        Args:
            name: The tool name.

        Returns:
            The tool plugin dict, or None if not found.
        """
        return self._tools.get(name)

    def get_tools_for_agent(self, agent_name: str) -> List[Dict[str, Any]]:
        """
        Get all tools configured for an agent.

        Combines universal tools (from config) with agent-specific tools.
        Universal tools are added first, then agent-specific tools.

        Args:
            agent_name: The agent name.

        Returns:
            List of tool plugin dicts for the agent's configured tools.
        """
        agent = self._agents.get(agent_name)
        if not agent:
            return []

        # Get agent-specific tools (check root level first, then config)
        agent_tool_names = agent.get('tools', [])
        if not agent_tool_names:
            config = agent.get('config', {})
            agent_tool_names = config.get('tools', [])

        # Get universal tools from config
        universal_tool_names = self._get_universal_tools()

        # Combine: universal first, then agent-specific (avoid duplicates)
        all_tool_names = list(universal_tool_names)
        for name in agent_tool_names:
            if name not in all_tool_names:
                all_tool_names.append(name)

        # Log for debugging tool resolution
        available_tool_names = list(self._tools.keys())
        missing_tools = [n for n in all_tool_names if n not in self._tools]
        if missing_tools:
            logger.warning(
                f"Agent '{agent_name}' requested tools not in registry: {missing_tools}. "
                f"Available tools: {available_tool_names}"
            )

        return [
            self._tools[name]
            for name in all_tool_names
            if name in self._tools
        ]

    def _get_universal_tools(self) -> List[str]:
        """Get universal tools from config or defaults."""
        if self._config and hasattr(self._config, 'tools'):
            return self._config.tools.universal_tools
        # Fallback - ask_user removed, agents that need it add explicitly
        return ["skill_gateway", "remember", "recall"]

    def list_skills(self) -> List[str]:
        """Get list of all registered skill names."""
        return list(self._skills.keys())

    def list_agents(self) -> List[str]:
        """Get list of all registered agent names."""
        return list(self._agents.keys())

    def list_tools(self) -> List[str]:
        """Get list of all registered tool names."""
        return list(self._tools.keys())

    def get_all_plugins(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Get all registered plugins.

        Returns:
            Dictionary with keys 'skills', 'agents', 'tools'.
        """
        return {
            "skills": dict(self._skills),
            "agents": dict(self._agents),
            "tools": dict(self._tools),
        }
