"""Unit tests for Chat Skill (declarative version)."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.declarative_skill import DeclarativeSkill
from app.core.skill_loader import SkillLoader
from app.core.context import ExecutionContext, UserProfile, Message
from app.core.container import Container
from app.core.config import Config, ModelCapabilities, BackendConfig


# =============================================================================
# Mock Classes
# =============================================================================

class MockVRAMOrchestrator:
    """Mock VRAM orchestrator for testing."""
    def __init__(self):
        self.loaded_models = set()
        self.calls = []

    async def request_load(self, model_id: str) -> bool:
        self.calls.append({"method": "request_load", "model_id": model_id})
        self.loaded_models.add(model_id)
        return True

    def is_loaded(self, model_id: str) -> bool:
        return model_id in self.loaded_models


class MockConfig:
    """Mock config for testing."""
    def get_model_for_task(self, task: str) -> str:
        return "test-skill:7b"

    def get_model_capabilities(self, model_id: str):
        backend = BackendConfig(type="ollama", host="http://localhost:11434")
        return ModelCapabilities(
            name=model_id,
            vram_size_gb=10.0,
            backend=backend,
        )


class MockPromptComposer:
    """Mock PromptComposer for testing."""

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


def create_mock_context(
    interface: str = "web",
    history: list = None,
    profile: UserProfile = None
) -> ExecutionContext:
    """Create a mock execution context."""
    return ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface=interface,
        conversation_history=history or [],
        user_profile=profile,
        websocket=None,
    )


def create_test_container(config: Config = None) -> Container:
    """Create a container with mock config."""
    container = Container()
    container.register(Config, config or MockConfig())
    return container


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def chat_skill_def():
    """Load the chat skill definition from SKILL.md."""
    skill_path = Path(__file__).parent.parent.parent / "app/plugins/skills/general/chat/SKILL.md"
    loader = SkillLoader()
    skill_def = loader.load_skill(skill_path)
    assert skill_def is not None, f"Failed to load chat skill from {skill_path}"
    return skill_def


@pytest.fixture
def create_chat_skill(chat_skill_def):
    """Factory to create ChatSkill with mocks."""
    def _create(llm_response: str = "Mock response", config=None):
        orchestrator = MockVRAMOrchestrator()
        test_config = config or MockConfig()
        container = create_test_container(test_config)
        prompt_composer = MockPromptComposer()
        skill = DeclarativeSkill(
            skill_def=chat_skill_def,
            vram_orchestrator=orchestrator,
            prompt_composer=prompt_composer,
            container=container,
        )
        return skill, orchestrator, container, llm_response
    return _create


# =============================================================================
# Basic Execution Tests
# =============================================================================

@pytest.mark.asyncio
async def test_execute_returns_skill_result(create_chat_skill):
    """ChatSkill.execute returns SkillResult with content."""
    skill, orchestrator, _, llm_response = create_chat_skill("Hello! How can I help you today?")
    context = create_mock_context()

    # Mock ollama.Client to return our expected response
    with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.return_value = {
            "message": {"content": "Hello! How can I help you today?"}
        }
        mock_client_class.return_value = mock_client

        result = await skill.execute("Hello", context)

        assert result.content == "Hello! How can I help you today?"
        assert result.metadata["skill"] == "chat"


@pytest.mark.asyncio
async def test_execute_calls_ollama_chat(create_chat_skill):
    """ChatSkill calls ollama.Client.chat with messages."""
    skill, orchestrator, _, _ = create_chat_skill("Response")
    context = create_mock_context()

    with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.return_value = {"message": {"content": "Response"}}
        mock_client_class.return_value = mock_client

        await skill.execute("Test input", context)

        # Verify VRAMOrchestrator was used to load model
        assert len(orchestrator.calls) == 1
        assert orchestrator.calls[0]["method"] == "request_load"

        # Verify ollama.Client.chat was called
        mock_client.chat.assert_called_once()
        call_kwargs = mock_client.chat.call_args[1]
        assert call_kwargs["model"] == "test-skill:7b"
        assert "messages" in call_kwargs

        # Should have system and user message at minimum
        messages = call_kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "Test input"


# =============================================================================
# Context Integration Tests
# =============================================================================

@pytest.mark.asyncio
async def test_uses_interface_context(create_chat_skill):
    """ChatSkill includes interface context in system prompt."""
    skill, orchestrator, _, _ = create_chat_skill("Response")
    context = create_mock_context(interface="discord")

    with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.return_value = {"message": {"content": "Response"}}
        mock_client_class.return_value = mock_client

        await skill.execute("Hello", context)

        messages = mock_client.chat.call_args[1]["messages"]
        system_prompt = messages[0]["content"]

        # Discord interface context should be included
        assert "Discord" in system_prompt or "concise" in system_prompt


@pytest.mark.asyncio
async def test_uses_personalization_context(create_chat_skill):
    """ChatSkill includes user profile personalization."""
    skill, orchestrator, _, _ = create_chat_skill("Response")
    profile = UserProfile(
        user_id="test-user",
        communication_style="technical",
        explicit_expertise=["python", "ml"],
    )
    context = create_mock_context(profile=profile)

    with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.return_value = {"message": {"content": "Response"}}
        mock_client_class.return_value = mock_client

        await skill.execute("Hello", context)

        messages = mock_client.chat.call_args[1]["messages"]
        system_prompt = messages[0]["content"]

        # Personalization should be included
        assert "technical" in system_prompt
        assert "python" in system_prompt


@pytest.mark.asyncio
async def test_includes_conversation_history(create_chat_skill):
    """ChatSkill includes recent conversation history."""
    skill, orchestrator, _, _ = create_chat_skill("Response")
    history = [
        Message(role="user", content="Previous question"),
        Message(role="assistant", content="Previous answer"),
    ]
    context = create_mock_context(history=history)

    with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.return_value = {"message": {"content": "Response"}}
        mock_client_class.return_value = mock_client

        await skill.execute("New question", context)

        messages = mock_client.chat.call_args[1]["messages"]

        # Should include history between system and current user message
        # System + 2 history messages + current user = 4 messages
        assert len(messages) == 4
        assert messages[1]["content"] == "Previous question"
        assert messages[2]["content"] == "Previous answer"
        assert messages[3]["content"] == "New question"


@pytest.mark.asyncio
async def test_limits_conversation_history(create_chat_skill):
    """ChatSkill limits history to last 6 messages."""
    skill, orchestrator, _, _ = create_chat_skill("Response")
    # Create 10 messages
    history = [
        Message(role="user" if i % 2 == 0 else "assistant", content=f"Message {i}")
        for i in range(10)
    ]
    context = create_mock_context(history=history)

    with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.return_value = {"message": {"content": "Response"}}
        mock_client_class.return_value = mock_client

        await skill.execute("Current", context)

        messages = mock_client.chat.call_args[1]["messages"]

        # System + 6 history + current user = 8 messages
        assert len(messages) == 8


# =============================================================================
# Metadata Tests
# =============================================================================

@pytest.mark.asyncio
async def test_metadata_includes_model(create_chat_skill):
    """SkillResult metadata includes model used."""
    skill, orchestrator, _, _ = create_chat_skill("Response")
    context = create_mock_context()

    with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.return_value = {"message": {"content": "Response"}}
        mock_client_class.return_value = mock_client

        result = await skill.execute("Test", context)

        assert result.metadata["model"] == "test-skill:7b"


@pytest.mark.asyncio
async def test_metadata_includes_declarative_flag(create_chat_skill):
    """SkillResult metadata includes declarative flag."""
    skill, orchestrator, _, _ = create_chat_skill("Response")
    context = create_mock_context()

    with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.return_value = {"message": {"content": "Response"}}
        mock_client_class.return_value = mock_client

        result = await skill.execute("Test", context)

        assert result.metadata["declarative"] is True


# =============================================================================
# Skill Definition Tests
# =============================================================================

def test_skill_name(chat_skill_def):
    """Chat skill has correct name attribute."""
    assert chat_skill_def.name == "chat"


def test_skill_category(chat_skill_def):
    """Chat skill has correct category attribute (derived from directory path)."""
    assert chat_skill_def.category == "general"


def test_skill_includes_history(chat_skill_def):
    """Chat skill has include_history enabled."""
    assert chat_skill_def.include_history is True
    assert chat_skill_def.history_turns == 6


def test_skill_temperature(chat_skill_def):
    """Chat skill has correct temperature."""
    assert chat_skill_def.temperature == 0.7
