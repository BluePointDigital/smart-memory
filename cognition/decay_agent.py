"""Decay agent for long-term memory importance aging."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math

from prompt_engine.schemas import LongTermMemory


@dataclass(frozen=True)
class DecayResult:
    updated_memories: list[LongTermMemory]
    archive_ids: list[str]
    vector_prune_ids: list[str]


class DecayAgent:
    """Apply deterministic importance decay based on access recency."""

    def decay(
        self,
        memories: list[LongTermMemory],
        *,
        now: datetime | None = None,
        half_life_days: float = 45.0,
        archive_threshold: float = 0.10,
        vector_prune_threshold: float = 0.10,
    ) -> DecayResult:
        now = now or datetime.now(timezone.utc)
        updated: list[LongTermMemory] = []
        archive_ids: list[str] = []
        vector_prune_ids: list[str] = []

        decay_lambda = math.log(2.0) / max(1.0, half_life_days)

        for memory in memories:
            age_days = max(0.0, (now - memory.last_accessed).total_seconds() / 86400.0)
            decayed_importance = memory.importance * math.exp(-decay_lambda * age_days)
            decayed_importance = max(0.0, min(1.0, decayed_importance))

            if decayed_importance < archive_threshold:
                archive_ids.append(str(memory.id))

            if decayed_importance < vector_prune_threshold:
                vector_prune_ids.append(str(memory.id))

            updated_memory = memory.model_copy(update={"importance": decayed_importance})
            updated.append(updated_memory)

        return DecayResult(
            updated_memories=updated,
            archive_ids=archive_ids,
            vector_prune_ids=vector_prune_ids,
        )
