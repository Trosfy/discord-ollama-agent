"""AI Learned Context Adapter - reads/writes ai-learned.yaml.

The learned context file is AI-populated and user-reviewable.
It stores high-confidence (>0.9) learned context that has been
promoted from DynamoDB ephemeral storage.

Contents:
- expertise_areas: Skills learned from interactions
- communication_patterns: Observed preferences
- project_context: Current project state
- custom learned items

Location: {vault}/00-meta/ai-learned.yaml
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .vault_service import VaultService, NoteNotFoundError

logger = logging.getLogger(__name__)


# Default learned context file path within vault
LEARNED_PATH = "00-meta/ai-learned.yaml"

# Minimum confidence to store in learned context
MIN_CONFIDENCE = 0.9


@dataclass
class LearnedSkill:
    """A skill/expertise learned about the user."""
    skill: str
    confidence: float
    learned_at: str  # ISO8601
    learned_by: str  # Agent that learned this
    evidence: str  # Why we believe this


@dataclass
class LearnedPattern:
    """A communication/behavior pattern observed."""
    pattern: str
    confidence: float
    learned_at: str  # ISO8601
    evidence: str


@dataclass
class ProjectContext:
    """Learned context about a project."""
    status: str = "active"  # active | paused | completed
    technologies: List[str] = field(default_factory=list)
    last_discussed: Optional[str] = None  # ISO8601
    notes: Optional[str] = None


@dataclass
class LearnedContext:
    """Complete learned context from ai-learned.yaml."""
    expertise_areas: List[LearnedSkill] = field(default_factory=list)
    communication_patterns: List[LearnedPattern] = field(default_factory=list)
    project_context: Dict[str, ProjectContext] = field(default_factory=dict)
    custom: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "expertise_areas": [
                {
                    "skill": s.skill,
                    "confidence": s.confidence,
                    "learned_at": s.learned_at,
                    "learned_by": s.learned_by,
                    "evidence": s.evidence,
                }
                for s in self.expertise_areas
            ],
            "communication_patterns": [
                {
                    "pattern": p.pattern,
                    "confidence": p.confidence,
                    "learned_at": p.learned_at,
                    "evidence": p.evidence,
                }
                for p in self.communication_patterns
            ],
            "project_context": {
                name: {
                    "status": ctx.status,
                    "technologies": ctx.technologies,
                    "last_discussed": ctx.last_discussed,
                    "notes": ctx.notes,
                }
                for name, ctx in self.project_context.items()
            },
            **self.custom,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearnedContext":
        """Create from dictionary (YAML data)."""
        # Parse expertise areas
        expertise_areas = []
        for item in data.get("expertise_areas", []):
            expertise_areas.append(LearnedSkill(
                skill=item.get("skill", ""),
                confidence=item.get("confidence", 0.0),
                learned_at=item.get("learned_at", ""),
                learned_by=item.get("learned_by", "unknown"),
                evidence=item.get("evidence", ""),
            ))

        # Parse communication patterns
        patterns = []
        for item in data.get("communication_patterns", []):
            patterns.append(LearnedPattern(
                pattern=item.get("pattern", ""),
                confidence=item.get("confidence", 0.0),
                learned_at=item.get("learned_at", ""),
                evidence=item.get("evidence", ""),
            ))

        # Parse project context
        project_context = {}
        for name, ctx_data in data.get("project_context", {}).items():
            project_context[name] = ProjectContext(
                status=ctx_data.get("status", "active"),
                technologies=ctx_data.get("technologies", []),
                last_discussed=ctx_data.get("last_discussed"),
                notes=ctx_data.get("notes"),
            )

        # Collect custom fields
        known_keys = {"expertise_areas", "communication_patterns", "project_context"}
        custom = {k: v for k, v in data.items() if k not in known_keys}

        return cls(
            expertise_areas=expertise_areas,
            communication_patterns=patterns,
            project_context=project_context,
            custom=custom,
        )

    def get_expertise_list(self) -> List[str]:
        """Get list of learned expertise skills."""
        return [s.skill for s in self.expertise_areas]

    def get_pattern_list(self) -> List[str]:
        """Get list of learned patterns."""
        return [p.pattern for p in self.communication_patterns]

    def get_active_projects(self) -> List[str]:
        """Get list of active project names."""
        return [name for name, ctx in self.project_context.items() if ctx.status == "active"]

    def get_expertise_prompt(self) -> str:
        """Get prompt text for learned expertise."""
        if not self.expertise_areas:
            return ""
        skills = [s.skill for s in self.expertise_areas if s.confidence >= MIN_CONFIDENCE]
        if not skills:
            return ""
        return f"User has demonstrated expertise in: {', '.join(skills)}."

    def get_patterns_prompt(self) -> str:
        """Get prompt text for learned patterns."""
        if not self.communication_patterns:
            return ""
        high_conf = [p for p in self.communication_patterns if p.confidence >= MIN_CONFIDENCE]
        if not high_conf:
            return ""
        patterns = [p.pattern.replace("_", " ") for p in high_conf]
        return f"Observed user patterns: {'; '.join(patterns)}."

    def get_projects_prompt(self) -> str:
        """Get prompt text for project context."""
        active = self.get_active_projects()
        if not active:
            return ""
        return f"Active projects: {', '.join(active)}."

    def get_full_context_prompt(self) -> str:
        """Get complete learned context prompt."""
        sections = [
            self.get_expertise_prompt(),
            self.get_patterns_prompt(),
            self.get_projects_prompt(),
        ]
        return "\n".join(s for s in sections if s)


class LearnedContextAdapter:
    """
    Adapter for reading and writing ai-learned.yaml.

    This file is AI-populated with high-confidence learned context.
    Users can review and edit this file to correct any mistakes.

    Items are promoted to this file from DynamoDB when they reach
    high confidence (>0.9) through repeated observation.

    Example:
        adapter = LearnedContextAdapter(vault_service)
        context = await adapter.load()

        # Add a learned skill
        await adapter.add_expertise(
            skill="rust",
            confidence=0.95,
            learned_by="agentic_code_agent",
            evidence="Built CLI tool in Rust"
        )

        # Update project context
        await adapter.update_project(
            "troise-ai",
            technologies=["python", "fastapi", "strands"],
            status="active"
        )
    """

    def __init__(
        self,
        vault: VaultService,
        learned_path: str = LEARNED_PATH,
    ):
        """
        Initialize the learned context adapter.

        Args:
            vault: VaultService instance.
            learned_path: Path to learned file relative to vault.
        """
        self._vault = vault
        self._learned_path = learned_path
        self._cache: Optional[LearnedContext] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 60

    async def load(self, use_cache: bool = True) -> LearnedContext:
        """
        Load learned context from YAML file.

        Args:
            use_cache: Whether to use cached context if available.

        Returns:
            LearnedContext object.
        """
        # Check cache
        if use_cache and self._cache and self._cache_time:
            age = (datetime.now() - self._cache_time).total_seconds()
            if age < self._cache_ttl_seconds:
                return self._cache

        try:
            data = await self._vault.read_yaml(self._learned_path)
            context = LearnedContext.from_dict(data)
            logger.debug(f"Loaded learned context from {self._learned_path}")

        except NoteNotFoundError:
            logger.info(f"No learned context file found, creating empty")
            context = LearnedContext()
            await self.save(context)

        # Update cache
        self._cache = context
        self._cache_time = datetime.now()

        return context

    async def save(self, context: LearnedContext) -> None:
        """
        Save learned context to YAML file.

        Args:
            context: LearnedContext to save.
        """
        data = context.to_dict()
        await self._vault.write_yaml(self._learned_path, data)

        # Update cache
        self._cache = context
        self._cache_time = datetime.now()

        logger.info(f"Saved learned context to {self._learned_path}")

    async def add_expertise(
        self,
        skill: str,
        confidence: float,
        learned_by: str,
        evidence: str,
    ) -> bool:
        """
        Add or update a learned expertise.

        Args:
            skill: Skill name (e.g., "rust", "kubernetes").
            confidence: Confidence level (0.0-1.0).
            learned_by: Agent that learned this.
            evidence: Evidence for why we believe this.

        Returns:
            True if added/updated, False if confidence too low.
        """
        if confidence < MIN_CONFIDENCE:
            logger.debug(f"Skill '{skill}' confidence {confidence} below threshold")
            return False

        context = await self.load()

        # Check if skill already exists
        for existing in context.expertise_areas:
            if existing.skill.lower() == skill.lower():
                # Update if new confidence is higher
                if confidence > existing.confidence:
                    existing.confidence = confidence
                    existing.learned_at = datetime.now().isoformat()
                    existing.learned_by = learned_by
                    existing.evidence = evidence
                    await self.save(context)
                    logger.info(f"Updated expertise '{skill}' to confidence {confidence}")
                return True

        # Add new skill
        context.expertise_areas.append(LearnedSkill(
            skill=skill,
            confidence=confidence,
            learned_at=datetime.now().isoformat(),
            learned_by=learned_by,
            evidence=evidence,
        ))
        await self.save(context)
        logger.info(f"Added new expertise '{skill}' with confidence {confidence}")
        return True

    async def remove_expertise(self, skill: str) -> bool:
        """
        Remove a learned expertise.

        Args:
            skill: Skill name to remove.

        Returns:
            True if removed, False if not found.
        """
        context = await self.load()

        for i, existing in enumerate(context.expertise_areas):
            if existing.skill.lower() == skill.lower():
                context.expertise_areas.pop(i)
                await self.save(context)
                logger.info(f"Removed expertise '{skill}'")
                return True

        return False

    async def add_pattern(
        self,
        pattern: str,
        confidence: float,
        evidence: str,
    ) -> bool:
        """
        Add or update a learned communication pattern.

        Args:
            pattern: Pattern identifier (e.g., "prefers_code_over_prose").
            confidence: Confidence level (0.0-1.0).
            evidence: Evidence for why we believe this.

        Returns:
            True if added/updated, False if confidence too low.
        """
        if confidence < MIN_CONFIDENCE:
            logger.debug(f"Pattern '{pattern}' confidence {confidence} below threshold")
            return False

        context = await self.load()

        # Check if pattern exists
        for existing in context.communication_patterns:
            if existing.pattern.lower() == pattern.lower():
                if confidence > existing.confidence:
                    existing.confidence = confidence
                    existing.learned_at = datetime.now().isoformat()
                    existing.evidence = evidence
                    await self.save(context)
                return True

        # Add new pattern
        context.communication_patterns.append(LearnedPattern(
            pattern=pattern,
            confidence=confidence,
            learned_at=datetime.now().isoformat(),
            evidence=evidence,
        ))
        await self.save(context)
        logger.info(f"Added new pattern '{pattern}' with confidence {confidence}")
        return True

    async def update_project(
        self,
        project_name: str,
        status: Optional[str] = None,
        technologies: Optional[List[str]] = None,
        notes: Optional[str] = None,
    ) -> None:
        """
        Update or create project context.

        Args:
            project_name: Project name.
            status: Project status (active, paused, completed).
            technologies: List of technologies used.
            notes: Additional notes.
        """
        context = await self.load()

        if project_name not in context.project_context:
            context.project_context[project_name] = ProjectContext()

        project = context.project_context[project_name]

        if status is not None:
            project.status = status
        if technologies is not None:
            project.technologies = technologies
        if notes is not None:
            project.notes = notes

        project.last_discussed = datetime.now().isoformat()

        await self.save(context)
        logger.info(f"Updated project context for '{project_name}'")

    async def get_project(self, project_name: str) -> Optional[ProjectContext]:
        """
        Get project context by name.

        Args:
            project_name: Project name.

        Returns:
            ProjectContext or None if not found.
        """
        context = await self.load()
        return context.project_context.get(project_name)

    async def get_all_skills(self) -> List[str]:
        """Get all learned skill names."""
        context = await self.load()
        return [s.skill for s in context.expertise_areas]

    async def get_high_confidence_skills(self) -> List[str]:
        """Get skills with confidence >= MIN_CONFIDENCE."""
        context = await self.load()
        return [s.skill for s in context.expertise_areas if s.confidence >= MIN_CONFIDENCE]

    async def decay_confidences(self, decay_rate: float = 0.01) -> int:
        """
        Apply confidence decay to all items.

        Items that fall below MIN_CONFIDENCE are not removed but
        will not be included in prompts.

        Args:
            decay_rate: Amount to reduce confidence by.

        Returns:
            Number of items that fell below threshold.
        """
        context = await self.load()
        fallen = 0

        for skill in context.expertise_areas:
            old_conf = skill.confidence
            skill.confidence = max(0.0, skill.confidence - decay_rate)
            if old_conf >= MIN_CONFIDENCE and skill.confidence < MIN_CONFIDENCE:
                fallen += 1

        for pattern in context.communication_patterns:
            old_conf = pattern.confidence
            pattern.confidence = max(0.0, pattern.confidence - decay_rate)
            if old_conf >= MIN_CONFIDENCE and pattern.confidence < MIN_CONFIDENCE:
                fallen += 1

        if fallen > 0:
            await self.save(context)
            logger.info(f"Decayed confidences, {fallen} items fell below threshold")

        return fallen

    async def reinforce_skill(self, skill: str, boost: float = 0.05) -> bool:
        """
        Reinforce a learned skill by boosting its confidence.

        Args:
            skill: Skill name.
            boost: Amount to increase confidence.

        Returns:
            True if skill found and boosted.
        """
        context = await self.load()

        for existing in context.expertise_areas:
            if existing.skill.lower() == skill.lower():
                existing.confidence = min(1.0, existing.confidence + boost)
                existing.learned_at = datetime.now().isoformat()
                await self.save(context)
                logger.info(f"Reinforced skill '{skill}' to {existing.confidence}")
                return True

        return False

    def invalidate_cache(self) -> None:
        """Force reload on next load() call."""
        self._cache = None
        self._cache_time = None
