"""Tests for the declarative skill loader."""
import pytest
from pathlib import Path
from textwrap import dedent
import tempfile
import os

from app.core.skill_loader import SkillLoader, DeclarativeSkillDef, SkillExample


class TestSkillLoader:
    """Tests for SkillLoader parsing skill.md files."""

    @pytest.fixture
    def skill_loader(self):
        """Create a skill loader instance."""
        return SkillLoader()

    @pytest.fixture
    def temp_skill_file(self, tmp_path):
        """Factory for creating temporary skill files."""
        def _create(content: str) -> Path:
            skill_path = tmp_path / "skill.md"
            skill_path.write_text(content)
            return skill_path
        return _create

    def test_load_skill_defaults(self, skill_loader, temp_skill_file):
        """Test loading a skill with minimal config uses defaults."""
        content = dedent("""
            ---
            name: extract
            description: Extract structured information from text
            use_when: User wants to pull out specific data
            category: extraction
            temperature: 0.1
            ---

            <system>
            You are a precise information extractor.

            {interface_context}

            {personalization_context}
            </system>
        """).strip()

        skill_path = temp_skill_file(content)
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert skill_def.name == "extract"
        assert skill_def.description == "Extract structured information from text"
        assert skill_def.use_when == "User wants to pull out specific data"
        assert skill_def.category == "extraction"
        assert skill_def.temperature == 0.1
        assert "precise information extractor" in skill_def.system_prompt
        assert "{interface_context}" in skill_def.system_prompt
        assert skill_def.examples == []
        assert skill_def.guardrails is None

    def test_load_skill_with_defaults(self, skill_loader, temp_skill_file):
        """Test that defaults are applied for missing config."""
        content = dedent("""
            ---
            name: basic
            description: Basic skill
            use_when: Testing
            category: test
            ---

            You are a basic assistant.
        """).strip()

        skill_path = temp_skill_file(content)
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert skill_def.temperature == 0.7  # default
        assert skill_def.max_tokens == 2048  # default
        assert skill_def.model_task == "general"  # default
        assert skill_def.include_history is False  # default
        assert skill_def.history_turns == 6  # default

    def test_load_skill_with_examples(self, skill_loader, temp_skill_file):
        """Test loading a skill with few-shot examples."""
        content = dedent("""
            ---
            name: analyze
            description: Analyze text
            use_when: User wants analysis
            category: reasoning
            ---

            <system>
            You are an analyst.
            </system>

            <examples>
            <example>
            <user>Analyze this argument.</user>
            <assistant>Here is my analysis...</assistant>
            </example>
            <example>
            <user>What about this claim?</user>
            <assistant>Let me break this down...</assistant>
            </example>
            </examples>
        """).strip()

        skill_path = temp_skill_file(content)
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert len(skill_def.examples) == 2
        assert skill_def.examples[0].user == "Analyze this argument."
        assert skill_def.examples[0].assistant == "Here is my analysis..."
        assert skill_def.examples[1].user == "What about this claim?"
        assert skill_def.examples[1].assistant == "Let me break this down..."

    def test_load_skill_with_guardrails(self, skill_loader, temp_skill_file):
        """Test loading a skill with guardrails."""
        content = dedent("""
            ---
            name: translate
            description: Translate text
            use_when: User wants translation
            category: text_processing
            ---

            <system>
            You are a translator.
            </system>

            <guardrails>
            - Never invent content
            - Flag idioms that don't translate
            - Maintain original meaning
            </guardrails>
        """).strip()

        skill_path = temp_skill_file(content)
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert skill_def.guardrails is not None
        assert "Never invent content" in skill_def.guardrails
        assert "Flag idioms" in skill_def.guardrails

    def test_load_skill_with_user_prompt_template(self, skill_loader, temp_skill_file):
        """Test loading a skill with custom user prompt template."""
        content = dedent("""
            ---
            name: summarize
            description: Summarize text
            use_when: User wants a summary
            category: text_processing

            user_prompt_template: |
              Please summarize the following text:

              {input}
            ---

            <system>
            You are a summarizer.
            </system>
        """).strip()

        skill_path = temp_skill_file(content)
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert skill_def.user_prompt_template is not None
        assert "Please summarize" in skill_def.user_prompt_template
        assert "{input}" in skill_def.user_prompt_template

    def test_load_skill_with_history(self, skill_loader, temp_skill_file):
        """Test loading a conversational skill with history enabled."""
        content = dedent("""
            ---
            name: chat
            description: General chat
            use_when: General conversation
            category: general

            include_history: true
            history_turns: 10
            ---

            <system>
            You are a helpful assistant.
            </system>
        """).strip()

        skill_path = temp_skill_file(content)
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert skill_def.include_history is True
        assert skill_def.history_turns == 10

    def test_load_skill_with_output_format(self, skill_loader, temp_skill_file):
        """Test loading a skill with output format specified."""
        content = dedent("""
            ---
            name: extract_json
            description: Extract to JSON
            use_when: User wants JSON output
            category: extraction
            output_format: json
            ---

            <system>
            Return valid JSON only.
            </system>
        """).strip()

        skill_path = temp_skill_file(content)
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert skill_def.output_format == "json"

    def test_load_skill_no_system_tag(self, skill_loader, temp_skill_file):
        """Test that body without <system> tag is used as system prompt."""
        content = dedent("""
            ---
            name: simple
            description: Simple skill
            use_when: Testing
            category: test
            ---

            You are a simple assistant. Help users with tasks.

            Guidelines:
            - Be helpful
            - Be concise
        """).strip()

        skill_path = temp_skill_file(content)
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert "simple assistant" in skill_def.system_prompt
        assert "Be helpful" in skill_def.system_prompt

    def test_load_skill_missing_required_field(self, skill_loader, temp_skill_file):
        """Test that missing required fields return None."""
        content = dedent("""
            ---
            name: incomplete
            description: Missing use_when
            category: test
            ---

            You are incomplete.
        """).strip()

        skill_path = temp_skill_file(content)
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is None

    def test_load_skill_no_frontmatter(self, skill_loader, temp_skill_file):
        """Test that file without frontmatter returns None."""
        content = "Just some text without frontmatter."

        skill_path = temp_skill_file(content)
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is None

    def test_load_skill_invalid_yaml(self, skill_loader, temp_skill_file):
        """Test that invalid YAML returns None."""
        content = dedent("""
            ---
            name: invalid
            description: [unclosed bracket
            ---

            System prompt
        """).strip()

        skill_path = temp_skill_file(content)
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is None

    def test_load_skill_source_path_stored(self, skill_loader, temp_skill_file):
        """Test that source path is stored in skill_def."""
        content = dedent("""
            ---
            name: tracked
            description: Track source
            use_when: Testing
            category: test
            ---

            System prompt.
        """).strip()

        skill_path = temp_skill_file(content)
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert skill_def.source_path == skill_path

    def test_split_frontmatter(self, skill_loader):
        """Test frontmatter splitting."""
        content = "---\nname: test\n---\nBody content"
        frontmatter, body = skill_loader._split_frontmatter(content)

        assert frontmatter == "name: test"
        assert body == "Body content"

    def test_split_frontmatter_no_closing(self, skill_loader):
        """Test frontmatter without closing delimiter."""
        content = "---\nname: test\nNo closing"
        frontmatter, body = skill_loader._split_frontmatter(content)

        assert frontmatter == ""
        assert body == "---\nname: test\nNo closing"

    def test_extract_tag(self, skill_loader):
        """Test XML tag extraction."""
        body = "<system>System content</system>\n<guardrails>Rules</guardrails>"

        system = skill_loader._extract_tag(body, "system")
        guardrails = skill_loader._extract_tag(body, "guardrails")
        missing = skill_loader._extract_tag(body, "examples")

        assert system == "System content"
        assert guardrails == "Rules"
        assert missing is None

    def test_parse_examples(self, skill_loader):
        """Test example parsing."""
        body = dedent("""
            <examples>
            <example>
            <user>Question 1</user>
            <assistant>Answer 1</assistant>
            </example>
            <example>
            <user>Question 2</user>
            <assistant>Answer 2</assistant>
            </example>
            </examples>
        """)

        examples = skill_loader._parse_examples(body)

        assert len(examples) == 2
        assert examples[0].user == "Question 1"
        assert examples[0].assistant == "Answer 1"
        assert examples[1].user == "Question 2"
        assert examples[1].assistant == "Answer 2"

    def test_parse_examples_incomplete(self, skill_loader):
        """Test that incomplete examples are skipped."""
        body = dedent("""
            <examples>
            <example>
            <user>Has user only</user>
            </example>
            <example>
            <user>Complete example</user>
            <assistant>Has both</assistant>
            </example>
            </examples>
        """)

        examples = skill_loader._parse_examples(body)

        assert len(examples) == 1
        assert examples[0].user == "Complete example"


class TestDeclarativeSkillDef:
    """Tests for DeclarativeSkillDef dataclass."""

    def test_dataclass_defaults(self):
        """Test default values for DeclarativeSkillDef."""
        skill_def = DeclarativeSkillDef(
            name="test",
            description="Test skill",
            use_when="Testing",
            category="test",
            system_prompt="You are a test.",
        )

        assert skill_def.temperature == 0.7
        assert skill_def.max_tokens == 2048
        assert skill_def.model_task == "general"
        assert skill_def.output_format is None
        assert skill_def.user_prompt_template is None
        assert skill_def.include_history is False
        assert skill_def.history_turns == 6
        assert skill_def.examples == []
        assert skill_def.guardrails is None
        assert skill_def.source_path is None


class TestSkillExample:
    """Tests for SkillExample dataclass."""

    def test_skill_example(self):
        """Test SkillExample creation."""
        example = SkillExample(
            user="What is Python?",
            assistant="Python is a programming language.",
        )

        assert example.user == "What is Python?"
        assert example.assistant == "Python is a programming language."


class TestSkillLoaderNewFormat:
    """Tests for SkillLoader parsing SKILL.md (Claude format) files."""

    @pytest.fixture
    def skill_loader(self):
        """Create a skill loader instance."""
        return SkillLoader()

    @pytest.fixture
    def temp_skill_dir(self, tmp_path):
        """Factory for creating temporary skill directories with SKILL.md."""
        def _create(content: str, category: str = "general", name: str = "test_skill") -> Path:
            # Create path: tmp_path/skills/<category>/<name>/SKILL.md
            skill_dir = tmp_path / "skills" / category / name
            skill_dir.mkdir(parents=True)
            skill_path = skill_dir / "SKILL.md"
            skill_path.write_text(content)
            return skill_path
        return _create

    def test_load_new_format_simple(self, skill_loader, temp_skill_dir):
        """Test loading a simple SKILL.md with Claude format."""
        content = dedent("""
            ---
            name: chat
            description: General conversational AI assistant. Use when user wants to chat or have a conversation.
            ---

            # Chat

            You are a helpful AI assistant. Respond naturally and helpfully.

            {interface_context}

            {personalization_context}

            ## Guidelines
            - Be helpful and accurate
            - Be concise

            ## Configuration

            ```yaml
            temperature: 0.7
            max_tokens: 2048
            model_task: general
            include_history: true
            history_turns: 6
            ```
        """).strip()

        skill_path = temp_skill_dir(content, category="general", name="chat")
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert skill_def.name == "chat"
        assert "conversational AI assistant" in skill_def.description
        assert skill_def.category == "general"
        assert skill_def.temperature == 0.7
        assert skill_def.max_tokens == 2048
        assert skill_def.model_task == "general"
        assert skill_def.include_history is True
        assert skill_def.history_turns == 6
        assert "helpful AI assistant" in skill_def.system_prompt
        assert "{interface_context}" in skill_def.system_prompt
        # Configuration section should be excluded from system prompt
        assert "```yaml" not in skill_def.system_prompt

    def test_load_new_format_extracts_use_when(self, skill_loader, temp_skill_dir):
        """Test that use_when is extracted from description."""
        content = dedent("""
            ---
            name: brainstorm
            description: Generate creative ideas. Use when user wants to brainstorm or ideate.
            ---

            # Brainstorm

            You are a creative brainstorming partner.
        """).strip()

        skill_path = temp_skill_dir(content, category="think", name="brainstorm")
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert skill_def.use_when == "user wants to brainstorm or ideate"

    def test_load_new_format_category_from_path(self, skill_loader, temp_skill_dir):
        """Test that category is derived from directory path."""
        content = dedent("""
            ---
            name: analyze
            description: Analyze content.
            ---

            # Analyze

            You analyze content.
        """).strip()

        # Create in analyze category
        skill_path = temp_skill_dir(content, category="analyze", name="analyze")
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert skill_def.category == "analyze"

    def test_load_new_format_with_examples(self, skill_loader, temp_skill_dir):
        """Test loading SKILL.md with examples section."""
        content = dedent("""
            ---
            name: summarize
            description: Summarize text. Use when user wants a summary.
            ---

            # Summarize

            You summarize text concisely.

            ## Examples

            <examples>
            <example>
            <user>Summarize this article about AI.</user>
            <assistant>This article discusses recent AI developments...</assistant>
            </example>
            </examples>
        """).strip()

        skill_path = temp_skill_dir(content, category="general", name="summarize")
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert len(skill_def.examples) == 1
        assert skill_def.examples[0].user == "Summarize this article about AI."
        # Examples section should be excluded from system prompt
        assert "<examples>" not in skill_def.system_prompt

    def test_load_new_format_with_guardrails(self, skill_loader, temp_skill_dir):
        """Test loading SKILL.md with guardrails section."""
        content = dedent("""
            ---
            name: translate
            description: Translate text. Use when user wants translation.
            ---

            # Translate

            You are a translator.

            ## Guardrails

            <guardrails>
            - Never invent content
            - Preserve original meaning
            </guardrails>
        """).strip()

        skill_path = temp_skill_dir(content, category="general", name="translate")
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert skill_def.guardrails is not None
        assert "Never invent content" in skill_def.guardrails
        # Guardrails section should be excluded from system prompt
        assert "<guardrails>" not in skill_def.system_prompt

    def test_load_new_format_with_references(self, skill_loader, tmp_path):
        """Test loading SKILL.md with references directory."""
        # Create skill directory structure
        skill_dir = tmp_path / "skills" / "general" / "brand"
        skill_dir.mkdir(parents=True)

        # Create references directory
        refs_dir = skill_dir / "references"
        refs_dir.mkdir()
        (refs_dir / "colors.md").write_text("# Brand Colors\n\nPrimary: #FF0000")
        (refs_dir / "guidelines.txt").write_text("Always use brand voice.")

        # Create SKILL.md
        content = dedent("""
            ---
            name: brand
            description: Apply brand guidelines. Use when brand styling needed.
            ---

            # Brand Guidelines

            Apply brand guidelines to content.
        """).strip()
        (skill_dir / "SKILL.md").write_text(content)

        skill_path = skill_dir / "SKILL.md"
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert skill_def.references_dir == refs_dir
        assert len(skill_def.references_content) == 2
        assert "colors.md" in skill_def.references_content
        assert "guidelines.txt" in skill_def.references_content
        assert "Brand Colors" in skill_def.references_content["colors.md"]
        assert "brand voice" in skill_def.references_content["guidelines.txt"]

    def test_load_new_format_with_scripts(self, skill_loader, tmp_path):
        """Test that scripts directory is detected."""
        # Create skill directory structure
        skill_dir = tmp_path / "skills" / "general" / "code"
        skill_dir.mkdir(parents=True)

        # Create scripts directory
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "format.py").write_text("# formatting script")

        # Create SKILL.md
        content = dedent("""
            ---
            name: code
            description: Code assistance.
            ---

            # Code

            Help with code.
        """).strip()
        (skill_dir / "SKILL.md").write_text(content)

        skill_path = skill_dir / "SKILL.md"
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert skill_def.scripts_dir == scripts_dir

    def test_load_new_format_no_config_block(self, skill_loader, temp_skill_dir):
        """Test loading SKILL.md without config block uses defaults."""
        content = dedent("""
            ---
            name: simple
            description: Simple skill.
            ---

            # Simple

            You are a simple assistant.
        """).strip()

        skill_path = temp_skill_dir(content, category="general", name="simple")
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is not None
        assert skill_def.temperature == 0.7  # default
        assert skill_def.max_tokens == 2048  # default
        assert skill_def.model_task == "general"  # default

    def test_load_new_format_missing_name(self, skill_loader, temp_skill_dir):
        """Test that missing name in SKILL.md returns None."""
        content = dedent("""
            ---
            description: Missing name
            ---

            # Missing Name

            System prompt.
        """).strip()

        skill_path = temp_skill_dir(content)
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is None

    def test_load_new_format_missing_description(self, skill_loader, temp_skill_dir):
        """Test that missing description in SKILL.md returns None."""
        content = dedent("""
            ---
            name: nodesc
            ---

            # No Description

            System prompt.
        """).strip()

        skill_path = temp_skill_dir(content)
        skill_def = skill_loader.load_skill(skill_path)

        assert skill_def is None

    def test_extract_use_when_patterns(self, skill_loader):
        """Test various use_when extraction patterns."""
        # Pattern: "Use when..."
        desc1 = "Generate creative ideas. Use when user wants to brainstorm."
        assert skill_loader._extract_use_when(desc1) == "user wants to brainstorm"

        # Pattern: "Use this when..."
        desc2 = "Summarize content. Use this when user needs a summary."
        assert skill_loader._extract_use_when(desc2) == "user needs a summary"

        # No pattern - returns full description
        desc3 = "Just a description without trigger"
        assert skill_loader._extract_use_when(desc3) == "Just a description without trigger"

    def test_extract_yaml_config(self, skill_loader):
        """Test YAML config block extraction."""
        body = dedent("""
            # Title

            Some text.

            ## Configuration

            ```yaml
            temperature: 0.9
            max_tokens: 4096
            model_task: research
            ```

            More text.
        """)

        config = skill_loader._extract_yaml_config(body)

        assert config["temperature"] == 0.9
        assert config["max_tokens"] == 4096
        assert config["model_task"] == "research"

    def test_extract_yaml_config_empty(self, skill_loader):
        """Test extraction returns empty dict when no config block."""
        body = "# Title\n\nJust text, no config."
        config = skill_loader._extract_yaml_config(body)
        assert config == {}

    def test_extract_system_prompt_excludes_sections(self, skill_loader):
        """Test that special sections are excluded from system prompt."""
        body = dedent("""
            # Title

            Main system prompt content.

            ## Guidelines
            - Be helpful

            ## Configuration

            ```yaml
            temperature: 0.7
            ```

            ## Examples

            <examples>
            <example>
            <user>Test</user>
            <assistant>Response</assistant>
            </example>
            </examples>

            ## Guardrails

            <guardrails>
            - Rule 1
            </guardrails>
        """)

        prompt = skill_loader._extract_system_prompt(body)

        assert "Main system prompt content" in prompt
        assert "Be helpful" in prompt
        assert "```yaml" not in prompt
        assert "temperature: 0.7" not in prompt
        assert "<examples>" not in prompt
        assert "<guardrails>" not in prompt

    def test_extract_category_from_path(self, skill_loader, tmp_path):
        """Test category extraction from various path structures."""
        # Standard: skills/<category>/<skill>/SKILL.md
        path1 = tmp_path / "skills" / "think" / "brainstorm" / "SKILL.md"
        path1.parent.mkdir(parents=True)
        assert skill_loader._extract_category_from_path(path1) == "think"

        # Fallback to general for non-standard paths
        path2 = tmp_path / "random" / "skill" / "SKILL.md"
        path2.parent.mkdir(parents=True)
        assert skill_loader._extract_category_from_path(path2) == "general"

    def test_load_references_empty_dir(self, skill_loader, tmp_path):
        """Test loading references from empty or non-existent directory."""
        # Non-existent
        refs = skill_loader._load_references(tmp_path / "nonexistent")
        assert refs == {}

        # Empty directory
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        refs = skill_loader._load_references(empty_dir)
        assert refs == {}

    def test_new_format_dataclass_has_reference_fields(self):
        """Test that DeclarativeSkillDef has new reference fields."""
        skill_def = DeclarativeSkillDef(
            name="test",
            description="Test skill",
            use_when="Testing",
            category="test",
            system_prompt="You are a test.",
            references_content={"test.md": "Reference content"},
        )

        assert skill_def.references_dir is None  # default
        assert skill_def.scripts_dir is None  # default
        assert skill_def.references_content == {"test.md": "Reference content"}
