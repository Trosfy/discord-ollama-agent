"""Skill Gateway Tool - Access skill instructions on demand.

This tool provides two functions:
1. list_skills() - Get a table of contents of all available skills
2. use_skill(name) - Get detailed instructions for a specific skill

This implements the "guidebook" pattern where skills are chapters
that the agent can read on demand for specialized instructions.
"""
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.context import ExecutionContext
from app.core.container import Container
from app.core.interfaces.tool import ToolResult

logger = logging.getLogger(__name__)

# Skills directory
SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"


def _parse_skill_frontmatter(content: str) -> tuple[Dict[str, str], str]:
    """Parse YAML frontmatter from skill markdown.

    Args:
        content: Raw SKILL.md content.

    Returns:
        Tuple of (frontmatter_dict, body_content).
    """
    frontmatter = {}
    body = content

    if content.startswith("---"):
        # Find end of frontmatter
        end_idx = content.find("---", 3)
        if end_idx > 0:
            fm_content = content[3:end_idx].strip()
            body = content[end_idx + 3:].strip()

            # Simple YAML parsing for key: value pairs
            for line in fm_content.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip()

    return frontmatter, body


def _discover_skills() -> Dict[str, Dict[str, Any]]:
    """Discover all skills from the skills directory.

    Returns:
        Dict mapping skill name to skill info (path, category, description).
    """
    skills = {}

    if not SKILLS_DIR.exists():
        logger.warning(f"Skills directory not found: {SKILLS_DIR}")
        return skills

    # Find all SKILL.md files
    for skill_file in SKILLS_DIR.rglob("SKILL.md"):
        try:
            content = skill_file.read_text()
            frontmatter, _ = _parse_skill_frontmatter(content)

            name = frontmatter.get("name", skill_file.parent.name)
            description = frontmatter.get("description", "No description")

            # Get category from directory structure
            rel_path = skill_file.relative_to(SKILLS_DIR)
            parts = list(rel_path.parts)[:-2]  # Remove skill_name/SKILL.md
            category = parts[0] if parts else "general"

            skills[name] = {
                "path": str(skill_file),
                "category": category,
                "description": description,
            }

        except Exception as e:
            logger.warning(f"Failed to parse skill {skill_file}: {e}")

    return skills


class SkillGatewayTool:
    """
    Tool for accessing skill instructions on demand.

    Implements the "guidebook" pattern:
    - list_skills: Table of contents
    - use_skill: Read a specific chapter

    This allows the agent to dynamically load specialized instructions
    without bloating the base system prompt.
    """

    name = "skill_gateway"
    description = """Access specialized skill instructions.

Use this tool when you need specific guidance for tasks like:
- Drafting emails, blog posts, or tweets
- Analyzing documents or extracting information
- Project management (status, blockers, next actions)
- Creating diagrams, mockups, or image prompts
- And many more specialized tasks

Functions:
- list_skills: See what skills are available
- use_skill: Get detailed instructions for a skill"""

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_skills", "use_skill"],
                "description": "Action to perform"
            },
            "skill_name": {
                "type": "string",
                "description": "Name of skill to use (required for use_skill action)"
            },
        },
        "required": ["action"]
    }

    def __init__(
        self,
        context: ExecutionContext,
        container: Container,
    ):
        """
        Initialize the skill gateway tool.

        Args:
            context: Execution context.
            container: DI container for service resolution.
        """
        self._context = context
        self._container = container
        self._skills_cache: Optional[Dict[str, Dict[str, Any]]] = None

    def _get_skills(self) -> Dict[str, Dict[str, Any]]:
        """Get skills, using cache if available."""
        if self._skills_cache is None:
            self._skills_cache = _discover_skills()
        return self._skills_cache

    def _list_skills(self) -> str:
        """Generate table of contents for all skills.

        Returns:
            Formatted string with skill categories and descriptions.
        """
        skills = self._get_skills()

        if not skills:
            return "No skills available."

        # Group by category
        by_category: Dict[str, List[tuple[str, str]]] = {}
        for name, info in skills.items():
            category = info["category"]
            if category not in by_category:
                by_category[category] = []
            by_category[category].append((name, info["description"]))

        # Format output
        lines = ["# Available Skills\n"]

        for category in sorted(by_category.keys()):
            lines.append(f"\n## {category.title()}\n")
            for name, desc in sorted(by_category[category]):
                # Truncate description for table of contents
                short_desc = desc[:80] + "..." if len(desc) > 80 else desc
                lines.append(f"- **{name}**: {short_desc}")

        lines.append("\n\nUse `use_skill` with the skill name to get detailed instructions.")

        return "\n".join(lines)

    def _use_skill(self, skill_name: str) -> str:
        """Get full instructions for a specific skill.

        Args:
            skill_name: Name of the skill.

        Returns:
            Full skill instructions or error message.
        """
        skills = self._get_skills()

        if skill_name not in skills:
            available = ", ".join(sorted(skills.keys()))
            return f"Skill '{skill_name}' not found. Available skills: {available}"

        skill_info = skills[skill_name]
        skill_path = Path(skill_info["path"])

        try:
            content = skill_path.read_text()
            _, body = _parse_skill_frontmatter(content)

            return f"# Skill: {skill_name}\n\n{body}"

        except Exception as e:
            logger.error(f"Failed to read skill {skill_name}: {e}")
            return f"Error loading skill '{skill_name}': {e}"

    async def execute(
        self,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Execute skill gateway action.

        Args:
            params: Tool parameters (action, skill_name).
            context: Execution context.

        Returns:
            ToolResult with skill information.
        """
        action = params.get("action", "")
        skill_name = params.get("skill_name", "")

        if action == "list_skills":
            result = self._list_skills()
            return ToolResult(
                content=result,
                success=True,
            )

        elif action == "use_skill":
            if not skill_name:
                return ToolResult(
                    content="Error: skill_name is required for use_skill action",
                    success=False,
                    error="skill_name required"
                )

            result = self._use_skill(skill_name)
            return ToolResult(
                content=result,
                success=True,
            )

        else:
            return ToolResult(
                content=f"Unknown action: {action}. Use 'list_skills' or 'use_skill'.",
                success=False,
                error=f"Unknown action: {action}"
            )

    def to_schema(self) -> Dict[str, Any]:
        """Return tool schema for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


def create_skill_gateway_tool(
    context: ExecutionContext,
    container: Container,
) -> SkillGatewayTool:
    """
    Factory function to create skill_gateway tool.

    Args:
        context: Execution context.
        container: DI container for service resolution.

    Returns:
        Configured SkillGatewayTool instance.
    """
    return SkillGatewayTool(
        context=context,
        container=container,
    )
