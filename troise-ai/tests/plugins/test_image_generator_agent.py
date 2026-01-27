"""Unit tests for Image Generator Agent.

Tests cover:
- Agent class attributes (name, category, tools)
- Initialization with default and custom config
- Model role resolution (image_handler)
- Factory function creation
- Plugin definition validation
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.plugins.agents.image_generator import (
    ImageGeneratorAgent,
    create_image_generator_agent,
    PLUGIN,
)
from app.core.context import ExecutionContext, UserProfile


# =============================================================================
# Mock Classes
# =============================================================================

class MockPromptComposer:
    """Mock PromptComposer for testing."""

    def compose_agent_prompt(
        self,
        agent_name: str,
        interface: str,
        profile: str = None,
        user_profile=None,
        **format_vars,
    ) -> str:
        """Compose agent prompt with interface and personalization layers."""
        interface_context = f"## {interface.title()} Interface\nFormatted for {interface}."
        personalization_context = ""
        if user_profile:
            personalization_context = user_profile.get_personalization_context()

        return f"""You are the {agent_name} agent.

{interface_context}

{personalization_context or "No specific preferences."}"""


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_context():
    """Create mock execution context."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
        user_profile=UserProfile(user_id="test-user"),
        agent_name="image_generator",
    )
    return context


@pytest.fixture
def mock_vram_orchestrator():
    """Create mock VRAM orchestrator."""
    orchestrator = MagicMock()
    mock_model = MagicMock()
    mock_model.close = AsyncMock()  # Make close awaitable
    orchestrator.get_model = AsyncMock(return_value=mock_model)
    # Mock get_profile_model (sync method) to return model for image_handler role
    orchestrator.get_profile_model.return_value = "gpt-oss:20b"
    return orchestrator


@pytest.fixture
def mock_tools():
    """Create mock tool list."""
    return [MagicMock(name="generate_image")]


@pytest.fixture
def mock_prompt_composer():
    """Create mock prompt composer."""
    return MockPromptComposer()


@pytest.fixture
def image_generator_agent(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """Create ImageGeneratorAgent with mocks."""
    return ImageGeneratorAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
    )


# =============================================================================
# Agent Attributes Tests
# =============================================================================

def test_agent_name():
    """Agent has correct name attribute."""
    assert ImageGeneratorAgent.name == "image_generator"


def test_agent_category():
    """Agent has correct category attribute."""
    assert ImageGeneratorAgent.category == "image"


def test_agent_tools():
    """Agent declares required tools."""
    assert "generate_image" in ImageGeneratorAgent.tools


# =============================================================================
# Initialization Tests
# =============================================================================

def test_init_stores_orchestrator(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() stores VRAM orchestrator."""
    agent = ImageGeneratorAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
    )

    assert agent._vram_orchestrator == mock_vram_orchestrator


def test_init_stores_tools(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() stores provided tools."""
    agent = ImageGeneratorAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
    )

    assert agent._tools == mock_tools


def test_init_stores_prompt_composer(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() stores prompt composer."""
    agent = ImageGeneratorAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
    )

    assert agent._prompt_composer == mock_prompt_composer


def test_init_default_config(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() uses creative temperature by default."""
    agent = ImageGeneratorAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
    )

    assert agent._temperature == 0.7
    assert agent._max_tokens == 2048


def test_init_uses_image_handler_model(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() uses image_handler model role."""
    agent = ImageGeneratorAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
    )

    assert agent._model_id == "gpt-oss:20b"
    mock_vram_orchestrator.get_profile_model.assert_called_with("image_handler")


def test_init_custom_config(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() accepts custom configuration."""
    custom_config = {
        "temperature": 0.9,
        "max_tokens": 4096,
    }
    agent = ImageGeneratorAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
        config=custom_config,
    )

    # Custom config should override defaults
    assert agent._temperature == 0.9
    assert agent._max_tokens == 4096


def test_init_model_override(mock_vram_orchestrator, mock_tools, mock_prompt_composer):
    """__init__() uses explicit model if provided in config."""
    custom_config = {
        "model": "custom-model:70b",
    }
    agent = ImageGeneratorAgent(
        vram_orchestrator=mock_vram_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_prompt_composer,
        config=custom_config,
    )

    assert agent._model_id == "custom-model:70b"


# =============================================================================
# Plugin Definition Tests
# =============================================================================

def test_plugin_type():
    """PLUGIN has correct type."""
    assert PLUGIN["type"] == "agent"


def test_plugin_name():
    """PLUGIN has correct name."""
    assert PLUGIN["name"] == "image_generator"


def test_plugin_class():
    """PLUGIN references correct class."""
    assert PLUGIN["class"] == ImageGeneratorAgent


def test_plugin_factory():
    """PLUGIN has factory function."""
    assert PLUGIN["factory"] == create_image_generator_agent


def test_plugin_description():
    """PLUGIN has meaningful description."""
    assert "FLUX" in PLUGIN["description"]
    assert "image" in PLUGIN["description"].lower()


def test_plugin_category():
    """PLUGIN has correct category."""
    assert PLUGIN["category"] == "image"


def test_plugin_tools():
    """PLUGIN lists required tools."""
    assert "generate_image" in PLUGIN["tools"]


def test_plugin_config_model_role():
    """PLUGIN config uses image_handler model role."""
    assert PLUGIN["config"]["model_role"] == "image_handler"


def test_plugin_config_temperature():
    """PLUGIN config has creative temperature."""
    assert PLUGIN["config"]["temperature"] == 0.7


def test_plugin_config_skip_universal_tools():
    """PLUGIN config skips universal tools."""
    assert PLUGIN["config"]["skip_universal_tools"] is True


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_image_generator_agent_factory():
    """create_image_generator_agent() creates agent instance."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.get_profile_model.return_value = "gpt-oss:20b"
    mock_tools = [MagicMock()]
    mock_composer = MockPromptComposer()

    agent = create_image_generator_agent(
        vram_orchestrator=mock_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_composer,
    )

    assert isinstance(agent, ImageGeneratorAgent)
    assert agent._vram_orchestrator == mock_orchestrator


def test_create_image_generator_agent_with_config():
    """create_image_generator_agent() accepts custom config."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.get_profile_model.return_value = "gpt-oss:20b"
    mock_tools = [MagicMock()]
    mock_composer = MockPromptComposer()
    custom_config = {"temperature": 0.5}

    agent = create_image_generator_agent(
        vram_orchestrator=mock_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_composer,
        config=custom_config,
    )

    assert agent._temperature == 0.5


def test_create_image_generator_agent_none_config():
    """create_image_generator_agent() handles None config."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.get_profile_model.return_value = "gpt-oss:20b"
    mock_tools = [MagicMock()]
    mock_composer = MockPromptComposer()

    agent = create_image_generator_agent(
        vram_orchestrator=mock_orchestrator,
        tools=mock_tools,
        prompt_composer=mock_composer,
        config=None,  # Explicitly None
    )

    # Should use defaults
    assert agent._temperature == 0.7
    assert agent._max_tokens == 2048


# =============================================================================
# Set Tools Test (from BaseAgent)
# =============================================================================

def test_set_tools(image_generator_agent):
    """set_tools() allows updating tools after creation."""
    new_tools = [MagicMock(name="new_tool")]

    image_generator_agent.set_tools(new_tools)

    assert image_generator_agent._tools == new_tools


def test_set_tools_preserves_other_state(image_generator_agent):
    """set_tools() preserves other agent state."""
    original_model = image_generator_agent._model_id
    original_temp = image_generator_agent._temperature
    new_tools = [MagicMock()]

    image_generator_agent.set_tools(new_tools)

    assert image_generator_agent._model_id == original_model
    assert image_generator_agent._temperature == original_temp
