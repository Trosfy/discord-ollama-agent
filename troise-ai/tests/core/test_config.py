"""Unit tests for Configuration management."""
import pytest

from app.core.config import SkillsConfig, ToolsConfig


# =============================================================================
# ToolsConfig Tests
# =============================================================================

def test_tools_config_defaults():
    """ToolsConfig has correct default values."""
    config = ToolsConfig()

    # ask_user not in universal_tools - agents add it explicitly if needed
    assert config.universal_tools == ["remember", "recall", "web_search", "web_fetch"]


def test_tools_config_from_dict():
    """ToolsConfig.from_dict parses YAML data correctly."""
    data = {
        "universal_tools": ["tool1", "tool2"],
    }

    config = ToolsConfig.from_dict(data)

    assert config.universal_tools == ["tool1", "tool2"]


def test_tools_config_from_dict_empty():
    """ToolsConfig.from_dict returns defaults for empty dict."""
    config = ToolsConfig.from_dict({})

    assert config.universal_tools == ["remember", "recall", "web_search", "web_fetch"]


def test_tools_config_from_dict_none():
    """ToolsConfig.from_dict returns defaults for None."""
    config = ToolsConfig.from_dict(None)

    assert config.universal_tools == ["remember", "recall", "web_search", "web_fetch"]


# =============================================================================
# SkillsConfig Tests
# =============================================================================

def test_skills_config_defaults():
    """SkillsConfig has correct default values."""
    config = SkillsConfig()

    assert config.max_skill_depth == 2


def test_skills_config_from_dict():
    """SkillsConfig.from_dict parses YAML data correctly."""
    data = {
        "max_skill_depth": 3,
    }

    config = SkillsConfig.from_dict(data)

    assert config.max_skill_depth == 3


def test_skills_config_from_dict_empty():
    """SkillsConfig.from_dict returns defaults for empty dict."""
    config = SkillsConfig.from_dict({})

    assert config.max_skill_depth == 2


def test_skills_config_from_dict_none():
    """SkillsConfig.from_dict returns defaults for None."""
    config = SkillsConfig.from_dict(None)

    assert config.max_skill_depth == 2
