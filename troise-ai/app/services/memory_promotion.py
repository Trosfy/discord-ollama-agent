"""Memory Promotion Service.

Handles the lifecycle of learned context:
- Promotes high-confidence inferences from DynamoDB to Obsidian (ai-learned.yaml)
- Decays ephemeral memories over time
- Reinforces memories when re-observed

Promotion Flow:
1. Agent learns something → stores in DynamoDB with confidence 0.5
2. Re-observed → confidence boosted (max 1.0)
3. confidence >= 0.9 → promote to ai-learned.yaml
4. Old/unused memories → decay and eventually expire

Categories:
- expertise: Skills and knowledge areas
- preference: Communication and style preferences
- project: Project-specific context
- fact: Factual information about the user
"""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.adapters.dynamodb import TroiseMainAdapter, MemoryItem
from app.adapters.obsidian import LearnedContextAdapter

logger = logging.getLogger(__name__)


# Promotion thresholds
PROMOTION_THRESHOLD = 0.9  # Minimum confidence to promote to Obsidian
DECAY_RATE = 0.02  # Confidence decay per cycle
BOOST_AMOUNT = 0.1  # Confidence boost when re-observed
MIN_CONFIDENCE = 0.1  # Minimum confidence before removal


@dataclass
class PromotionResult:
    """Result of a promotion attempt."""
    promoted: int
    decayed: int
    removed: int
    errors: List[str]

    def __str__(self) -> str:
        return (
            f"Promoted: {self.promoted}, "
            f"Decayed: {self.decayed}, "
            f"Removed: {self.removed}"
        )


@dataclass
class MemoryStats:
    """Statistics about memories for a user."""
    total: int
    by_category: Dict[str, int]
    high_confidence: int  # >= PROMOTION_THRESHOLD
    low_confidence: int   # <= MIN_CONFIDENCE
    average_confidence: float


class MemoryPromotionService:
    """
    Service for managing memory lifecycle and promotion.

    Handles the promotion of high-confidence learned context from
    ephemeral DynamoDB storage to permanent Obsidian files.

    Example:
        service = MemoryPromotionService(
            main_adapter=main_adapter,
            learned_adapter=learned_adapter,
        )

        # Check and promote eligible memories
        result = await service.promote_eligible("user123")
        print(f"Promoted {result.promoted} memories")

        # Decay old memories
        result = await service.decay_memories("user123")
    """

    def __init__(
        self,
        main_adapter: TroiseMainAdapter,
        learned_adapter: LearnedContextAdapter,
        promotion_threshold: float = PROMOTION_THRESHOLD,
        decay_rate: float = DECAY_RATE,
        boost_amount: float = BOOST_AMOUNT,
    ):
        """
        Initialize the memory promotion service.

        Args:
            main_adapter: DynamoDB adapter for ephemeral memories.
            learned_adapter: Obsidian adapter for permanent learned context.
            promotion_threshold: Confidence level to trigger promotion.
            decay_rate: Amount to decay confidence per cycle.
            boost_amount: Amount to boost confidence on re-observation.
        """
        self._main_adapter = main_adapter
        self._learned_adapter = learned_adapter
        self._promotion_threshold = promotion_threshold
        self._decay_rate = decay_rate
        self._boost_amount = boost_amount

    async def promote_eligible(self, user_id: str) -> PromotionResult:
        """
        Promote all eligible memories to Obsidian.

        Checks all memories for the user and promotes those that
        have reached the promotion threshold.

        Args:
            user_id: User ID to process.

        Returns:
            PromotionResult with counts and any errors.
        """
        promoted = 0
        errors = []

        # Get all memories for user
        memories = await self._main_adapter.query_memories(user_id)

        for memory in memories:
            if memory.confidence >= self._promotion_threshold:
                try:
                    success = await self._promote_memory(memory)
                    if success:
                        promoted += 1
                        logger.info(
                            f"Promoted {memory.category}/{memory.key} "
                            f"for user {user_id}"
                        )
                except Exception as e:
                    error_msg = f"Failed to promote {memory.key}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        return PromotionResult(
            promoted=promoted,
            decayed=0,
            removed=0,
            errors=errors,
        )

    async def _promote_memory(self, memory: MemoryItem) -> bool:
        """
        Promote a single memory to Obsidian.

        Args:
            memory: The memory to promote.

        Returns:
            True if promoted successfully.
        """
        if memory.category == "expertise":
            return await self._learned_adapter.add_expertise(
                skill=memory.key,
                confidence=memory.confidence,
                learned_by=memory.learned_by or "unknown",
                evidence=memory.evidence or memory.value,
            )

        elif memory.category == "preference":
            return await self._learned_adapter.add_pattern(
                pattern=memory.key,
                confidence=memory.confidence,
                evidence=memory.evidence or memory.value,
            )

        elif memory.category == "project":
            # Parse project context from value
            await self._learned_adapter.update_project(
                project_name=memory.key,
                notes=memory.value,
            )
            return True

        else:
            # For other categories, store in custom section
            context = await self._learned_adapter.load()
            if memory.category not in context.custom:
                context.custom[memory.category] = {}
            context.custom[memory.category][memory.key] = {
                "value": memory.value,
                "confidence": memory.confidence,
                "learned_at": datetime.now().isoformat(),
            }
            await self._learned_adapter.save(context)
            return True

    async def decay_memories(self, user_id: str) -> PromotionResult:
        """
        Apply confidence decay to all memories.

        Memories below MIN_CONFIDENCE after decay are removed.

        Args:
            user_id: User ID to process.

        Returns:
            PromotionResult with decay statistics.
        """
        decayed = 0
        removed = 0
        errors = []

        memories = await self._main_adapter.query_memories(user_id)

        for memory in memories:
            new_confidence = max(0.0, memory.confidence - self._decay_rate)

            if new_confidence < MIN_CONFIDENCE:
                # Remove the memory
                try:
                    await self._main_adapter.delete_memory(
                        user_id=user_id,
                        category=memory.category,
                        key=memory.key,
                    )
                    removed += 1
                    logger.debug(f"Removed low-confidence memory: {memory.key}")
                except Exception as e:
                    errors.append(f"Failed to remove {memory.key}: {e}")
            else:
                # Decay the confidence
                try:
                    await self._main_adapter.boost_memory_confidence(
                        user_id=user_id,
                        category=memory.category,
                        key=memory.key,
                        boost=-self._decay_rate,  # Negative boost = decay
                    )
                    decayed += 1
                except Exception as e:
                    errors.append(f"Failed to decay {memory.key}: {e}")

        if decayed > 0 or removed > 0:
            logger.info(
                f"Decayed {decayed}, removed {removed} memories for {user_id}"
            )

        return PromotionResult(
            promoted=0,
            decayed=decayed,
            removed=removed,
            errors=errors,
        )

    async def reinforce_memory(
        self,
        user_id: str,
        category: str,
        key: str,
        boost: Optional[float] = None,
    ) -> float:
        """
        Reinforce a memory by boosting its confidence.

        Called when the same information is observed again.

        Args:
            user_id: User ID.
            category: Memory category.
            key: Memory key.
            boost: Amount to boost (default: self._boost_amount).

        Returns:
            New confidence level.
        """
        boost = boost or self._boost_amount

        new_confidence = await self._main_adapter.boost_memory_confidence(
            user_id=user_id,
            category=category,
            key=key,
            boost=boost,
        )

        logger.debug(
            f"Reinforced {category}/{key} for {user_id}: "
            f"new confidence = {new_confidence}"
        )

        # Check if should promote
        if new_confidence >= self._promotion_threshold:
            memory = await self._main_adapter.get_memory(user_id, category, key)
            if memory:
                await self._promote_memory(memory)
                logger.info(
                    f"Auto-promoted {category}/{key} after reinforcement"
                )

        return new_confidence

    async def get_memory_stats(self, user_id: str) -> MemoryStats:
        """
        Get statistics about memories for a user.

        Args:
            user_id: User ID.

        Returns:
            MemoryStats with counts and averages.
        """
        memories = await self._main_adapter.query_memories(user_id)

        by_category: Dict[str, int] = {}
        total_confidence = 0.0
        high_confidence = 0
        low_confidence = 0

        for memory in memories:
            by_category[memory.category] = by_category.get(memory.category, 0) + 1
            total_confidence += memory.confidence

            if memory.confidence >= self._promotion_threshold:
                high_confidence += 1
            if memory.confidence <= MIN_CONFIDENCE:
                low_confidence += 1

        total = len(memories)
        avg_confidence = total_confidence / total if total > 0 else 0.0

        return MemoryStats(
            total=total,
            by_category=by_category,
            high_confidence=high_confidence,
            low_confidence=low_confidence,
            average_confidence=avg_confidence,
        )

    async def sync_from_obsidian(self, user_id: str) -> int:
        """
        Sync high-confidence items from Obsidian back to DynamoDB.

        Useful for ensuring consistency after manual edits to ai-learned.yaml.

        Args:
            user_id: User ID.

        Returns:
            Number of items synced.
        """
        synced = 0
        context = await self._learned_adapter.load()

        # Sync expertise
        for skill in context.expertise_areas:
            await self._main_adapter.put_memory(
                user_id=user_id,
                category="expertise",
                key=skill.skill,
                value=skill.evidence,
                confidence=skill.confidence,
                source="synced",
                learned_by=skill.learned_by,
            )
            synced += 1

        # Sync patterns
        for pattern in context.communication_patterns:
            await self._main_adapter.put_memory(
                user_id=user_id,
                category="preference",
                key=pattern.pattern,
                value=pattern.evidence,
                confidence=pattern.confidence,
                source="synced",
            )
            synced += 1

        # Sync projects
        for name, project in context.project_context.items():
            await self._main_adapter.put_memory(
                user_id=user_id,
                category="project",
                key=name,
                value=project.notes or "",
                confidence=1.0,  # Explicitly set = high confidence
                source="synced",
            )
            synced += 1

        logger.info(f"Synced {synced} items from Obsidian for {user_id}")
        return synced

    async def run_maintenance_cycle(self, user_id: str) -> PromotionResult:
        """
        Run a full maintenance cycle for a user.

        1. Promote eligible memories
        2. Decay old memories
        3. Remove expired memories

        Args:
            user_id: User ID.

        Returns:
            Combined PromotionResult.
        """
        # Promote first
        promote_result = await self.promote_eligible(user_id)

        # Then decay
        decay_result = await self.decay_memories(user_id)

        # Combine results
        return PromotionResult(
            promoted=promote_result.promoted,
            decayed=decay_result.decayed,
            removed=decay_result.removed,
            errors=promote_result.errors + decay_result.errors,
        )


def create_memory_promotion_service(
    main_adapter: TroiseMainAdapter,
    learned_adapter: LearnedContextAdapter,
) -> MemoryPromotionService:
    """
    Factory function to create a memory promotion service.

    Args:
        main_adapter: DynamoDB adapter for ephemeral memories.
        learned_adapter: Obsidian adapter for permanent learned context.

    Returns:
        Configured MemoryPromotionService instance.
    """
    return MemoryPromotionService(
        main_adapter=main_adapter,
        learned_adapter=learned_adapter,
    )
