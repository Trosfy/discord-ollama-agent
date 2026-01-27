"""Graph loader for YAML-based graph definitions.

Converts declarative YAML graph definitions into executable Graph objects.
This follows the Open/Closed Principle - new graphs are added via YAML,
not code changes.

Example YAML:
    name: code_graph
    domain: code
    entry_node: explorer

    nodes:
      explorer:
        agent: explorer
        prompt_variant: code
      coder:
        agent: agentic_code

    edges:
      explorer:
        - to: coder
      coder:
        - to: END
"""
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

import yaml

from app.core.graph import Graph
from app.core.interfaces.graph import Edge, GraphState
from app.core.graph_nodes import (
    AgentNode,
    CodeReviewerNode,
    TestGeneratorNode,
    FactCheckerNode,
    VaultConnectorNode,
    KnowledgeExplorerNode,
    SwarmNode,
    SwarmAgentConfig,
    QualitySwarmNode,
    ResearchSwarmNode,
)

if TYPE_CHECKING:
    from app.core.container import Container

logger = logging.getLogger(__name__)


# Mapping of agent names to specialized node classes
SPECIALIZED_NODES: Dict[str, type] = {
    "code_reviewer": CodeReviewerNode,
    "test_generator": TestGeneratorNode,
    "fact_checker": FactCheckerNode,
    "vault_connector": VaultConnectorNode,
}

# Mapping of swarm names to specialized swarm node classes (OCP extension point)
SPECIALIZED_SWARM_NODES: Dict[str, type] = {
    "quality_swarm": QualitySwarmNode,
    "research_swarm": ResearchSwarmNode,
}


class GraphLoader:
    """Loads Graph objects from YAML definitions.

    Handles:
    - Parsing YAML definitions
    - Resolving agent references from the DI container
    - Building node instances (regular or specialized)
    - Converting edge definitions with condition lookup

    Example:
        loader = GraphLoader(container, conditions)
        graph = loader.load(Path("definitions/code_graph.yaml"))
    """

    def __init__(
        self,
        container: "Container",
        conditions: Dict[str, Callable[[GraphState], bool]],
    ):
        """Initialize the graph loader.

        Args:
            container: DI container for resolving agents.
            conditions: Map of condition names to functions.
        """
        self._container = container
        self._conditions = conditions

    def load(self, yaml_path: Path) -> Graph:
        """Load a graph from a YAML file.

        Args:
            yaml_path: Path to the YAML definition file.

        Returns:
            Graph instance ready for execution.

        Raises:
            FileNotFoundError: If YAML file doesn't exist.
            ValueError: If definition is invalid.
            KeyError: If referenced agent or condition not found.
        """
        if not yaml_path.exists():
            raise FileNotFoundError(f"Graph definition not found: {yaml_path}")

        with open(yaml_path, "r") as f:
            definition = yaml.safe_load(f)

        return self._build_graph(definition, yaml_path)

    def _build_graph(self, definition: Dict[str, Any], source: Path) -> Graph:
        """Build a Graph object from parsed YAML definition.

        Args:
            definition: Parsed YAML dictionary.
            source: Source file path for error messages.

        Returns:
            Graph instance.
        """
        # Validate required fields
        required = ["name", "domain", "entry_node", "nodes", "edges"]
        for field in required:
            if field not in definition:
                raise ValueError(f"Missing required field '{field}' in {source}")

        # Build nodes
        nodes = self._build_nodes(definition["nodes"], definition.get("domain"))

        # Build edges
        edges = self._build_edges(definition["edges"])

        # Build complexity indicators if present
        complexity_indicators = definition.get("complexity_indicators", {})

        return Graph(
            name=definition["name"],
            domain=definition["domain"],
            nodes=nodes,
            edges=edges,
            entry_node=definition["entry_node"],
            simple_entry=definition.get("simple_entry"),
            max_loops=definition.get("max_loops", 3),
            description=definition.get("description", ""),
            complexity_indicators=complexity_indicators,
        )

    def _build_nodes(
        self,
        node_defs: Dict[str, Dict[str, Any]],
        default_domain: Optional[str] = None,
    ) -> Dict[str, AgentNode]:
        """Build node instances from definitions.

        Extended to support both agent nodes and swarm nodes (OCP).
        Dispatches based on the 'type' field in node definition.

        Args:
            node_defs: Node definitions from YAML.
            default_domain: Default domain for prompt variants.

        Returns:
            Dictionary of node name to node instance.
        """
        nodes = {}

        for node_name, node_def in node_defs.items():
            node_type = node_def.get("type", "agent")

            if node_type == "swarm":
                # Build swarm node (Phase 2: Strands Swarm Integration)
                node = self._build_swarm_node(node_name, node_def)
            else:
                # Build agent node (existing behavior)
                node = self._build_agent_node(node_name, node_def, default_domain)

            nodes[node_name] = node

        return nodes

    def _build_agent_node(
        self,
        node_name: str,
        node_def: Dict[str, Any],
        default_domain: Optional[str],
    ) -> AgentNode:
        """Build an AgentNode from YAML definition.

        Args:
            node_name: Unique node identifier.
            node_def: Node definition from YAML.
            default_domain: Default domain for prompt variants.

        Returns:
            AgentNode instance.
        """
        agent_name = node_def.get("agent", node_name)
        prompt_variant = node_def.get("prompt_variant", default_domain)
        state_key = node_def.get("state_key")
        tool_override = node_def.get("tools")  # Optional per-node tool list from YAML
        tool_limits = node_def.get("tool_limits")  # Optional tool call limits (e.g., {"web_fetch": 3})
        streaming = node_def.get("streaming", True)  # Whether node streams output (default: True)

        # Resolve agent from container
        agent = self._resolve_agent(agent_name)

        if agent is None:
            raise KeyError(f"Agent '{agent_name}' not found in container")

        # Use specialized node class if available
        node_class = SPECIALIZED_NODES.get(agent_name, AgentNode)

        # Special case: explorer with research variant uses KnowledgeExplorerNode
        if agent_name == "explorer" and prompt_variant == "research":
            node_class = KnowledgeExplorerNode

        node = node_class(
            agent=agent,
            prompt_variant=prompt_variant,
            state_key=state_key,
            tool_override=tool_override,
            tool_limits=tool_limits,
            streaming=streaming,
        )

        # Override name if different from agent name
        if node_name != agent_name:
            node.name = node_name

        # Log node configuration
        config_parts = [f"agent='{agent_name}'"]
        if tool_override:
            config_parts.append(f"tools={tool_override}")
        if tool_limits:
            config_parts.append(f"tool_limits={tool_limits}")
        if not streaming:
            config_parts.append("streaming=False")
        logger.debug(f"Built agent node '{node_name}' with {', '.join(config_parts)}")
        return node

    def _build_swarm_node(
        self,
        node_name: str,
        node_def: Dict[str, Any],
    ) -> SwarmNode:
        """Build a SwarmNode from YAML definition.

        Creates SwarmAgentConfig objects for deferred model creation.
        Models are created at execution time via VRAMOrchestrator for
        proper VRAM management.

        Args:
            node_name: Unique node identifier.
            node_def: Node definition from YAML with swarm configuration.

        Returns:
            SwarmNode instance with agent configs (no models yet).

        YAML Schema:
            <node_name>:
              type: swarm
              agents: [agent1, agent2, ...]  # Agent names from PluginRegistry
              entry_point: agent1            # Starting agent name
              max_handoffs: 10               # Optional, default 20
              max_iterations: 15             # Optional, default 20
        """
        from app.core.config import Config
        from app.core.registry import PluginRegistry

        config = self._container.resolve(Config)
        registry = self._container.resolve(PluginRegistry)

        # Resolve agents from plugin registry
        agent_names = node_def.get("agents", [])
        if not agent_names:
            raise ValueError(f"Swarm node '{node_name}' requires 'agents' list")

        # Build agent configs (models and prompts created at execution time)
        agent_configs = []
        for agent_name in agent_names:
            # Get our BaseAgent from registry to access its config
            base_agent = self._resolve_agent(agent_name)
            if base_agent is None:
                raise KeyError(f"Agent '{agent_name}' not found for swarm '{node_name}'")

            # Get agent plugin config to determine model_role
            agent_plugin = registry.get_agent(agent_name)
            agent_cfg = agent_plugin.get("config", {}) if agent_plugin else {}
            model_role = agent_cfg.get("model_role", "general")

            # Get model ID from profile based on role
            model_id = config.get_model_for_task(model_role)

            # Get agent's tool list from class attribute
            agent_tools = getattr(type(base_agent), "tools", [])

            # Create config (model AND prompt created at execution time)
            # NOTE: system_prompt is NOT stored here - it's composed at execution time
            # using PromptComposer to ensure template placeholders are filled
            agent_configs.append(SwarmAgentConfig(
                name=agent_name,
                model_id=model_id,
                model_role=model_role,
                temperature=agent_cfg.get("temperature", 0.7),
                max_tokens=agent_cfg.get("max_tokens", 4096),
                tools=agent_tools,
            ))

            logger.debug(
                f"Swarm '{node_name}': Agent '{agent_name}' config created "
                f"(model={model_id}, role={model_role}, tools={agent_tools})"
            )

        # Use specialized swarm node class if available (OCP)
        node_class = SPECIALIZED_SWARM_NODES.get(node_name, SwarmNode)

        entry_point_name = node_def.get("entry_point", agent_names[0])

        logger.debug(
            f"Built swarm node '{node_name}' with {len(agent_configs)} agent configs "
            f"(entry_point={entry_point_name})"
        )

        return node_class(
            agent_configs=agent_configs,
            entry_point_name=entry_point_name,
            name=node_name,
            max_handoffs=node_def.get("max_handoffs", 20),
            max_iterations=node_def.get("max_iterations", 20),
        )

    def _build_edges(
        self,
        edge_defs: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, List[Edge]]:
        """Build edge instances from definitions.

        Args:
            edge_defs: Edge definitions from YAML.

        Returns:
            Dictionary of source node name to list of Edge instances.
        """
        edges = {}

        for from_node, edge_list in edge_defs.items():
            edges[from_node] = []

            for edge_def in edge_list:
                to_node = edge_def["to"]
                condition_name = edge_def.get("condition")

                # Look up condition function if specified
                condition = None
                if condition_name:
                    if condition_name not in self._conditions:
                        raise KeyError(
                            f"Unknown condition '{condition_name}' in edge "
                            f"'{from_node}' -> '{to_node}'"
                        )
                    condition = self._conditions[condition_name]

                edge = Edge(to=to_node, condition=condition)
                edges[from_node].append(edge)

                logger.debug(
                    f"Built edge: {from_node} -> {to_node} "
                    f"(condition={condition_name or 'none'})"
                )

        return edges

    def _resolve_agent(self, agent_name: str) -> Optional[Any]:
        """Resolve an agent by name from the container.

        Tries multiple resolution strategies:
        1. Direct resolution from plugin registry
        2. Factory resolution from container

        Args:
            agent_name: Name of the agent to resolve.

        Returns:
            Agent instance or None if not found.
        """
        try:
            # Try to get from plugin registry first
            from app.core.registry import PluginRegistry

            registry = self._container.resolve(PluginRegistry)
            agent_plugin = registry.get_agent(agent_name)

            if agent_plugin:
                # Extract the class from the plugin dict
                agent_class = agent_plugin.get("class")
                if not agent_class:
                    logger.error(f"Agent plugin '{agent_name}' has no 'class' key")
                    return None
                # Instantiate the agent using container dependencies
                return self._instantiate_agent(agent_name, agent_class)

            logger.warning(f"Agent '{agent_name}' not found in plugin registry")
            return None

        except Exception as e:
            logger.error(f"Failed to resolve agent '{agent_name}': {e}")
            return None

    def _instantiate_agent(self, name: str, agent_class: type) -> Any:
        """Instantiate an agent with its dependencies.

        Args:
            name: Agent name for logging.
            agent_class: Agent class to instantiate.

        Returns:
            Instantiated agent.
        """
        from app.services.vram_orchestrator import VRAMOrchestrator
        from app.prompts import PromptComposer
        from app.core.tool_factory import ToolFactory

        try:
            # Resolve dependencies
            vram_orchestrator = self._container.resolve(VRAMOrchestrator)
            prompt_composer = self._container.resolve(PromptComposer)
            tool_factory = self._container.resolve(ToolFactory)

            # Get agent's tool list
            tools = getattr(agent_class, "tools", [])

            # Create tool instances (will be replaced with shared tools during graph execution)
            # For now, create empty list - tools are injected at execution time
            tool_instances = []

            # Instantiate agent
            agent = agent_class(
                vram_orchestrator=vram_orchestrator,
                tools=tool_instances,
                prompt_composer=prompt_composer,
            )

            logger.debug(f"Instantiated agent '{name}'")
            return agent

        except Exception as e:
            logger.error(f"Failed to instantiate agent '{name}': {e}")
            raise


def load_graph_from_yaml(
    yaml_path: Path,
    container: "Container",
    conditions: Dict[str, Callable[[GraphState], bool]],
) -> Graph:
    """Convenience function to load a single graph from YAML.

    Args:
        yaml_path: Path to YAML file.
        container: DI container.
        conditions: Condition function map.

    Returns:
        Graph instance.
    """
    loader = GraphLoader(container, conditions)
    return loader.load(yaml_path)
