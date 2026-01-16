"""Tests for the declarative skill executor."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from app.core.declarative_skill import DeclarativeSkill
from app.core.skill_loader import DeclarativeSkillDef, SkillExample
from app.core.context import ExecutionContext, UserProfile, Message
from app.core.container import Container
from app.core.config import Config, BackendConfig, ModelCapabilities


class MockVRAMOrchestrator:
    """Mock VRAM orchestrator for testing."""

    def __init__(self):
        self.loaded_models = set()
        self.calls = []

    async def request_load(self, model_id: str) -> bool:
        """Track model load requests."""
        self.calls.append({"method": "request_load", "model_id": model_id})
        self.loaded_models.add(model_id)
        return True

    def is_loaded(self, model_id: str) -> bool:
        return model_id in self.loaded_models


class MockConfig:
    """Mock config for testing."""

    def get_model_for_task(self, task: str) -> str:
        return f"test-model-for-{task}"

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

        # Simple template substitution
        prompt = skill_system_prompt
        prompt = prompt.replace("{interface_context}", interface_context)
        prompt = prompt.replace(
            "{personalization_context}",
            personalization_context or "No specific preferences.",
        )
        return prompt


class TestDeclarativeSkill:
    """Tests for DeclarativeSkill executor."""

    @pytest.fixture
    def mock_vram_orchestrator(self):
        """Create mock VRAM orchestrator."""
        return MockVRAMOrchestrator()

    @pytest.fixture
    def mock_prompt_composer(self):
        """Create mock prompt composer."""
        return MockPromptComposer()

    @pytest.fixture
    def mock_container(self):
        """Create mock container."""
        container = Container()
        container.register(Config, MockConfig())
        return container

    @pytest.fixture
    def mock_context(self):
        """Create mock execution context."""
        return ExecutionContext(
            user_id="test-user",
            session_id="test-session",
            interface="web",
            user_profile=UserProfile(
                user_id="test-user",
                communication_style="balanced",
                explicit_expertise=["python"],
            ),
        )

    @pytest.fixture
    def general_skill_def(self):
        """Create a general skill definition."""
        return DeclarativeSkillDef(
            name="test_skill",
            description="A test skill",
            use_when="Testing",
            category="test",
            system_prompt="You are a test assistant.\n\n{interface_context}\n\n{personalization_context}",
            temperature=0.5,
            max_tokens=1024,
            model_task="general",
        )

    @pytest.fixture
    def skill_def_with_examples(self):
        """Create skill definition with examples."""
        return DeclarativeSkillDef(
            name="example_skill",
            description="Skill with examples",
            use_when="Testing examples",
            category="test",
            system_prompt="You are helpful.",
            examples=[
                SkillExample(user="Hello", assistant="Hi there!"),
                SkillExample(user="Goodbye", assistant="Farewell!"),
            ],
        )

    @pytest.fixture
    def skill_def_with_guardrails(self):
        """Create skill definition with guardrails."""
        return DeclarativeSkillDef(
            name="guarded_skill",
            description="Skill with guardrails",
            use_when="Testing guardrails",
            category="test",
            system_prompt="You are careful.",
            guardrails="- Never do X\n- Always do Y",
        )

    @pytest.fixture
    def skill_def_with_history(self):
        """Create skill definition with history enabled."""
        return DeclarativeSkillDef(
            name="chat_skill",
            description="Conversational skill",
            use_when="Chat",
            category="conversation",
            system_prompt="You are conversational.",
            include_history=True,
            history_turns=3,
        )

    @pytest.fixture
    def skill_def_with_template(self):
        """Create skill definition with user prompt template."""
        return DeclarativeSkillDef(
            name="template_skill",
            description="Skill with template",
            use_when="Testing template",
            category="test",
            system_prompt="You summarize.",
            user_prompt_template="Please process:\n\n{input}",
        )

    @pytest.mark.asyncio
    async def test_general_skill_execution(
        self, general_skill_def, mock_vram_orchestrator, mock_prompt_composer, mock_container, mock_context
    ):
        """Test basic skill execution."""
        skill = DeclarativeSkill(
            skill_def=general_skill_def,
            vram_orchestrator=mock_vram_orchestrator,
            prompt_composer=mock_prompt_composer,
            container=mock_container,
        )

        with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat.return_value = {"message": {"content": "Test skill response"}}
            mock_client_class.return_value = mock_client

            result = await skill.execute("Test input", mock_context)

            assert result.content == "Test skill response"
            assert result.metadata["skill"] == "test_skill"
            assert result.metadata["model"] == "test-model-for-general"

    @pytest.mark.asyncio
    async def test_skill_llm_call_parameters(
        self, general_skill_def, mock_vram_orchestrator, mock_prompt_composer, mock_container, mock_context
    ):
        """Test that LLM is called with correct parameters."""
        skill = DeclarativeSkill(
            skill_def=general_skill_def,
            vram_orchestrator=mock_vram_orchestrator,
            prompt_composer=mock_prompt_composer,
            container=mock_container,
        )

        with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat.return_value = {"message": {"content": "Response"}}
            mock_client_class.return_value = mock_client

            await skill.execute("Test input", mock_context)

            # Verify VRAMOrchestrator was used to load model
            assert len(mock_vram_orchestrator.calls) == 1
            assert mock_vram_orchestrator.calls[0]["method"] == "request_load"
            assert mock_vram_orchestrator.calls[0]["model_id"] == "test-model-for-general"

            # Verify ollama.Client.chat was called with correct parameters
            mock_client.chat.assert_called_once()
            call_kwargs = mock_client.chat.call_args[1]
            assert call_kwargs["model"] == "test-model-for-general"
            assert call_kwargs["options"]["temperature"] == 0.5
            assert call_kwargs["options"]["num_predict"] == 1024

    @pytest.mark.asyncio
    async def test_skill_messages_structure(
        self, general_skill_def, mock_vram_orchestrator, mock_prompt_composer, mock_container, mock_context
    ):
        """Test that messages are structured correctly."""
        skill = DeclarativeSkill(
            skill_def=general_skill_def,
            vram_orchestrator=mock_vram_orchestrator,
            prompt_composer=mock_prompt_composer,
            container=mock_container,
        )

        with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat.return_value = {"message": {"content": "Response"}}
            mock_client_class.return_value = mock_client

            await skill.execute("User query", mock_context)

            messages = mock_client.chat.call_args[1]["messages"]

            # Should have system and user messages
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == "User query"

    @pytest.mark.asyncio
    async def test_skill_context_injection(
        self, general_skill_def, mock_vram_orchestrator, mock_prompt_composer, mock_container, mock_context
    ):
        """Test that context is injected into system prompt."""
        skill = DeclarativeSkill(
            skill_def=general_skill_def,
            vram_orchestrator=mock_vram_orchestrator,
            prompt_composer=mock_prompt_composer,
            container=mock_container,
        )

        with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat.return_value = {"message": {"content": "Response"}}
            mock_client_class.return_value = mock_client

            await skill.execute("Test", mock_context)

            system_prompt = mock_client.chat.call_args[1]["messages"][0]["content"]

            # Should have injected interface context
            assert "web" in system_prompt.lower() or "interface" in system_prompt.lower()

    @pytest.mark.asyncio
    async def test_skill_with_examples(
        self, skill_def_with_examples, mock_vram_orchestrator, mock_prompt_composer, mock_container, mock_context
    ):
        """Test that examples are included as messages."""
        skill = DeclarativeSkill(
            skill_def=skill_def_with_examples,
            vram_orchestrator=mock_vram_orchestrator,
            prompt_composer=mock_prompt_composer,
            container=mock_container,
        )

        with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat.return_value = {"message": {"content": "Response"}}
            mock_client_class.return_value = mock_client

            await skill.execute("New query", mock_context)

            messages = mock_client.chat.call_args[1]["messages"]

            # System + 2 examples (4 messages) + user = 6 messages
            assert len(messages) == 6
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == "Hello"
            assert messages[2]["role"] == "assistant"
            assert messages[2]["content"] == "Hi there!"
            assert messages[3]["role"] == "user"
            assert messages[3]["content"] == "Goodbye"
            assert messages[4]["role"] == "assistant"
            assert messages[4]["content"] == "Farewell!"
            assert messages[5]["role"] == "user"
            assert messages[5]["content"] == "New query"

    @pytest.mark.asyncio
    async def test_skill_with_guardrails(
        self, skill_def_with_guardrails, mock_vram_orchestrator, mock_prompt_composer, mock_container, mock_context
    ):
        """Test that guardrails are appended to system prompt."""
        skill = DeclarativeSkill(
            skill_def=skill_def_with_guardrails,
            vram_orchestrator=mock_vram_orchestrator,
            prompt_composer=mock_prompt_composer,
            container=mock_container,
        )

        with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat.return_value = {"message": {"content": "Response"}}
            mock_client_class.return_value = mock_client

            await skill.execute("Test", mock_context)

            system_prompt = mock_client.chat.call_args[1]["messages"][0]["content"]

            assert "<guardrails>" in system_prompt
            assert "Never do X" in system_prompt
            assert "Always do Y" in system_prompt
            assert "</guardrails>" in system_prompt

    @pytest.mark.asyncio
    async def test_skill_with_history(
        self, skill_def_with_history, mock_vram_orchestrator, mock_prompt_composer, mock_container
    ):
        """Test that conversation history is included."""
        context = ExecutionContext(
            user_id="test-user",
            session_id="test-session",
            interface="web",
            conversation_history=[
                Message(role="user", content="First message"),
                Message(role="assistant", content="First response"),
                Message(role="user", content="Second message"),
                Message(role="assistant", content="Second response"),
                Message(role="user", content="Third message"),
                Message(role="assistant", content="Third response"),
            ],
        )

        skill = DeclarativeSkill(
            skill_def=skill_def_with_history,
            vram_orchestrator=mock_vram_orchestrator,
            prompt_composer=mock_prompt_composer,
            container=mock_container,
        )

        with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat.return_value = {"message": {"content": "Response"}}
            mock_client_class.return_value = mock_client

            await skill.execute("Current query", context)

            messages = mock_client.chat.call_args[1]["messages"]

            # System + 3 history turns (6 messages) + user = 8 messages
            # history_turns=3 means last 3 messages from history
            assert len(messages) >= 4  # At minimum: system + some history + user

            # Current query should be last
            assert messages[-1]["role"] == "user"
            assert messages[-1]["content"] == "Current query"

    @pytest.mark.asyncio
    async def test_skill_with_user_prompt_template(
        self, skill_def_with_template, mock_vram_orchestrator, mock_prompt_composer, mock_container, mock_context
    ):
        """Test that user prompt template is applied."""
        skill = DeclarativeSkill(
            skill_def=skill_def_with_template,
            vram_orchestrator=mock_vram_orchestrator,
            prompt_composer=mock_prompt_composer,
            container=mock_container,
        )

        with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat.return_value = {"message": {"content": "Response"}}
            mock_client_class.return_value = mock_client

            await skill.execute("Raw input", mock_context)

            user_content = mock_client.chat.call_args[1]["messages"][-1]["content"]

            assert "Please process:" in user_content
            assert "Raw input" in user_content

    def test_skill_name_and_category(
        self, general_skill_def, mock_vram_orchestrator, mock_prompt_composer, mock_container
    ):
        """Test that name and category are exposed."""
        skill = DeclarativeSkill(
            skill_def=general_skill_def,
            vram_orchestrator=mock_vram_orchestrator,
            prompt_composer=mock_prompt_composer,
            container=mock_container,
        )

        assert skill.name == "test_skill"
        assert skill.category == "test"

    @pytest.mark.asyncio
    async def test_skill_metadata_includes_output_format(
        self, mock_vram_orchestrator, mock_prompt_composer, mock_container, mock_context
    ):
        """Test that output_format is included in metadata."""
        skill_def = DeclarativeSkillDef(
            name="json_skill",
            description="JSON output",
            use_when="Testing",
            category="test",
            system_prompt="Return JSON.",
            output_format="json",
        )

        skill = DeclarativeSkill(
            skill_def=skill_def,
            vram_orchestrator=mock_vram_orchestrator,
            prompt_composer=mock_prompt_composer,
            container=mock_container,
        )

        with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat.return_value = {"message": {"content": "Response"}}
            mock_client_class.return_value = mock_client

            result = await skill.execute("Test", mock_context)

            assert result.metadata["output_format"] == "json"
            assert result.metadata["declarative"] is True

    @pytest.mark.asyncio
    async def test_skill_without_user_profile(
        self, general_skill_def, mock_vram_orchestrator, mock_prompt_composer, mock_container
    ):
        """Test skill execution without user profile."""
        context = ExecutionContext(
            user_id="test-user",
            session_id="test-session",
            interface="api",
            user_profile=None,
        )

        skill = DeclarativeSkill(
            skill_def=general_skill_def,
            vram_orchestrator=mock_vram_orchestrator,
            prompt_composer=mock_prompt_composer,
            container=mock_container,
        )

        with patch("app.core.declarative_skill.ollama.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat.return_value = {"message": {"content": "Test skill response"}}
            mock_client_class.return_value = mock_client

            # Should not raise
            result = await skill.execute("Test input", context)

            assert result.content == "Test skill response"


class TestDeclarativeSkillMessageBuilding:
    """Tests for message building logic."""

    @pytest.fixture
    def mock_vram_orchestrator(self):
        return MockVRAMOrchestrator()

    @pytest.fixture
    def mock_container(self):
        container = Container()
        container.register(Config, MockConfig())
        return container

    @pytest.fixture
    def mock_prompt_composer(self):
        """Create mock prompt composer."""
        return MockPromptComposer()

    def test_build_system_prompt_with_context(
        self, mock_vram_orchestrator, mock_prompt_composer, mock_container
    ):
        """Test system prompt building with context injection."""
        skill_def = DeclarativeSkillDef(
            name="test",
            description="Test",
            use_when="Test",
            category="test",
            system_prompt="Hello {interface_context} and {personalization_context}",
        )

        skill = DeclarativeSkill(
            skill_def=skill_def,
            vram_orchestrator=mock_vram_orchestrator,
            prompt_composer=mock_prompt_composer,
            container=mock_container,
        )

        context = ExecutionContext(
            user_id="test",
            session_id="test",
            interface="discord",
            user_profile=UserProfile(
                user_id="test",
                communication_style="technical",
            ),
        )

        prompt = skill._build_system_prompt(context)

        # Should have replaced placeholders
        assert "{interface_context}" not in prompt
        assert "{personalization_context}" not in prompt

    def test_format_user_input_with_template(
        self, mock_vram_orchestrator, mock_prompt_composer, mock_container
    ):
        """Test user input formatting with template."""
        skill_def = DeclarativeSkillDef(
            name="test",
            description="Test",
            use_when="Test",
            category="test",
            system_prompt="System",
            user_prompt_template="PREFIX: {input} :SUFFIX",
        )

        skill = DeclarativeSkill(
            skill_def=skill_def,
            vram_orchestrator=mock_vram_orchestrator,
            prompt_composer=mock_prompt_composer,
            container=mock_container,
        )

        formatted = skill._format_user_input("my content")

        assert formatted == "PREFIX: my content :SUFFIX"

    def test_format_user_input_without_template(
        self, mock_vram_orchestrator, mock_prompt_composer, mock_container
    ):
        """Test user input formatting without template."""
        skill_def = DeclarativeSkillDef(
            name="test",
            description="Test",
            use_when="Test",
            category="test",
            system_prompt="System",
        )

        skill = DeclarativeSkill(
            skill_def=skill_def,
            vram_orchestrator=mock_vram_orchestrator,
            prompt_composer=mock_prompt_composer,
            container=mock_container,
        )

        formatted = skill._format_user_input("my content")

        assert formatted == "my content"
