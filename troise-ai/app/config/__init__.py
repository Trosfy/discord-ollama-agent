"""Configuration module for TROISE AI.

Provides YAML-based configuration loading for routes and other settings.
"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

# Default config directory (relative to this file)
CONFIG_DIR = Path(__file__).parent


def load_yaml_config(filename: str) -> Dict[str, Any]:
    """Load a YAML configuration file.

    Args:
        filename: Name of the YAML file (e.g., "routes.yaml").

    Returns:
        Parsed YAML as dictionary, or empty dict if file not found.
    """
    config_path = CONFIG_DIR / filename
    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}")
        return {}

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
            logger.debug(f"Loaded config from {filename}")
            return config or {}
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse {filename}: {e}")
        return {}


def load_routes_config() -> Dict[str, Any]:
    """Load routes configuration.

    Returns:
        Routes configuration dictionary.
    """
    return load_yaml_config("routes.yaml")


__all__ = [
    "load_yaml_config",
    "load_routes_config",
    "CONFIG_DIR",
]
