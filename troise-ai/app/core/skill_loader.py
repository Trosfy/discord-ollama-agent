"""Skill loader for declarative markdown-based skills.

Parses SKILL.md (Claude format) and skill.md (legacy format) files.
Supports references/ and scripts/ directories for SKILL.md format.
"""
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class SkillExample:
    """A single few-shot example for a skill."""

    user: str
    assistant: str


@dataclass
class DeclarativeSkillDef:
    """Parsed skill definition from SKILL.md or skill.md.

    Contains all metadata, configuration, and prompt content
    needed to execute a declarative skill.

    Supports two formats:
    - SKILL.md (Claude format): Minimal frontmatter, config in ```yaml block
    - skill.md (legacy format): Full config in frontmatter, XML-tagged sections
    """

    # Required metadata (from YAML frontmatter)
    name: str
    description: str
    use_when: str
    category: str

    # Parsed body sections
    system_prompt: str  # Content of <system> tag or markdown body
    examples: List[SkillExample] = field(default_factory=list)  # From <examples>
    guardrails: Optional[str] = None  # Content of <guardrails>

    # Config with defaults (from YAML frontmatter or ```yaml block)
    temperature: float = 0.7
    max_tokens: int = 2048
    model_task: str = "general"
    output_format: Optional[str] = None  # "json", "markdown", etc.

    # Optional features (from YAML frontmatter or ```yaml block)
    user_prompt_template: Optional[str] = None
    include_history: bool = False
    history_turns: int = 6

    # Routing control
    routable: bool = True  # If False, skill is excluded from routing table (internal use only)

    # Source tracking
    source_path: Optional[Path] = None

    # References support (SKILL.md format)
    references_dir: Optional[Path] = None  # Path to references/ directory
    scripts_dir: Optional[Path] = None  # Path to scripts/ directory
    references_content: Dict[str, str] = field(default_factory=dict)  # Loaded reference files


class SkillLoader:
    """Parse SKILL.md and skill.md files into DeclarativeSkillDef objects.

    Supports two formats:

    **SKILL.md (Claude format):**
    ```markdown
    ---
    name: skill_name
    description: What the skill does. Use when [trigger conditions].
    ---

    # Skill Title

    System prompt content here with {interface_context} and {personalization_context}

    ## Configuration

    ```yaml
    temperature: 0.7
    max_tokens: 2048
    model_task: general
    ```

    ## Examples

    <examples>
    <example>
    <user>Example user input</user>
    <assistant>Example response</assistant>
    </example>
    </examples>
    ```

    **skill.md (legacy format):**
    ```markdown
    ---
    name: skill_name
    description: What the skill does
    use_when: When to use this skill
    category: skill_category
    temperature: 0.7
    max_tokens: 2048
    ---

    <system>
    System prompt content
    </system>
    ```
    """

    def load_skill(self, path: Path) -> Optional[DeclarativeSkillDef]:
        """Parse skill file (SKILL.md or skill.md).

        Args:
            path: Path to the skill file.

        Returns:
            DeclarativeSkillDef if parsing succeeds, None otherwise.
        """
        is_new_format = path.name == "SKILL.md"

        if is_new_format:
            return self._load_new_format(path)
        else:
            return self._load_legacy_format(path)

    def _load_new_format(self, path: Path) -> Optional[DeclarativeSkillDef]:
        """Parse SKILL.md (Claude format) file.

        Args:
            path: Path to the SKILL.md file.

        Returns:
            DeclarativeSkillDef if parsing succeeds, None otherwise.
        """
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read skill file {path}: {e}")
            return None

        # Split YAML frontmatter from body
        frontmatter, body = self._split_frontmatter(content)
        if not frontmatter:
            logger.error(f"No frontmatter found in {path}")
            return None

        # Parse YAML frontmatter (minimal: name, description)
        try:
            meta = yaml.safe_load(frontmatter)
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in {path}: {e}")
            return None

        # Validate required fields for new format
        if "name" not in meta:
            logger.error(f"Missing required field 'name' in {path}")
            return None
        if "description" not in meta:
            logger.error(f"Missing required field 'description' in {path}")
            return None

        # Extract use_when from description or use description as use_when
        description = meta["description"]
        use_when = self._extract_use_when(description)

        # Derive category from directory path
        category = self._extract_category_from_path(path)

        # Extract config from ```yaml code block in body
        config = self._extract_yaml_config(body)

        # Extract system prompt (markdown body, excluding special sections)
        system_prompt = self._extract_system_prompt(body)

        # Parse examples and guardrails (same XML format)
        examples = self._parse_examples(body)
        guardrails = self._extract_tag(body, "guardrails")

        # Load references if directory exists
        skill_dir = path.parent
        references_dir = skill_dir / "references"
        scripts_dir = skill_dir / "scripts"
        references_content = self._load_references(references_dir)

        skill_def = DeclarativeSkillDef(
            name=meta["name"],
            description=description,
            use_when=use_when,
            category=category,
            system_prompt=system_prompt,
            examples=examples,
            guardrails=guardrails,
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 2048),
            model_task=config.get("model_task", "general"),
            output_format=config.get("output_format"),
            user_prompt_template=config.get("user_prompt_template"),
            include_history=config.get("include_history", False),
            history_turns=config.get("history_turns", 6),
            routable=config.get("routable", True),
            source_path=path,
            references_dir=references_dir if references_dir.exists() else None,
            scripts_dir=scripts_dir if scripts_dir.exists() else None,
            references_content=references_content,
        )

        logger.debug(f"Loaded SKILL.md '{skill_def.name}' from {path}")
        return skill_def

    def _load_legacy_format(self, path: Path) -> Optional[DeclarativeSkillDef]:
        """Parse skill.md (legacy format) file.

        Args:
            path: Path to the skill.md file.

        Returns:
            DeclarativeSkillDef if parsing succeeds, None otherwise.
        """
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read skill file {path}: {e}")
            return None

        # Split YAML frontmatter from body
        frontmatter, body = self._split_frontmatter(content)
        if not frontmatter:
            logger.error(f"No frontmatter found in {path}")
            return None

        # Parse YAML
        try:
            meta = yaml.safe_load(frontmatter)
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in {path}: {e}")
            return None

        # Validate required fields
        required_fields = ["name", "description", "use_when", "category"]
        for field_name in required_fields:
            if field_name not in meta:
                logger.error(f"Missing required field '{field_name}' in {path}")
                return None

        # Parse XML-style sections from body
        system_prompt = self._extract_tag(body, "system")
        if not system_prompt:
            # If no <system> tag, use entire body as system prompt
            system_prompt = body.strip()

        examples = self._parse_examples(body)
        guardrails = self._extract_tag(body, "guardrails")

        skill_def = DeclarativeSkillDef(
            name=meta["name"],
            description=meta["description"],
            use_when=meta["use_when"],
            category=meta["category"],
            system_prompt=system_prompt,
            examples=examples,
            guardrails=guardrails,
            temperature=meta.get("temperature", 0.7),
            max_tokens=meta.get("max_tokens", 2048),
            model_task=meta.get("model_task", "general"),
            output_format=meta.get("output_format"),
            user_prompt_template=meta.get("user_prompt_template"),
            include_history=meta.get("include_history", False),
            history_turns=meta.get("history_turns", 6),
            routable=meta.get("routable", True),
            source_path=path,
        )

        logger.debug(f"Loaded legacy skill '{skill_def.name}' from {path}")
        return skill_def

    def _split_frontmatter(self, content: str) -> tuple[str, str]:
        """Split YAML frontmatter from markdown body.

        Args:
            content: Full file content.

        Returns:
            Tuple of (frontmatter, body). Empty frontmatter if not found.
        """
        if not content.startswith("---"):
            return "", content

        # Find the closing ---
        parts = content.split("---", 2)
        if len(parts) < 3:
            return "", content

        return parts[1].strip(), parts[2].strip()

    def _extract_tag(self, body: str, tag: str) -> Optional[str]:
        """Extract content between <tag> and </tag>.

        Args:
            body: Text to search in.
            tag: Tag name (without angle brackets).

        Returns:
            Content between tags, or None if not found.
        """
        pattern = rf"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, body, re.DOTALL)
        return match.group(1).strip() if match else None

    def _parse_examples(self, body: str) -> List[SkillExample]:
        """Parse <examples> section into SkillExample list.

        Args:
            body: Text to search in.

        Returns:
            List of SkillExample objects.
        """
        examples_content = self._extract_tag(body, "examples")
        if not examples_content:
            return []

        examples = []

        # Find each <example>...</example> block
        for match in re.finditer(
            r"<example>(.*?)</example>", examples_content, re.DOTALL
        ):
            example_text = match.group(1)
            user = self._extract_tag(example_text, "user")
            assistant = self._extract_tag(example_text, "assistant")

            if user and assistant:
                examples.append(SkillExample(user=user, assistant=assistant))
            else:
                logger.warning(
                    f"Incomplete example found (missing user or assistant): {example_text[:50]}..."
                )

        return examples

    # ==================== New Format Helpers ====================

    def _extract_use_when(self, description: str) -> str:
        """Extract use_when trigger from description.

        In Claude format, use_when is embedded in description like:
        "What the skill does. Use when [trigger conditions]."

        Args:
            description: The full description text.

        Returns:
            Extracted use_when text, or the full description if not found.
        """
        # Look for patterns like "Use when...", "Use this when...", etc.
        patterns = [
            r"[.]\s*Use when\s+(.+?)(?:\.|$)",
            r"[.]\s*Use this when\s+(.+?)(?:\.|$)",
            r"[.]\s*Trigger when\s+(.+?)(?:\.|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()

        # If no pattern found, use the description itself as use_when
        return description

    def _extract_category_from_path(self, path: Path) -> str:
        """Derive category from the skill's directory path.

        Path structure: .../skills/<category>/<skill_name>/SKILL.md
        Example: .../skills/general/chat/SKILL.md -> "general"

        Args:
            path: Path to the SKILL.md file.

        Returns:
            Category name derived from path, or "general" as default.
        """
        try:
            # Path: .../skills/<category>/<skill_name>/SKILL.md
            # parent: .../skills/<category>/<skill_name>
            # parent.parent: .../skills/<category>
            skill_dir = path.parent  # skill directory
            category_dir = skill_dir.parent  # category directory

            # Ensure we're in a skills directory structure
            if category_dir.parent.name == "skills":
                return category_dir.name

            # Fallback: check if parent is named 'skills'
            if skill_dir.parent.name == "skills":
                return skill_dir.name

            return "general"
        except Exception:
            return "general"

    def _extract_yaml_config(self, body: str) -> Dict[str, Any]:
        """Extract configuration from ```yaml code block in body.

        Args:
            body: Markdown body text.

        Returns:
            Dictionary of config values, empty dict if not found.
        """
        # Match ```yaml ... ``` code block
        pattern = r"```yaml\s*\n(.*?)\n```"
        match = re.search(pattern, body, re.DOTALL)

        if not match:
            return {}

        try:
            config = yaml.safe_load(match.group(1))
            return config if isinstance(config, dict) else {}
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse YAML config block: {e}")
            return {}

    def _extract_system_prompt(self, body: str) -> str:
        """Extract system prompt from markdown body.

        The system prompt is the markdown content after the title,
        excluding special sections like ## Configuration, ## Examples,
        ## Guardrails, and code blocks.

        Args:
            body: Markdown body text.

        Returns:
            Cleaned system prompt text.
        """
        lines = body.split("\n")
        result_lines = []
        skip_section = False
        in_code_block = False
        skip_sections = {"configuration", "examples", "guardrails"}

        for line in lines:
            # Track code blocks
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                # Skip the entire code block
                if in_code_block:
                    continue
                else:
                    continue

            if in_code_block:
                continue

            # Check for section headers
            if line.startswith("## "):
                section_name = line[3:].strip().lower()
                skip_section = section_name in skip_sections
                if skip_section:
                    continue

            # Skip content in excluded sections
            if skip_section:
                # Check if we've hit a new section
                if line.startswith("## "):
                    section_name = line[3:].strip().lower()
                    skip_section = section_name in skip_sections
                    if not skip_section:
                        result_lines.append(line)
                continue

            # Skip XML-style tags
            if re.match(r"^\s*<(examples|guardrails|example|user|assistant)>", line):
                continue
            if re.match(r"^\s*</(examples|guardrails|example|user|assistant)>", line):
                continue

            result_lines.append(line)

        # Clean up the result
        prompt = "\n".join(result_lines).strip()

        # Remove the title line if it starts with #
        if prompt.startswith("# "):
            lines = prompt.split("\n", 1)
            prompt = lines[1].strip() if len(lines) > 1 else ""

        return prompt

    def _load_references(self, references_dir: Path) -> Dict[str, str]:
        """Load all reference files from references/ directory.

        Args:
            references_dir: Path to the references/ directory.

        Returns:
            Dictionary mapping filename to file content.
        """
        if not references_dir.exists():
            return {}

        references = {}
        try:
            for file_path in references_dir.iterdir():
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        references[file_path.name] = content
                        logger.debug(f"Loaded reference file: {file_path.name}")
                    except Exception as e:
                        logger.warning(f"Failed to read reference file {file_path}: {e}")
        except Exception as e:
            logger.warning(f"Failed to iterate references directory {references_dir}: {e}")

        return references
