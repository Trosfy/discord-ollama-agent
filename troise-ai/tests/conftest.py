"""Shared test fixtures for TROISE AI tests."""
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add app to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.container import Container
from app.core.context import ExecutionContext, UserProfile, Message
from app.core.config import Config, BackendConfig, ModelPriority
from app.core.registry import PluginRegistry
from app.core.interfaces.skill import SkillResult
from app.core.interfaces.agent import AgentResult
from app.core.interfaces.tool import ToolResult


# =============================================================================
# Mock VRAM Orchestrator
# =============================================================================

class MockStrandsModel:
    """Mock Strands Model for testing."""
    def __init__(self, model_id: str = "test:7b"):
        self.model_id = model_id
        self.config = {"model_id": model_id, "temperature": 0.7, "max_tokens": 4096}

    def update_config(self, **kwargs):
        self.config.update(kwargs)

    def get_config(self):
        return self.config

    async def stream(self, messages, **kwargs):
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": "mock response"}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}


class MockVRAMOrchestrator:
    """Mock VRAM orchestrator for testing."""

    def __init__(self, responses: Optional[Dict[str, str]] = None):
        """
        Initialize mock VRAM orchestrator.

        Args:
            responses: Dict mapping model substrings to responses.
                      If None, returns default responses.
        """
        self._responses = responses or {}
        self._calls: List[Dict[str, Any]] = []
        self._loaded_models: set = set()

    async def get_model(
        self,
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        additional_args: Optional[Dict[str, Any]] = None,
    ) -> MockStrandsModel:
        """Record call and return mock Strands model."""
        self._calls.append({
            "method": "get_model",
            "model_id": model_id,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "additional_args": additional_args,
        })
        self._loaded_models.add(model_id)
        model = MockStrandsModel(model_id)
        model.config["temperature"] = temperature
        model.config["max_tokens"] = max_tokens
        return model

    async def request_load(self, model_id: str) -> bool:
        """Record load request and return True."""
        self._calls.append({
            "method": "request_load",
            "model_id": model_id,
        })
        self._loaded_models.add(model_id)
        return True

    def is_loaded(self, model_id: str) -> bool:
        """Check if model is loaded."""
        return model_id in self._loaded_models

    def get_profile_model(self, role: str = "agent") -> str:
        """Return a mock model ID for the role."""
        role_map = {
            "agent": "test-agent:70b",
            "router": "test-router:7b",
            "code": "test-code:13b",
            "vision": "test-vision:7b",
            "embedding": "test-embed:0.5b",
        }
        return role_map.get(role, "test:7b")

    @property
    def calls(self) -> List[Dict[str, Any]]:
        """Get recorded calls."""
        return self._calls

    def reset(self):
        """Clear recorded calls and loaded models."""
        self._calls.clear()
        self._loaded_models.clear()


@pytest.fixture
def mock_vram_orchestrator():
    """Create a mock VRAM orchestrator."""
    return MockVRAMOrchestrator()


@pytest.fixture
def mock_vram_orchestrator_with_responses():
    """Factory fixture for mock VRAM orchestrator with custom responses."""
    def _create(responses: Dict[str, str]) -> MockVRAMOrchestrator:
        return MockVRAMOrchestrator(responses)
    return _create


# =============================================================================
# Mock Config
# =============================================================================

class MockProfile:
    """Mock profile for testing."""
    name = "test"
    router_model = "test-router:7b"
    general_model = "test-general:70b"
    research_model = "test-research:24b"
    code_model = "test-code:13b"
    braindump_model = "test-braindump:24b"
    vision_model = "test-vision:7b"
    embedding_model = "test-embed:0.5b"
    available_models = []


class MockConfig:
    """Mock configuration for testing."""

    def __init__(self):
        self.profile = MockProfile()
        self.backends = {
            "ollama": BackendConfig(
                type="ollama",
                host="http://localhost:11434",
            )
        }
        self._data = {"active_profile": "test"}

    @property
    def dgx_config(self) -> Dict:
        return {}

    @property
    def vault_path(self) -> str:
        return "/tmp/test-vault"

    def get_model_for_task(self, task: str) -> str:
        task_map = {
            "route": self.profile.router_model,
            "routing": self.profile.router_model,
            "general": self.profile.general_model,
            "research": self.profile.research_model,
            "code": self.profile.code_model,
            "braindump": self.profile.braindump_model,
            "vision": self.profile.vision_model,
            "embedding": self.profile.embedding_model,
        }
        return task_map.get(task, self.profile.general_model)

    def get_backend_for_model(self, model_id: str) -> Optional[BackendConfig]:
        return self.backends.get("ollama")


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    return MockConfig()


# =============================================================================
# Mock Execution Context
# =============================================================================

class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []
        self.pending_responses: Dict[str, str] = {}

    async def send_json(self, data: Dict[str, Any]):
        """Record sent message."""
        self.sent_messages.append(data)

    def set_response(self, request_id: str, response: str):
        """Set a response for a pending question."""
        self.pending_responses[request_id] = response


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket."""
    return MockWebSocket()


@pytest.fixture
def mock_context(mock_websocket):
    """Create a mock execution context."""
    return ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
        websocket=mock_websocket,
        user_profile=UserProfile(
            user_id="test-user",
            communication_style="balanced",
            explicit_expertise=["python", "testing"],
        ),
    )


@pytest.fixture
def mock_context_no_websocket():
    """Create a mock execution context without WebSocket."""
    return ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="api",
        websocket=None,
    )


# =============================================================================
# Mock Registry with Test Plugins
# =============================================================================

class MockSkill:
    """Mock skill for testing."""
    name = "mock_skill"
    category = "test"

    def __init__(self, **kwargs):
        pass

    async def execute(self, input: str, context: ExecutionContext) -> SkillResult:
        return SkillResult(content=f"Mock skill response to: {input}")


class MockAgent:
    """Mock agent for testing."""
    name = "mock_agent"
    category = "test"
    tools = ["mock_tool"]

    def __init__(self, **kwargs):
        self.tools_provided = kwargs.get("tools", [])

    async def execute(self, input: str, context: ExecutionContext) -> AgentResult:
        return AgentResult(
            content=f"Mock agent response to: {input}",
            tool_calls=[{"name": "mock_tool", "args": {}}],
        )


class MockTool:
    """Mock tool for testing."""
    name = "mock_tool"
    description = "A mock tool for testing"
    parameters = {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "Test input"},
        },
        "required": ["input"],
    }

    def __init__(self, **kwargs):
        pass

    async def execute(
        self,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        return ToolResult(content=f"Mock tool result: {params.get('input', '')}")

    def to_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


def mock_tool_factory(context: ExecutionContext, container: Container) -> MockTool:
    """Factory function for mock tool."""
    return MockTool()


@pytest.fixture
def mock_registry():
    """Create a mock registry with test plugins."""
    registry = PluginRegistry()

    # Manually register test plugins
    registry._skills["mock_skill"] = {
        "type": "skill",
        "name": "mock_skill",
        "category": "test",
        "class": MockSkill,
        "description": "Mock skill for testing",
        "use_when": "Testing purposes",
    }
    registry._skills["chat"] = {
        "type": "skill",
        "name": "chat",
        "category": "conversation",
        "class": MockSkill,
        "description": "Chat skill",
        "use_when": "General conversation",
    }

    registry._agents["mock_agent"] = {
        "type": "agent",
        "name": "mock_agent",
        "category": "test",
        "class": MockAgent,
        "description": "Mock agent for testing",
        "use_when": "Testing purposes",
        "config": {
            "tools": ["mock_tool"],
            "model": "test-agent:70b",
        },
    }

    registry._tools["mock_tool"] = {
        "type": "tool",
        "name": "mock_tool",
        "factory": mock_tool_factory,
        "description": "Mock tool for testing",
    }

    return registry


# =============================================================================
# Test Container
# =============================================================================

@pytest.fixture
def test_container(mock_config, mock_vram_orchestrator, mock_registry):
    """Create a test container with mocks registered."""
    container = Container()

    # Register mocks
    container.register(Config, mock_config)
    container.register(PluginRegistry, mock_registry)

    # Register VRAM orchestrator under the interface
    from app.core.interfaces.services import IVRAMOrchestrator
    container.register(IVRAMOrchestrator, mock_vram_orchestrator)

    return container


# =============================================================================
# Async Helpers
# =============================================================================

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
