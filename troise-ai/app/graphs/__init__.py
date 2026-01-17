"""Graph definitions and loading for TROISE AI.

This module provides YAML-based graph discovery and registration,
following the Open/Closed Principle - add new graphs via YAML files,
no code changes required.

Usage:
    from app.graphs import load_graphs

    registry = GraphRegistry()
    load_graphs(registry, container)
"""
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .loader import GraphLoader
from .conditions import CONDITIONS

if TYPE_CHECKING:
    from app.core.graph import GraphRegistry
    from app.core.container import Container

logger = logging.getLogger(__name__)

# Directory containing YAML graph definitions
DEFINITIONS_DIR = Path(__file__).parent / "definitions"


def load_graphs(registry: "GraphRegistry", container: "Container") -> int:
    """Load all graph definitions from YAML files.

    Discovers all .yaml files in the definitions/ directory and loads
    them into the registry. This is the main entry point for graph
    initialization at application startup.

    Args:
        registry: GraphRegistry to populate.
        container: DI container for resolving agents.

    Returns:
        Number of graphs loaded.

    Example:
        container = create_container()
        registry = container.resolve(GraphRegistry)
        count = load_graphs(registry, container)
        logger.info(f"Loaded {count} graphs")
    """
    if not DEFINITIONS_DIR.exists():
        logger.warning(f"Graph definitions directory not found: {DEFINITIONS_DIR}")
        return 0

    loader = GraphLoader(container, CONDITIONS)
    loaded = 0

    for yaml_file in DEFINITIONS_DIR.glob("*.yaml"):
        try:
            graph = loader.load(yaml_file)
            registry.register(graph)
            loaded += 1
            logger.info(f"Loaded graph '{graph.name}' from {yaml_file.name}")
        except Exception as e:
            logger.error(f"Failed to load graph from {yaml_file}: {e}")

    return loaded


def get_definitions_dir() -> Path:
    """Get the path to graph definitions directory.

    Returns:
        Path to definitions/ directory.
    """
    return DEFINITIONS_DIR


__all__ = [
    "load_graphs",
    "get_definitions_dir",
    "GraphLoader",
    "CONDITIONS",
]
