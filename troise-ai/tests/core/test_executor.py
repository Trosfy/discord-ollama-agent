"""Unit tests for Executor."""
import pytest
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from app.core.executor import Executor, ExecutionResult
from app.core.router import RoutingResult
from app.core.registry import PluginRegistry
from app.core.container import Container
from app.core.tool_factory import ToolFactory
from app.core.context import ExecutionContext
from app.core.exceptions import PluginNotFoundError, PluginError
from app.core.interfaces.skill import SkillResult
from app.core.interfaces.agent import AgentResult
from app.core.interfaces.services import IVRAMOrchestrator
from app.prompts import PromptComposer


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

    def compose_skill_prompt(
        self,
        skill_system_prompt: str,
        interface: str,
        profile: str = None,
        user_profile=None,
    ) -> str:
        """Compose skill prompt with interface and personalization layers."""
        interface_context = f"## {interface.title()} Interface\nFormatted for {interface}."
        personalization_context = ""
        if user_profile:
            personalization_context = user_profile.get_personalization_context()

        prompt = skill_system_prompt
        prompt = prompt.replace("{interface_context}", interface_context)
        prompt = prompt.replace(
            "{personalization_context}",
            personalization_context or "No specific preferences.",
        )
        return prompt

class MockLLMProviderModel:
    """Mock Strands Model."""
    def update_config(self, **kwargs):
        pass

    def get_config(self):
        return {"model_id": "test:7b", "temperature": 0.7}

    async def stream(self, messages, **kwargs):
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": "mock response"}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}


class MockVRAMOrchestrator:
    """Mock VRAM orchestrator."""
    async def get_model(self, model_id, temperature=0.7, max_tokens=4096, additional_args=None):
        return MockLLMProviderModel()

    async def request_load(self, model_id):
        return True

    def is_loaded(self, model_id):
        return True


class MockSkill:
    """Mock skill for testing."""
    name = "mock_skill"

    def __init__(self, vram_orchestrator, container):
        self._vram_orchestrator = vram_orchestrator
        self._container = container

    async def execute(self, input: str, context: ExecutionContext) -> SkillResult:
        return SkillResult(
            content=f"Skill response to: {input}",
            metadata={"processed_by": "mock_skill"},
        )


class MockSkillThatRaises:
    """Mock skill that raises an exception."""
    name = "failing_skill"

    def __init__(self, vram_orchestrator, container):
        pass

    async def execute(self, input: str, context: ExecutionContext) -> SkillResult:
        raise RuntimeError("Skill execution failed!")


class MockAgent:
    """Mock agent for testing."""
    name = "mock_agent"

    def __init__(self, vram_orchestrator, tools, prompt_composer, config):
        self._vram_orchestrator = vram_orchestrator
        self._tools = tools
        self._prompt_composer = prompt_composer
        self._config = config

    async def execute(self, input: str, context: ExecutionContext, stream_handler=None) -> AgentResult:
        return AgentResult(
            content=f"Agent response to: {input}",
            tool_calls=[{"name": "test_tool", "args": {"x": 1}}],
            metadata={"agent_name": "mock_agent", "tool_count": len(self._tools)},
        )


class MockToolFactory:
    """Mock tool factory for testing."""
    def __init__(self, registry: PluginRegistry):
        self._registry = registry

    def create_tools_for_agent(self, agent_name: str, context: ExecutionContext) -> List[Dict]:
        return [
            {"name": "tool1", "description": "Test tool 1"},
            {"name": "tool2", "description": "Test tool 2"},
        ]

    def create_tool(self, tool_name: str, context: ExecutionContext) -> Optional[Dict]:
        return {"name": tool_name}

    async def cleanup(self):
        """Clean up any tool resources."""
        pass


def create_mock_context() -> ExecutionContext:
    """Create a mock execution context."""
    return ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="test",
        websocket=None,
    )


def create_test_registry() -> PluginRegistry:
    """Create a registry with mock plugins."""
    registry = PluginRegistry()

    registry._skills["mock_skill"] = {
        "type": "skill",
        "name": "mock_skill",
        "class": MockSkill,
        "description": "A mock skill",
    }

    registry._skills["failing_skill"] = {
        "type": "skill",
        "name": "failing_skill",
        "class": MockSkillThatRaises,
        "description": "A skill that fails",
    }

    registry._agents["mock_agent"] = {
        "type": "agent",
        "name": "mock_agent",
        "class": MockAgent,
        "description": "A mock agent",
        "config": {
            "tools": ["tool1", "tool2"],
            "model": "test:7b",
        },
    }

    return registry


def create_test_container() -> Container:
    """Create a container with mock services."""
    container = Container()
    container.register(IVRAMOrchestrator, MockVRAMOrchestrator())
    container.register(PromptComposer, MockPromptComposer())
    return container


# =============================================================================
# Execute Skill Tests
# =============================================================================

async def test_execute_skill():
    """Executes skill successfully and returns ExecutionResult."""
    registry = create_test_registry()
    container = create_test_container()
    tool_factory = MockToolFactory(registry)
    context = create_mock_context()

    executor = Executor(registry, container, tool_factory)
    routing_result = RoutingResult(type="skill", name="mock_skill", reason="test")

    result = await executor.execute(routing_result, "Hello world", context)

    assert result.success is True
    assert result.source_type == "skill"
    assert result.source_name == "mock_skill"
    assert "Hello world" in result.content
    assert result.metadata["processed_by"] == "mock_skill"


async def test_execute_skill_not_found():
    """Returns error ExecutionResult when skill not in registry."""
    registry = create_test_registry()
    container = create_test_container()
    tool_factory = MockToolFactory(registry)
    context = create_mock_context()

    executor = Executor(registry, container, tool_factory)
    routing_result = RoutingResult(type="skill", name="nonexistent", reason="test")

    result = await executor.execute(routing_result, "Hello", context)

    assert result.success is False
    assert "not found" in result.error.lower()


async def test_execute_skill_directly():
    """execute_skill_directly works without routing."""
    registry = create_test_registry()
    container = create_test_container()
    tool_factory = MockToolFactory(registry)
    context = create_mock_context()

    executor = Executor(registry, container, tool_factory)
    result = await executor.execute_skill_directly("mock_skill", "Direct call", context)

    assert result.success is True
    assert result.source_name == "mock_skill"
    assert "Direct call" in result.content


# =============================================================================
# Execute Agent Tests
# =============================================================================

async def test_execute_agent():
    """Executes agent with tools and returns ExecutionResult."""
    registry = create_test_registry()
    container = create_test_container()
    tool_factory = MockToolFactory(registry)
    context = create_mock_context()

    executor = Executor(registry, container, tool_factory)
    routing_result = RoutingResult(type="agent", name="mock_agent", reason="test")

    result = await executor.execute(routing_result, "Do something complex", context)

    assert result.success is True
    assert result.source_type == "agent"
    assert result.source_name == "mock_agent"
    assert "Do something complex" in result.content
    assert len(result.tool_calls) > 0
    assert result.tool_calls[0]["name"] == "test_tool"


async def test_execute_agent_not_found():
    """Returns error ExecutionResult when agent not in registry."""
    registry = create_test_registry()
    container = create_test_container()
    tool_factory = MockToolFactory(registry)
    context = create_mock_context()

    executor = Executor(registry, container, tool_factory)
    routing_result = RoutingResult(type="agent", name="nonexistent", reason="test")

    result = await executor.execute(routing_result, "Hello", context)

    assert result.success is False
    assert "not found" in result.error.lower()


async def test_execute_agent_directly():
    """execute_agent_directly works without routing."""
    registry = create_test_registry()
    container = create_test_container()
    tool_factory = MockToolFactory(registry)
    context = create_mock_context()

    executor = Executor(registry, container, tool_factory)
    result = await executor.execute_agent_directly("mock_agent", "Direct agent call", context)

    assert result.success is True
    assert result.source_name == "mock_agent"


async def test_agent_sets_context_name():
    """Agent execution sets context.agent_name."""
    registry = create_test_registry()
    container = create_test_container()
    tool_factory = MockToolFactory(registry)
    context = create_mock_context()

    executor = Executor(registry, container, tool_factory)
    routing_result = RoutingResult(type="agent", name="mock_agent", reason="test")

    await executor.execute(routing_result, "Test", context)

    assert context.agent_name == "mock_agent"


# =============================================================================
# Error Handling Tests
# =============================================================================

async def test_skill_error_handling():
    """Captures skill errors in ExecutionResult."""
    registry = create_test_registry()
    container = create_test_container()
    tool_factory = MockToolFactory(registry)
    context = create_mock_context()

    executor = Executor(registry, container, tool_factory)
    routing_result = RoutingResult(type="skill", name="failing_skill", reason="test")

    result = await executor.execute(routing_result, "This will fail", context)

    assert result.success is False
    assert "Skill execution failed!" in result.error
    assert result.source_name == "failing_skill"


async def test_unknown_routing_type():
    """Handles unknown routing type gracefully."""
    registry = create_test_registry()
    container = create_test_container()
    tool_factory = MockToolFactory(registry)
    context = create_mock_context()

    executor = Executor(registry, container, tool_factory)
    routing_result = RoutingResult(type="unknown", name="something", reason="test")

    result = await executor.execute(routing_result, "Test", context)

    assert result.success is False
    assert "Unknown routing type" in result.error


# =============================================================================
# ExecutionResult Tests
# =============================================================================

def test_execution_result_defaults():
    """ExecutionResult has sensible defaults."""
    result = ExecutionResult(
        content="test content",
        source_type="skill",
        source_name="test",
    )

    assert result.tool_calls == []
    assert result.metadata == {}
    assert result.success is True
    assert result.error is None


def test_execution_result_with_all_fields():
    """ExecutionResult stores all fields correctly."""
    result = ExecutionResult(
        content="response",
        source_type="agent",
        source_name="my_agent",
        tool_calls=[{"name": "tool", "args": {}}],
        metadata={"key": "value"},
        success=True,
        error=None,
    )

    assert result.content == "response"
    assert result.source_type == "agent"
    assert result.source_name == "my_agent"
    assert len(result.tool_calls) == 1
    assert result.metadata["key"] == "value"


def test_execution_result_error_state():
    """ExecutionResult represents error state correctly."""
    result = ExecutionResult(
        content="",
        source_type="skill",
        source_name="broken",
        success=False,
        error="Something went wrong",
    )

    assert result.success is False
    assert result.error == "Something went wrong"
    assert result.content == ""
