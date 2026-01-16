"""AI Preferences Adapter - reads/writes ai-preferences.yaml.

The preferences file is user-editable and defines explicit preferences:
- Communication style (terse, balanced, detailed, socratic)
- Response length (brief, adaptive, thorough)
- Expertise areas (skip basic explanations)
- Interests (proactive mentions)
- Current context (project, role, company)
- Formatting preferences

Location: {vault}/00-meta/ai-preferences.yaml
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .vault_service import VaultService, NoteNotFoundError

logger = logging.getLogger(__name__)


# Default preferences file path within vault
PREFERENCES_PATH = "00-meta/ai-preferences.yaml"


@dataclass
class CommunicationPreferences:
    """User's communication preferences."""
    style: str = "balanced"           # terse | balanced | detailed | socratic
    response_length: str = "adaptive"  # brief | adaptive | thorough
    use_emoji: bool = False
    formality: str = "casual"          # casual | professional | academic


@dataclass
class FormattingPreferences:
    """Code and content formatting preferences."""
    code_style: str = "functional"     # imperative | functional | declarative
    prefer_examples: bool = True
    max_code_length: int = 50          # Lines before splitting


@dataclass
class ContextInfo:
    """Current user context."""
    current_project: Optional[str] = None
    role: Optional[str] = None
    company: Optional[str] = None


@dataclass
class UserPreferences:
    """Complete user preferences from ai-preferences.yaml."""
    communication: CommunicationPreferences = field(default_factory=CommunicationPreferences)
    expertise: List[str] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)
    context: ContextInfo = field(default_factory=ContextInfo)
    formatting: FormattingPreferences = field(default_factory=FormattingPreferences)
    custom: Dict[str, Any] = field(default_factory=dict)  # User-defined extras

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "communication": {
                "style": self.communication.style,
                "response_length": self.communication.response_length,
                "use_emoji": self.communication.use_emoji,
                "formality": self.communication.formality,
            },
            "expertise": self.expertise,
            "interests": self.interests,
            "context": {
                "current_project": self.context.current_project,
                "role": self.context.role,
                "company": self.context.company,
            },
            "formatting": {
                "code_style": self.formatting.code_style,
                "prefer_examples": self.formatting.prefer_examples,
                "max_code_length": self.formatting.max_code_length,
            },
            **self.custom,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserPreferences":
        """Create from dictionary (YAML data)."""
        # Extract known sections
        comm_data = data.get("communication", {})
        fmt_data = data.get("formatting", {})
        ctx_data = data.get("context", {})

        # Build nested dataclasses
        communication = CommunicationPreferences(
            style=comm_data.get("style", "balanced"),
            response_length=comm_data.get("response_length", "adaptive"),
            use_emoji=comm_data.get("use_emoji", False),
            formality=comm_data.get("formality", "casual"),
        )

        formatting = FormattingPreferences(
            code_style=fmt_data.get("code_style", "functional"),
            prefer_examples=fmt_data.get("prefer_examples", True),
            max_code_length=fmt_data.get("max_code_length", 50),
        )

        context = ContextInfo(
            current_project=ctx_data.get("current_project"),
            role=ctx_data.get("role"),
            company=ctx_data.get("company"),
        )

        # Collect any custom fields not in the known sections
        known_keys = {"communication", "expertise", "interests", "context", "formatting"}
        custom = {k: v for k, v in data.items() if k not in known_keys}

        return cls(
            communication=communication,
            expertise=data.get("expertise", []),
            interests=data.get("interests", []),
            context=context,
            formatting=formatting,
            custom=custom,
        )

    def get_expertise_prompt(self) -> str:
        """Get prompt text describing user expertise."""
        if not self.expertise:
            return ""
        return f"User has expertise in: {', '.join(self.expertise)}. Skip basic explanations in these areas."

    def get_interests_prompt(self) -> str:
        """Get prompt text describing user interests."""
        if not self.interests:
            return ""
        return f"User is interested in: {', '.join(self.interests)}."

    def get_context_prompt(self) -> str:
        """Get prompt text describing current context."""
        parts = []
        if self.context.current_project:
            parts.append(f"Currently working on: {self.context.current_project}")
        if self.context.role:
            parts.append(f"Role: {self.context.role}")
        if self.context.company:
            parts.append(f"Company: {self.context.company}")
        return ". ".join(parts) if parts else ""

    def get_communication_prompt(self) -> str:
        """Get prompt text describing communication preferences."""
        parts = []

        # Style
        style_prompts = {
            "terse": "Be very concise and direct",
            "balanced": "Balance detail with brevity",
            "detailed": "Provide thorough explanations",
            "socratic": "Use questions to guide understanding",
        }
        parts.append(style_prompts.get(self.communication.style, ""))

        # Response length
        length_prompts = {
            "brief": "Keep responses short",
            "adaptive": "Adapt length to question complexity",
            "thorough": "Provide comprehensive responses",
        }
        parts.append(length_prompts.get(self.communication.response_length, ""))

        # Emoji
        if not self.communication.use_emoji:
            parts.append("Do not use emoji")

        # Formality
        formality_prompts = {
            "casual": "Use casual, friendly tone",
            "professional": "Use professional tone",
            "academic": "Use academic, formal tone",
        }
        parts.append(formality_prompts.get(self.communication.formality, ""))

        return ". ".join(p for p in parts if p)

    def get_full_personalization_prompt(self) -> str:
        """Get complete personalization prompt for system prompts."""
        sections = [
            self.get_communication_prompt(),
            self.get_expertise_prompt(),
            self.get_interests_prompt(),
            self.get_context_prompt(),
        ]
        return "\n".join(s for s in sections if s)


class PreferencesAdapter:
    """
    Adapter for reading and writing ai-preferences.yaml.

    This file is user-editable and contains explicit preferences
    that the user has set. Changes to this file take immediate effect.

    Example:
        adapter = PreferencesAdapter(vault_service)
        prefs = await adapter.load()
        print(prefs.communication.style)  # "balanced"

        prefs.expertise.append("rust")
        await adapter.save(prefs)
    """

    def __init__(
        self,
        vault: VaultService,
        preferences_path: str = PREFERENCES_PATH,
    ):
        """
        Initialize the preferences adapter.

        Args:
            vault: VaultService instance.
            preferences_path: Path to preferences file relative to vault.
        """
        self._vault = vault
        self._preferences_path = preferences_path
        self._cache: Optional[UserPreferences] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # Re-read from disk every 60 seconds

    async def load(self, use_cache: bool = True) -> UserPreferences:
        """
        Load user preferences from YAML file.

        Args:
            use_cache: Whether to use cached preferences if available.

        Returns:
            UserPreferences object.
        """
        # Check cache
        if use_cache and self._cache and self._cache_time:
            age = (datetime.now() - self._cache_time).total_seconds()
            if age < self._cache_ttl_seconds:
                return self._cache

        try:
            data = await self._vault.read_yaml(self._preferences_path)
            prefs = UserPreferences.from_dict(data)
            logger.debug(f"Loaded preferences from {self._preferences_path}")

        except NoteNotFoundError:
            logger.info(f"No preferences file found, using defaults")
            prefs = UserPreferences()

            # Create default preferences file
            await self.save(prefs)

        # Update cache
        self._cache = prefs
        self._cache_time = datetime.now()

        return prefs

    async def save(self, preferences: UserPreferences) -> None:
        """
        Save user preferences to YAML file.

        Args:
            preferences: UserPreferences to save.
        """
        data = preferences.to_dict()

        # Add header comment
        header = """# TROISE AI Preferences
# Edit this file to customize how TROISE interacts with you
#
# Communication styles: terse | balanced | detailed | socratic
# Response lengths: brief | adaptive | thorough
# Formality: casual | professional | academic
# Code style: imperative | functional | declarative

"""
        await self._vault.write_yaml(self._preferences_path, data)

        # Update cache
        self._cache = preferences
        self._cache_time = datetime.now()

        logger.info(f"Saved preferences to {self._preferences_path}")

    async def update(self, updates: Dict[str, Any]) -> UserPreferences:
        """
        Update specific preferences and save.

        Args:
            updates: Dictionary of updates to apply.

        Returns:
            Updated UserPreferences.
        """
        prefs = await self.load()
        data = prefs.to_dict()

        # Deep merge updates
        self._deep_merge(data, updates)

        # Create new preferences from merged data
        new_prefs = UserPreferences.from_dict(data)
        await self.save(new_prefs)

        return new_prefs

    def _deep_merge(self, base: Dict, updates: Dict) -> None:
        """Deep merge updates into base dictionary."""
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    async def add_expertise(self, skill: str) -> None:
        """Add an expertise area."""
        prefs = await self.load()
        if skill not in prefs.expertise:
            prefs.expertise.append(skill)
            await self.save(prefs)

    async def remove_expertise(self, skill: str) -> None:
        """Remove an expertise area."""
        prefs = await self.load()
        if skill in prefs.expertise:
            prefs.expertise.remove(skill)
            await self.save(prefs)

    async def add_interest(self, interest: str) -> None:
        """Add an interest."""
        prefs = await self.load()
        if interest not in prefs.interests:
            prefs.interests.append(interest)
            await self.save(prefs)

    async def set_current_project(self, project: str) -> None:
        """Set the current project context."""
        prefs = await self.load()
        prefs.context.current_project = project
        await self.save(prefs)

    def invalidate_cache(self) -> None:
        """Force reload on next load() call."""
        self._cache = None
        self._cache_time = None
