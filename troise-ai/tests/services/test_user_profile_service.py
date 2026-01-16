"""Unit tests for User Profile Service."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.user_profile_service import (
    UserProfileService,
    UserProfile,
    UserMemoryAdapter,
    PROMOTION_THRESHOLD,
    MIN_CONFIDENCE_THRESHOLD,
    create_user_profile_service,
    create_user_memory_adapter,
)


# =============================================================================
# Mock Classes
# =============================================================================

@dataclass
class MockCommunication:
    style: Optional[str] = "balanced"
    expertise_level: Optional[str] = "intermediate"
    response_length: Optional[str] = "medium"
    language: Optional[str] = "en"


@dataclass
class MockFormatting:
    code_style: Optional[str] = "pep8"


@dataclass
class MockContext:
    occupation: Optional[str] = "developer"
    timezone: Optional[str] = "UTC"
    working_hours: Optional[str] = "9-17"


@dataclass
class MockUserPreferences:
    communication: MockCommunication = field(default_factory=MockCommunication)
    formatting: Optional[MockFormatting] = field(default_factory=MockFormatting)
    context: Optional[MockContext] = field(default_factory=MockContext)
    expertise: List[str] = field(default_factory=lambda: ["python", "testing"])
    interests: List[str] = field(default_factory=lambda: ["ai", "automation"])


class MockPreferencesAdapter:
    """Mock preferences adapter."""

    def __init__(self, prefs: MockUserPreferences = None):
        self._prefs = prefs or MockUserPreferences()
        self._updates = []

    async def load(self) -> MockUserPreferences:
        return self._prefs

    async def update(self, updates: Dict) -> None:
        self._updates.append(updates)


@dataclass
class MockLearnedContext:
    expertise: Dict[str, Any] = field(default_factory=dict)
    patterns: Dict[str, Any] = field(default_factory=dict)
    projects: Dict[str, Any] = field(default_factory=dict)

    def get_expertise_list(self) -> List[str]:
        return list(self.expertise.keys())

    def get_pattern_list(self) -> List[str]:
        return list(self.patterns.keys())

    def get_active_projects(self) -> List[str]:
        return [p for p, info in self.projects.items() if info.get("status") == "active"]


class MockLearnedContextAdapter:
    """Mock learned context adapter."""

    def __init__(self, context: MockLearnedContext = None):
        self._context = context or MockLearnedContext()
        self._added_expertise = []
        self._added_patterns = []
        self._updated_projects = []

    async def load(self) -> MockLearnedContext:
        return self._context

    async def add_expertise(self, skill: str, confidence: float, learned_by: str, evidence: str) -> None:
        self._added_expertise.append({
            "skill": skill,
            "confidence": confidence,
            "learned_by": learned_by,
            "evidence": evidence,
        })

    async def add_pattern(self, pattern: str, confidence: float, evidence: str) -> None:
        self._added_patterns.append({
            "pattern": pattern,
            "confidence": confidence,
            "evidence": evidence,
        })

    async def update_project(self, project_name: str, status: str, notes: str) -> None:
        self._updated_projects.append({
            "project_name": project_name,
            "status": status,
            "notes": notes,
        })


@dataclass
class MockMemoryItem:
    user_id: str
    category: str
    key: str
    value: str
    confidence: float = 0.5
    source: str = "learned"
    learned_by: Optional[str] = None
    evidence: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MockMainAdapter:
    """Mock DynamoDB main adapter."""

    def __init__(self):
        self._memories: Dict[str, MockMemoryItem] = {}
        self._decay_calls = []

    def _key(self, user_id: str, category: str, key: str) -> str:
        return f"{user_id}:{category}:{key}"

    async def put_memory(
        self,
        user_id: str,
        category: str,
        key: str,
        value: str,
        confidence: float = 0.5,
        source: str = "learned",
        learned_by: str = None,
        ttl_seconds: int = None,
    ) -> None:
        mem_key = self._key(user_id, category, key)
        self._memories[mem_key] = MockMemoryItem(
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            confidence=confidence,
            source=source,
            learned_by=learned_by,
        )

    async def get_memory(self, user_id: str, category: str, key: str) -> Optional[MockMemoryItem]:
        return self._memories.get(self._key(user_id, category, key))

    async def get_all_memories(self, user_id: str) -> List[MockMemoryItem]:
        return [m for m in self._memories.values() if m.user_id == user_id]

    async def query_memories(
        self,
        user_id: str,
        category: str = None,
        min_confidence: float = 0.0,
    ) -> List[MockMemoryItem]:
        memories = [m for m in self._memories.values() if m.user_id == user_id]
        if category:
            memories = [m for m in memories if m.category == category]
        memories = [m for m in memories if m.confidence >= min_confidence]
        return memories

    async def delete_memory(self, user_id: str, category: str, key: str) -> bool:
        key_str = self._key(user_id, category, key)
        if key_str in self._memories:
            del self._memories[key_str]
            return True
        return False

    async def decay_memories(self, user_id: str, decay_rate: float) -> int:
        self._decay_calls.append({"user_id": user_id, "decay_rate": decay_rate})
        count = 0
        for m in self._memories.values():
            if m.user_id == user_id:
                m.confidence = max(0, m.confidence - decay_rate)
                count += 1
        return count

    def add_memory(self, **kwargs):
        """Helper to add test memories."""
        mem = MockMemoryItem(**kwargs)
        self._memories[self._key(mem.user_id, mem.category, mem.key)] = mem


# =============================================================================
# UserProfile Tests
# =============================================================================

def test_user_profile_defaults():
    """UserProfile has correct defaults."""
    profile = UserProfile(user_id="test")

    assert profile.user_id == "test"
    assert profile.expertise_areas == []
    assert profile.interests == []
    assert profile.patterns == []
    assert profile.active_projects == []
    assert profile.recent_facts == {}


def test_user_profile_personalization_context():
    """get_personalization_context() generates formatted context."""
    profile = UserProfile(
        user_id="test",
        expertise_level="expert",
        communication_style="concise",
        expertise_areas=["python", "kubernetes"],
        patterns=["prefers_code_examples"],
        active_projects=["troise-ai"],
        occupation="developer",
    )

    context = profile.get_personalization_context()

    assert "expert" in context.lower()
    assert "concise" in context
    assert "python" in context
    assert "prefers_code_examples" in context
    assert "troise-ai" in context
    assert "developer" in context


def test_user_profile_personalization_empty():
    """get_personalization_context() returns empty for minimal profile."""
    profile = UserProfile(user_id="test")

    context = profile.get_personalization_context()

    assert context == ""


def test_user_profile_has_expertise():
    """has_expertise() checks case-insensitively."""
    profile = UserProfile(user_id="test", expertise_areas=["Python", "JavaScript"])

    assert profile.has_expertise("python")
    assert profile.has_expertise("PYTHON")
    assert profile.has_expertise("javascript")
    assert not profile.has_expertise("rust")


def test_user_profile_get_expertise_list():
    """get_expertise_list() returns expertise areas."""
    profile = UserProfile(user_id="test", expertise_areas=["python", "testing"])

    assert profile.get_expertise_list() == ["python", "testing"]


def test_user_profile_get_pattern():
    """get_pattern() checks patterns case-insensitively."""
    profile = UserProfile(user_id="test", patterns=["prefers_concise", "likes_examples"])

    assert profile.get_pattern("prefers_concise")
    assert profile.get_pattern("PREFERS_CONCISE")
    assert profile.get_pattern("prefers concise")  # underscore to space
    assert not profile.get_pattern("unknown_pattern")


# =============================================================================
# UserProfileService.get_profile Tests
# =============================================================================

async def test_get_profile_basic():
    """get_profile() returns UserProfile."""
    service = UserProfileService()

    profile = await service.get_profile("test-user")

    assert profile.user_id == "test-user"
    assert isinstance(profile, UserProfile)


async def test_get_profile_with_preferences():
    """get_profile() loads preferences."""
    prefs = MockUserPreferences(
        communication=MockCommunication(style="formal", expertise_level="expert"),
        expertise=["rust", "go"],
        interests=["systems"],
    )
    prefs_adapter = MockPreferencesAdapter(prefs)

    service = UserProfileService(preferences_adapter=prefs_adapter)

    profile = await service.get_profile("test-user")

    assert profile.communication_style == "formal"
    assert profile.expertise_level == "expert"
    assert "rust" in profile.expertise_areas
    assert "go" in profile.expertise_areas
    assert "systems" in profile.interests


async def test_get_profile_with_learned():
    """get_profile() loads learned context."""
    learned = MockLearnedContext(
        expertise={"python": {}, "testing": {}},
        patterns={"prefers_examples": {}},
        projects={"troise": {"status": "active"}},
    )
    learned_adapter = MockLearnedContextAdapter(learned)

    service = UserProfileService(learned_adapter=learned_adapter)

    profile = await service.get_profile("test-user")

    assert "python" in profile.expertise_areas
    assert "testing" in profile.expertise_areas
    assert "prefers_examples" in profile.patterns
    assert "troise" in profile.active_projects


async def test_get_profile_merges_expertise():
    """get_profile() merges expertise from all sources without duplicates."""
    prefs = MockUserPreferences(expertise=["python"])
    prefs_adapter = MockPreferencesAdapter(prefs)

    learned = MockLearnedContext(expertise={"python": {}, "rust": {}})
    learned_adapter = MockLearnedContextAdapter(learned)

    service = UserProfileService(
        preferences_adapter=prefs_adapter,
        learned_adapter=learned_adapter,
    )

    profile = await service.get_profile("test-user")

    # python should appear only once
    assert profile.expertise_areas.count("python") == 1
    assert "rust" in profile.expertise_areas


async def test_get_profile_with_ephemeral_memory():
    """get_profile() includes ephemeral memory."""
    main_adapter = MockMainAdapter()
    main_adapter.add_memory(
        user_id="test-user",
        category="expertise",
        key="kubernetes",
        value="knows k8s well",
        confidence=0.7,
    )
    main_adapter.add_memory(
        user_id="test-user",
        category="fact",
        key="prefers_vim",
        value="uses vim daily",
        confidence=0.8,
    )

    service = UserProfileService(main_adapter=main_adapter)

    profile = await service.get_profile("test-user")

    assert "kubernetes" in profile.expertise_areas
    assert "prefers_vim" in profile.recent_facts


async def test_get_profile_filters_low_confidence():
    """get_profile() filters out low confidence memories."""
    main_adapter = MockMainAdapter()
    main_adapter.add_memory(
        user_id="test-user",
        category="expertise",
        key="low_skill",
        value="maybe knows",
        confidence=0.1,  # Below threshold
    )
    main_adapter.add_memory(
        user_id="test-user",
        category="expertise",
        key="high_skill",
        value="definitely knows",
        confidence=0.5,
    )

    service = UserProfileService(main_adapter=main_adapter)

    profile = await service.get_profile("test-user")

    assert "high_skill" in profile.expertise_areas
    assert "low_skill" not in profile.expertise_areas


async def test_get_profile_exclude_ephemeral():
    """get_profile() can exclude ephemeral memory."""
    main_adapter = MockMainAdapter()
    main_adapter.add_memory(
        user_id="test-user",
        category="expertise",
        key="ephemeral_skill",
        value="temp",
        confidence=0.8,
    )

    service = UserProfileService(main_adapter=main_adapter)

    profile = await service.get_profile("test-user", include_ephemeral=False)

    assert "ephemeral_skill" not in profile.expertise_areas


# =============================================================================
# UserProfileService.update_preference Tests
# =============================================================================

async def test_update_preference():
    """update_preference() updates preferences file."""
    prefs_adapter = MockPreferencesAdapter()
    service = UserProfileService(preferences_adapter=prefs_adapter)

    result = await service.update_preference("communication.style", "formal")

    assert result is True
    assert len(prefs_adapter._updates) == 1
    assert "communication" in prefs_adapter._updates[0]


async def test_update_preference_no_adapter():
    """update_preference() returns False without adapter."""
    service = UserProfileService()

    result = await service.update_preference("communication.style", "formal")

    assert result is False


# =============================================================================
# UserProfileService.promote_memory_to_learned Tests
# =============================================================================

async def test_promote_memory_expertise():
    """promote_memory_to_learned() promotes expertise memory."""
    main_adapter = MockMainAdapter()
    main_adapter.add_memory(
        user_id="test-user",
        category="expertise",
        key="rust",
        value="experienced rust developer",
        confidence=0.95,
        evidence="mentioned in multiple conversations",
    )

    learned_adapter = MockLearnedContextAdapter()

    service = UserProfileService(
        main_adapter=main_adapter,
        learned_adapter=learned_adapter,
    )

    result = await service.promote_memory_to_learned(
        user_id="test-user",
        category="expertise",
        key="rust",
    )

    assert result is True
    assert len(learned_adapter._added_expertise) == 1
    assert learned_adapter._added_expertise[0]["skill"] == "rust"


async def test_promote_memory_preference():
    """promote_memory_to_learned() promotes preference as pattern."""
    main_adapter = MockMainAdapter()
    main_adapter.add_memory(
        user_id="test-user",
        category="preference",
        key="prefers_concise",
        value="likes short answers",
        confidence=0.92,
    )

    learned_adapter = MockLearnedContextAdapter()

    service = UserProfileService(
        main_adapter=main_adapter,
        learned_adapter=learned_adapter,
    )

    result = await service.promote_memory_to_learned(
        user_id="test-user",
        category="preference",
        key="prefers_concise",
    )

    assert result is True
    assert len(learned_adapter._added_patterns) == 1


async def test_promote_memory_project():
    """promote_memory_to_learned() promotes project memory."""
    main_adapter = MockMainAdapter()
    main_adapter.add_memory(
        user_id="test-user",
        category="project",
        key="troise-ai",
        value="AI assistant project",
        confidence=0.91,
    )

    learned_adapter = MockLearnedContextAdapter()

    service = UserProfileService(
        main_adapter=main_adapter,
        learned_adapter=learned_adapter,
    )

    result = await service.promote_memory_to_learned(
        user_id="test-user",
        category="project",
        key="troise-ai",
    )

    assert result is True
    assert len(learned_adapter._updated_projects) == 1


async def test_promote_memory_below_threshold():
    """promote_memory_to_learned() rejects low confidence."""
    main_adapter = MockMainAdapter()
    main_adapter.add_memory(
        user_id="test-user",
        category="expertise",
        key="low_conf_skill",
        value="maybe",
        confidence=0.5,  # Below threshold
    )

    learned_adapter = MockLearnedContextAdapter()

    service = UserProfileService(
        main_adapter=main_adapter,
        learned_adapter=learned_adapter,
    )

    result = await service.promote_memory_to_learned(
        user_id="test-user",
        category="expertise",
        key="low_conf_skill",
    )

    assert result is False
    assert len(learned_adapter._added_expertise) == 0


async def test_promote_memory_not_found():
    """promote_memory_to_learned() returns False for missing memory."""
    main_adapter = MockMainAdapter()
    learned_adapter = MockLearnedContextAdapter()

    service = UserProfileService(
        main_adapter=main_adapter,
        learned_adapter=learned_adapter,
    )

    result = await service.promote_memory_to_learned(
        user_id="test-user",
        category="expertise",
        key="nonexistent",
    )

    assert result is False


# =============================================================================
# UserProfileService.check_and_promote_memories Tests
# =============================================================================

async def test_check_and_promote_memories():
    """check_and_promote_memories() promotes all eligible memories."""
    main_adapter = MockMainAdapter()
    main_adapter.add_memory(
        user_id="test-user",
        category="expertise",
        key="python",
        value="expert",
        confidence=0.95,
    )
    main_adapter.add_memory(
        user_id="test-user",
        category="expertise",
        key="rust",
        value="learning",
        confidence=0.3,  # Too low
    )
    main_adapter.add_memory(
        user_id="test-user",
        category="preference",
        key="concise",
        value="yes",
        confidence=0.91,
    )

    learned_adapter = MockLearnedContextAdapter()

    service = UserProfileService(
        main_adapter=main_adapter,
        learned_adapter=learned_adapter,
    )

    count = await service.check_and_promote_memories("test-user")

    assert count == 2  # python and concise
    assert len(learned_adapter._added_expertise) == 1
    assert len(learned_adapter._added_patterns) == 1


# =============================================================================
# UserProfileService.decay_ephemeral_memories Tests
# =============================================================================

async def test_decay_ephemeral_memories():
    """decay_ephemeral_memories() reduces confidence."""
    main_adapter = MockMainAdapter()
    main_adapter.add_memory(
        user_id="test-user",
        category="expertise",
        key="skill",
        value="test",
        confidence=0.5,
    )

    service = UserProfileService(main_adapter=main_adapter)

    count = await service.decay_ephemeral_memories("test-user", decay_rate=0.1)

    assert count == 1
    assert main_adapter._decay_calls[0]["decay_rate"] == 0.1


async def test_decay_ephemeral_memories_no_adapter():
    """decay_ephemeral_memories() returns 0 without adapter."""
    service = UserProfileService()

    count = await service.decay_ephemeral_memories("test-user")

    assert count == 0


# =============================================================================
# UserProfileService.get_profile_summary Tests
# =============================================================================

async def test_get_profile_summary():
    """get_profile_summary() returns summary dict."""
    prefs_adapter = MockPreferencesAdapter()
    learned_adapter = MockLearnedContextAdapter(MockLearnedContext(
        expertise={"python": {}, "rust": {}},
        patterns={"concise": {}},
    ))
    main_adapter = MockMainAdapter()
    main_adapter.add_memory(
        user_id="test-user",
        category="fact",
        key="test",
        value="value",
        confidence=0.5,
    )

    service = UserProfileService(
        preferences_adapter=prefs_adapter,
        learned_adapter=learned_adapter,
        main_adapter=main_adapter,
    )

    summary = await service.get_profile_summary("test-user")

    assert summary["user_id"] == "test-user"
    assert summary["expertise_count"] >= 2
    assert summary["has_preferences"] is True
    assert summary["has_learned_context"] is True


# =============================================================================
# UserMemoryAdapter Tests
# =============================================================================

async def test_user_memory_adapter_get_all():
    """UserMemoryAdapter.get_all() returns all memories."""
    main_adapter = MockMainAdapter()
    main_adapter.add_memory(user_id="user1", category="test", key="key1", value="val1", confidence=0.5)
    main_adapter.add_memory(user_id="user1", category="test", key="key2", value="val2", confidence=0.6)

    adapter = UserMemoryAdapter(main_adapter)

    memories = await adapter.get_all("user1")

    assert len(memories) == 2


async def test_user_memory_adapter_get():
    """UserMemoryAdapter.get() returns specific memory."""
    main_adapter = MockMainAdapter()
    main_adapter.add_memory(user_id="user1", category="cat", key="key1", value="val1", confidence=0.5)

    adapter = UserMemoryAdapter(main_adapter)

    memory = await adapter.get("user1", "cat", "key1")

    assert memory is not None
    assert memory["value"] == "val1"


async def test_user_memory_adapter_get_not_found():
    """UserMemoryAdapter.get() returns None for missing."""
    main_adapter = MockMainAdapter()
    adapter = UserMemoryAdapter(main_adapter)

    memory = await adapter.get("user1", "cat", "nonexistent")

    assert memory is None


async def test_user_memory_adapter_query():
    """UserMemoryAdapter.query() filters by category."""
    main_adapter = MockMainAdapter()
    main_adapter.add_memory(user_id="user1", category="cat1", key="k1", value="v1", confidence=0.5)
    main_adapter.add_memory(user_id="user1", category="cat2", key="k2", value="v2", confidence=0.5)

    adapter = UserMemoryAdapter(main_adapter)

    memories = await adapter.query("user1", "cat1")

    assert len(memories) == 1
    assert memories[0]["category"] == "cat1"


async def test_user_memory_adapter_put():
    """UserMemoryAdapter.put() stores memory."""
    main_adapter = MockMainAdapter()
    adapter = UserMemoryAdapter(main_adapter)

    await adapter.put(
        user_id="user1",
        category="test",
        key="key1",
        value="value1",
        confidence=0.8,
    )

    memory = await main_adapter.get_memory("user1", "test", "key1")
    assert memory is not None
    assert memory.value == "value1"


async def test_user_memory_adapter_delete():
    """UserMemoryAdapter.delete() removes memory."""
    main_adapter = MockMainAdapter()
    main_adapter.add_memory(user_id="user1", category="cat", key="key1", value="val1", confidence=0.5)

    adapter = UserMemoryAdapter(main_adapter)

    await adapter.delete("user1", "cat", "key1")

    memory = await main_adapter.get_memory("user1", "cat", "key1")
    assert memory is None


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_user_profile_service():
    """create_user_profile_service() creates instance."""
    service = create_user_profile_service()

    assert isinstance(service, UserProfileService)


def test_create_user_memory_adapter():
    """create_user_memory_adapter() creates instance."""
    main_adapter = MockMainAdapter()

    adapter = create_user_memory_adapter(main_adapter)

    assert isinstance(adapter, UserMemoryAdapter)
