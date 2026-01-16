"""Unit tests for Router."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.router import Router, RoutingResult, ROUTE_MAP


# =============================================================================
# Mock Fixtures
# =============================================================================

class MockProfile:
    """Mock profile for router tests."""
    router_model = "test-router:7b"


class MockConfig:
    """Mock config for router tests."""
    def __init__(self):
        self.profile = MockProfile()


class MockStrandsModel:
    """Mock Strands Model for testing."""
    def __init__(self, response: str = "GENERAL"):
        self._response = response
        self.model_id = "test-router:7b"
        self.config = {"temperature": 0.1, "max_tokens": 500}

    def update_config(self, **kwargs):
        self.config.update(kwargs)

    def get_config(self):
        return self.config


class MockVRAMOrchestrator:
    """Mock VRAM orchestrator that returns a mock model."""
    def __init__(self, response: str = "GENERAL"):
        self._response = response
        self.calls = []

    async def get_model(self, model_id: str, temperature: float = 0.7, max_tokens: int = 4096, additional_args=None):
        self.calls.append({
            "method": "get_model",
            "model_id": model_id,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "additional_args": additional_args,
        })
        return MockStrandsModel(self._response)


# =============================================================================
# Route Classification Tests
# =============================================================================

async def test_route_to_general():
    """Routes to general agent for general queries."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator("GENERAL")

    # Mock Strands Agent to return our expected response
    with patch("app.core.router.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = "GENERAL"
        mock_agent_class.return_value = mock_agent_instance

        router = Router(config, orchestrator)
        result = await router.route("What is Python?")

        assert result.type == "agent"
        assert result.name == "general"
        assert result.fallback is False


async def test_route_to_research():
    """Routes to deep_research agent for research queries."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator("RESEARCH")

    with patch("app.core.router.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = "RESEARCH"
        mock_agent_class.return_value = mock_agent_instance

        router = Router(config, orchestrator)
        result = await router.route("Research quantum computing advances")

        assert result.type == "agent"
        assert result.name == "deep_research"
        assert result.fallback is False


async def test_route_to_code():
    """Routes to agentic_code agent for code queries."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator("CODE")

    with patch("app.core.router.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = "CODE"
        mock_agent_class.return_value = mock_agent_instance

        router = Router(config, orchestrator)
        result = await router.route("Write a function to reverse a string")

        assert result.type == "agent"
        assert result.name == "agentic_code"
        assert result.fallback is False


async def test_route_to_braindump():
    """Routes to braindump agent for thought capture."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator("BRAINDUMP")

    with patch("app.core.router.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = "BRAINDUMP"
        mock_agent_class.return_value = mock_agent_instance

        router = Router(config, orchestrator)
        result = await router.route("Let me dump my thoughts about this project")

        assert result.type == "agent"
        assert result.name == "braindump"
        assert result.fallback is False


# =============================================================================
# Case Insensitivity Tests
# =============================================================================

async def test_route_lowercase():
    """Handles lowercase classification response."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator("general")

    with patch("app.core.router.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = "general"
        mock_agent_class.return_value = mock_agent_instance

        router = Router(config, orchestrator)
        result = await router.route("Hello")

        assert result.type == "agent"
        assert result.name == "general"


async def test_route_mixed_case():
    """Handles mixed case classification response."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator("Research")

    with patch("app.core.router.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = "Research"
        mock_agent_class.return_value = mock_agent_instance

        router = Router(config, orchestrator)
        result = await router.route("Look into AI developments")

        assert result.type == "agent"
        assert result.name == "deep_research"


# =============================================================================
# Fallback Tests
# =============================================================================

async def test_fallback_on_unknown_classification():
    """Falls back to GENERAL for unknown classification."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator("UNKNOWN_THING")

    with patch("app.core.router.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = "UNKNOWN_THING"
        mock_agent_class.return_value = mock_agent_instance

        router = Router(config, orchestrator)
        result = await router.route("Do something")

        assert result.type == "agent"
        assert result.name == "general"
        assert result.fallback is True


async def test_fallback_on_empty_response():
    """Falls back to GENERAL for empty response."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator("")

    with patch("app.core.router.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = ""
        mock_agent_class.return_value = mock_agent_instance

        router = Router(config, orchestrator)
        result = await router.route("Test")

        assert result.type == "agent"
        assert result.name == "general"
        assert result.fallback is True


async def test_fallback_on_orchestrator_exception():
    """Falls back when VRAM orchestrator raises exception."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator()
    orchestrator.get_model = AsyncMock(side_effect=Exception("Model error"))

    router = Router(config, orchestrator)
    result = await router.route("Test input")

    assert result.type == "agent"
    assert result.name == "general"
    assert result.fallback is True


# =============================================================================
# Response Parsing Tests
# =============================================================================

def test_parse_exact_match():
    """Parses exact match classification."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator()
    router = Router(config, orchestrator)

    result = router._parse_response("CODE")

    assert result.type == "agent"
    assert result.name == "agentic_code"
    assert result.confidence == 0.9


def test_parse_with_whitespace():
    """Handles whitespace in response."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator()
    router = Router(config, orchestrator)

    result = router._parse_response("  RESEARCH  \n")

    assert result.type == "agent"
    assert result.name == "deep_research"


def test_parse_extracts_from_extra_text():
    """Extracts classification from response with extra text."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator()
    router = Router(config, orchestrator)

    result = router._parse_response("Based on the request, I classify this as CODE.")

    assert result.type == "agent"
    assert result.name == "agentic_code"
    assert result.confidence == 0.7  # Lower confidence for extraction


def test_parse_unknown_returns_fallback():
    """Returns fallback for unknown classification."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator()
    router = Router(config, orchestrator)

    result = router._parse_response("Something completely irrelevant")

    assert result.type == "agent"
    assert result.name == "general"
    assert result.fallback is True


# =============================================================================
# VRAMOrchestrator Integration Tests
# =============================================================================

async def test_routing_uses_vram_orchestrator():
    """Router calls VRAMOrchestrator.get_model with correct parameters."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator("GENERAL")

    with patch("app.core.router.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = "GENERAL"
        mock_agent_class.return_value = mock_agent_instance

        router = Router(config, orchestrator)
        await router.route("Hello world")

        # Verify VRAMOrchestrator was called
        assert len(orchestrator.calls) == 1
        call = orchestrator.calls[0]

        assert call["method"] == "get_model"
        assert call["model_id"] == "test-router:7b"
        assert call["temperature"] == 0.1  # Low temp for consistent routing
        assert call["max_tokens"] == 500  # Room for thinking + classification


async def test_routing_creates_agent_with_system_prompt():
    """Router creates Strands Agent with system prompt containing classifications."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator("GENERAL")

    with patch("app.core.router.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = "GENERAL"
        mock_agent_class.return_value = mock_agent_instance

        router = Router(config, orchestrator)
        await router.route("Test input")

        # Check that Agent was created with correct parameters
        mock_agent_class.assert_called_once()
        call_kwargs = mock_agent_class.call_args[1]

        assert "system_prompt" in call_kwargs
        system_prompt = call_kwargs["system_prompt"]
        assert "GENERAL" in system_prompt
        assert "RESEARCH" in system_prompt
        assert "CODE" in system_prompt
        assert "BRAINDUMP" in system_prompt
        assert call_kwargs["tools"] == []


async def test_routing_with_file_context():
    """Router includes file context in prompt when provided."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator("CODE")

    with patch("app.core.router.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = "CODE"
        mock_agent_class.return_value = mock_agent_instance

        router = Router(config, orchestrator)
        await router.route(
            "Review this code",
            file_context="def hello():\n    print('world')"
        )

        # Check that file content is in the system prompt
        call_kwargs = mock_agent_class.call_args[1]
        system_prompt = call_kwargs["system_prompt"]

        assert "ATTACHED FILE CONTENT" in system_prompt
        assert "def hello():" in system_prompt


# =============================================================================
# Utility Method Tests
# =============================================================================

def test_get_routing_table():
    """get_routing_table returns formatted route list."""
    config = MockConfig()
    orchestrator = MockVRAMOrchestrator()

    router = Router(config, orchestrator)
    table = router.get_routing_table()

    assert "GENERAL" in table
    assert "RESEARCH" in table
    assert "CODE" in table
    assert "BRAINDUMP" in table
    assert "agent:general" in table
    assert "agent:deep_research" in table


def test_routing_result_defaults():
    """RoutingResult has sensible defaults."""
    result = RoutingResult(type="agent", name="general", reason="test")

    assert result.confidence == 0.9
    assert result.fallback is False


def test_route_map_completeness():
    """All expected routes are in ROUTE_MAP."""
    assert "GENERAL" in ROUTE_MAP
    assert "RESEARCH" in ROUTE_MAP
    assert "CODE" in ROUTE_MAP
    assert "BRAINDUMP" in ROUTE_MAP

    # All map to agent type
    for route, (handler_type, handler_name) in ROUTE_MAP.items():
        assert handler_type == "agent"
