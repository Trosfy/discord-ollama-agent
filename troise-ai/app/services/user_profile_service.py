"""
User Profile Service for TROISE AI.

Provides unified access to user profile data from multiple sources:
- ai-preferences.yaml: User-editable preferences
- ai-learned.yaml: AI-populated learned context (high confidence)
- DynamoDB troise_main: Ephemeral memory (lower confidence)

The service combines these sources to build a complete user profile
for personalization and context in agent interactions.

Memory Hierarchy:
1. Preferences (highest priority) - explicit user settings
2. Learned Context (high priority) - high-confidence learned facts
3. Ephemeral Memory (lower priority) - recently learned, may decay
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.adapters.obsidian import PreferencesAdapter, LearnedContextAdapter, UserPreferences, LearnedContext
from app.adapters.dynamodb import DynamoDBClient, TroiseMainAdapter

logger = logging.getLogger(__name__)

# Confidence threshold for promoting to learned context
PROMOTION_THRESHOLD = 0.9

# Minimum confidence for including in profile
MIN_CONFIDENCE_THRESHOLD = 0.3


@dataclass
class UserProfile:
    """
    Complete user profile aggregated from all sources.

    Provides context for agent personalization.
    """
    user_id: str

    # From preferences (explicit)
    communication_style: Optional[str] = None
    expertise_level: Optional[str] = None
    preferred_response_length: Optional[str] = None
    preferred_language: Optional[str] = None
    preferred_formatting: Optional[str] = None

    # Aggregated from all sources
    expertise_areas: List[str] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)
    active_projects: List[str] = field(default_factory=list)

    # Communication patterns
    patterns: List[str] = field(default_factory=list)

    # Context info
    occupation: Optional[str] = None
    timezone: Optional[str] = None
    working_hours: Optional[str] = None

    # Ephemeral facts (from DynamoDB)
    recent_facts: Dict[str, str] = field(default_factory=dict)

    # Raw sources for debugging
    _preferences: Optional[UserPreferences] = field(default=None, repr=False)
    _learned: Optional[LearnedContext] = field(default=None, repr=False)

    def get_personalization_context(self) -> str:
        """
        Generate personalization context string for system prompts.

        Returns:
            Formatted context string for LLM consumption.
        """
        sections = []

        # Communication preferences
        if self.communication_style or self.expertise_level or self.preferred_response_length:
            prefs = []
            if self.expertise_level:
                prefs.append(f"User expertise level: {self.expertise_level}")
            if self.communication_style:
                prefs.append(f"Communication style: {self.communication_style}")
            if self.preferred_response_length:
                prefs.append(f"Preferred response length: {self.preferred_response_length}")
            if prefs:
                sections.append("Communication: " + "; ".join(prefs))

        # Expertise
        if self.expertise_areas:
            sections.append(f"User expertise: {', '.join(self.expertise_areas[:10])}")

        # Patterns
        if self.patterns:
            sections.append(f"Observed patterns: {'; '.join(self.patterns[:5])}")

        # Active projects
        if self.active_projects:
            sections.append(f"Active projects: {', '.join(self.active_projects[:5])}")

        # Context
        if self.occupation:
            sections.append(f"Occupation: {self.occupation}")

        return "\n".join(sections) if sections else ""

    def get_expertise_list(self) -> List[str]:
        """Get list of expertise areas."""
        return self.expertise_areas

    def has_expertise(self, skill: str) -> bool:
        """Check if user has a specific expertise."""
        skill_lower = skill.lower()
        return any(s.lower() == skill_lower for s in self.expertise_areas)

    def get_pattern(self, pattern_name: str) -> bool:
        """Check if user has a specific pattern."""
        pattern_lower = pattern_name.lower()
        return any(p.lower() == pattern_lower or p.lower().replace("_", " ") == pattern_lower
                   for p in self.patterns)


class UserProfileService:
    """
    Service for managing and aggregating user profiles.

    Combines data from:
    - PreferencesAdapter: User-editable preferences
    - LearnedContextAdapter: High-confidence learned facts
    - TroiseMainAdapter: Ephemeral DynamoDB memory

    Example:
        service = UserProfileService(
            preferences_adapter=PreferencesAdapter(vault),
            learned_adapter=LearnedContextAdapter(vault),
            main_adapter=TroiseMainAdapter(dynamo_client)
        )

        profile = await service.get_profile("user123")
        context = profile.get_personalization_context()
    """

    def __init__(
        self,
        preferences_adapter: Optional[PreferencesAdapter] = None,
        learned_adapter: Optional[LearnedContextAdapter] = None,
        main_adapter: Optional[TroiseMainAdapter] = None,
    ):
        """
        Initialize the user profile service.

        Args:
            preferences_adapter: Adapter for ai-preferences.yaml.
            learned_adapter: Adapter for ai-learned.yaml.
            main_adapter: DynamoDB adapter for ephemeral memory.
        """
        self._preferences = preferences_adapter
        self._learned = learned_adapter
        self._memory = main_adapter

    async def get_profile(
        self,
        user_id: str,
        include_ephemeral: bool = True,
    ) -> UserProfile:
        """
        Get complete user profile.

        Aggregates data from all sources with preference hierarchy:
        1. Explicit preferences (highest)
        2. Learned context (high confidence)
        3. Ephemeral memory (recent learnings)

        Args:
            user_id: User identifier.
            include_ephemeral: Include DynamoDB ephemeral memory.

        Returns:
            Aggregated UserProfile.
        """
        profile = UserProfile(user_id=user_id)

        # Load from preferences (if available)
        if self._preferences:
            try:
                prefs = await self._preferences.load()
                profile._preferences = prefs

                # Communication preferences
                profile.communication_style = prefs.communication.style
                profile.expertise_level = prefs.communication.expertise_level
                profile.preferred_response_length = prefs.communication.response_length
                profile.preferred_language = prefs.communication.language

                # Formatting
                if prefs.formatting:
                    profile.preferred_formatting = prefs.formatting.code_style

                # Context
                if prefs.context:
                    profile.occupation = prefs.context.occupation
                    profile.timezone = prefs.context.timezone
                    profile.working_hours = prefs.context.working_hours

                # Initial expertise and interests
                profile.expertise_areas = list(prefs.expertise)
                profile.interests = list(prefs.interests)

            except Exception as e:
                logger.warning(f"Failed to load preferences: {e}")

        # Load from learned context (if available)
        if self._learned:
            try:
                learned = await self._learned.load()
                profile._learned = learned

                # Add learned expertise (avoid duplicates)
                for skill in learned.get_expertise_list():
                    if skill not in profile.expertise_areas:
                        profile.expertise_areas.append(skill)

                # Add patterns
                profile.patterns = learned.get_pattern_list()

                # Add active projects
                profile.active_projects = learned.get_active_projects()

            except Exception as e:
                logger.warning(f"Failed to load learned context: {e}")

        # Load from ephemeral memory (if available and requested)
        if include_ephemeral and self._memory:
            try:
                memories = await self._memory.query_memories(
                    user_id=user_id,
                    min_confidence=MIN_CONFIDENCE_THRESHOLD,
                )

                for memory in memories:
                    category = memory.category
                    key = memory.key
                    value = memory.value

                    # Add to appropriate section
                    if category == "expertise":
                        if key not in profile.expertise_areas:
                            profile.expertise_areas.append(key)
                    elif category == "project":
                        if key not in profile.active_projects:
                            profile.active_projects.append(key)
                    elif category == "fact":
                        profile.recent_facts[key] = value

            except Exception as e:
                logger.warning(f"Failed to load ephemeral memory: {e}")

        return profile

    async def update_preference(
        self,
        key: str,
        value: Any,
    ) -> bool:
        """
        Update a user preference.

        Args:
            key: Preference key (e.g., "communication.style").
            value: New value.

        Returns:
            True if updated successfully.
        """
        if not self._preferences:
            logger.warning("No preferences adapter available")
            return False

        try:
            # Parse nested key
            parts = key.split(".")
            updates = {}
            current = updates

            for i, part in enumerate(parts[:-1]):
                current[part] = {}
                current = current[part]

            current[parts[-1]] = value

            await self._preferences.update(updates)
            return True

        except Exception as e:
            logger.error(f"Failed to update preference: {e}")
            return False

    async def promote_memory_to_learned(
        self,
        user_id: str,
        category: str,
        key: str,
        agent_name: str = "unknown",
    ) -> bool:
        """
        Promote a high-confidence ephemeral memory to learned context.

        Args:
            user_id: User identifier.
            category: Memory category.
            key: Memory key.
            agent_name: Agent doing the promotion.

        Returns:
            True if promoted successfully.
        """
        if not self._memory or not self._learned:
            logger.warning("Both memory and learned adapters required for promotion")
            return False

        try:
            # Get the memory
            memory = await self._memory.get_memory(user_id, category, key)
            if not memory:
                logger.warning(f"Memory {category}/{key} not found")
                return False

            if memory.confidence < PROMOTION_THRESHOLD:
                logger.warning(
                    f"Memory {category}/{key} confidence {memory.confidence} "
                    f"below threshold {PROMOTION_THRESHOLD}"
                )
                return False

            # Promote based on category
            if category == "expertise":
                await self._learned.add_expertise(
                    skill=key,
                    confidence=memory.confidence,
                    learned_by=agent_name,
                    evidence=memory.evidence or memory.value,
                )
            elif category == "preference":
                await self._learned.add_pattern(
                    pattern=key,
                    confidence=memory.confidence,
                    evidence=memory.evidence or memory.value,
                )
            elif category == "project":
                await self._learned.update_project(
                    project_name=key,
                    status="active",
                    notes=memory.value,
                )
            else:
                logger.warning(f"Unknown category for promotion: {category}")
                return False

            logger.info(f"Promoted memory {category}/{key} to learned context")
            return True

        except Exception as e:
            logger.error(f"Failed to promote memory: {e}")
            return False

    async def check_and_promote_memories(
        self,
        user_id: str,
        agent_name: str = "promotion_task",
    ) -> int:
        """
        Check all memories and promote those above threshold.

        Args:
            user_id: User identifier.
            agent_name: Agent name for tracking.

        Returns:
            Number of memories promoted.
        """
        if not self._memory:
            return 0

        try:
            memories = await self._memory.query_memories(
                user_id=user_id,
                min_confidence=PROMOTION_THRESHOLD,
            )

            promoted = 0
            for memory in memories:
                if await self.promote_memory_to_learned(
                    user_id=user_id,
                    category=memory.category,
                    key=memory.key,
                    agent_name=agent_name,
                ):
                    promoted += 1

            if promoted > 0:
                logger.info(f"Promoted {promoted} memories to learned context")

            return promoted

        except Exception as e:
            logger.error(f"Failed to check/promote memories: {e}")
            return 0

    async def decay_ephemeral_memories(
        self,
        user_id: str,
        decay_rate: float = 0.01,
    ) -> int:
        """
        Apply confidence decay to ephemeral memories.

        Args:
            user_id: User identifier.
            decay_rate: Decay amount per call.

        Returns:
            Number of memories updated.
        """
        if not self._memory:
            return 0

        return await self._memory.decay_memories(user_id, decay_rate)

    async def get_profile_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get a summary of the user profile for debugging.

        Args:
            user_id: User identifier.

        Returns:
            Summary dictionary.
        """
        profile = await self.get_profile(user_id)

        return {
            "user_id": user_id,
            "expertise_count": len(profile.expertise_areas),
            "expertise_areas": profile.expertise_areas[:10],
            "pattern_count": len(profile.patterns),
            "patterns": profile.patterns[:5],
            "active_projects": profile.active_projects[:5],
            "recent_facts_count": len(profile.recent_facts),
            "has_preferences": profile._preferences is not None,
            "has_learned_context": profile._learned is not None,
            "personalization_length": len(profile.get_personalization_context()),
        }


class UserMemoryAdapter:
    """
    Adapter that implements IUserMemory using TroiseMainAdapter.

    Provides the interface expected by remember/recall tools.
    """

    def __init__(self, main_adapter: TroiseMainAdapter):
        """
        Initialize the adapter.

        Args:
            main_adapter: TroiseMainAdapter instance.
        """
        self._adapter = main_adapter

    async def get_all(self, user_id: str) -> List[Dict]:
        """Get all memory items for a user."""
        memories = await self._adapter.get_all_memories(user_id)
        return [self._to_dict(m) for m in memories]

    async def get(
        self,
        user_id: str,
        category: str,
        key: str,
    ) -> Optional[Dict]:
        """Get specific memory item."""
        memory = await self._adapter.get_memory(user_id, category, key)
        if memory:
            return self._to_dict(memory)
        return None

    async def query(
        self,
        user_id: str,
        category: str = None,
    ) -> List[Dict]:
        """Query memory by category."""
        memories = await self._adapter.query_memories(user_id, category)
        return [self._to_dict(m) for m in memories]

    async def put(
        self,
        user_id: str,
        category: str,
        key: str,
        value: str,
        source: str = "learned",
        confidence: float = 1.0,
        learned_by: str = None,
        ttl: int = None,
    ) -> None:
        """Store a memory item."""
        await self._adapter.put_memory(
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            confidence=confidence,
            source=source,
            learned_by=learned_by,
            ttl_seconds=ttl,
        )

    async def delete(
        self,
        user_id: str,
        category: str,
        key: str,
    ) -> None:
        """Delete a memory item."""
        await self._adapter.delete_memory(user_id, category, key)

    def _to_dict(self, memory) -> Dict:
        """Convert MemoryItem to dict."""
        return {
            "user_id": memory.user_id,
            "category": memory.category,
            "key": memory.key,
            "value": memory.value,
            "confidence": memory.confidence,
            "source": memory.source,
            "learned_by": memory.learned_by,
            "created_at": memory.created_at,
            "updated_at": memory.updated_at,
            "evidence": memory.evidence,
        }


# Factory functions for DI container
def create_user_profile_service(
    preferences_adapter: Optional[PreferencesAdapter] = None,
    learned_adapter: Optional[LearnedContextAdapter] = None,
    main_adapter: Optional[TroiseMainAdapter] = None,
) -> UserProfileService:
    """
    Create a UserProfileService instance.

    Factory function for the DI container.

    Args:
        preferences_adapter: Adapter for ai-preferences.yaml.
        learned_adapter: Adapter for ai-learned.yaml.
        main_adapter: DynamoDB adapter for ephemeral memory.

    Returns:
        Configured UserProfileService instance.
    """
    return UserProfileService(
        preferences_adapter=preferences_adapter,
        learned_adapter=learned_adapter,
        main_adapter=main_adapter,
    )


def create_user_memory_adapter(
    main_adapter: TroiseMainAdapter,
) -> UserMemoryAdapter:
    """
    Create a UserMemoryAdapter instance.

    Factory function for the DI container.

    Args:
        main_adapter: TroiseMainAdapter instance.

    Returns:
        Configured UserMemoryAdapter instance.
    """
    return UserMemoryAdapter(main_adapter)
