"""Reflection agent for pattern extraction and insight generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from prompt_engine.schemas import (
    BeliefMemory,
    InsightObject,
    LongTermMemory,
    MemorySource,
    MemoryType,
)


PREFERENCE_TERMS = (
    "prefer",
    "preference",
    "value",
    "principle",
    "always",
    "never",
)


@dataclass(frozen=True)
class ReflectionResult:
    synthesized_beliefs: list[BeliefMemory]
    insights: list[InsightObject]


class ReflectionAgent:
    """Deterministic reflection pass over recent memories."""

    def analyze(self, memories: list[LongTermMemory]) -> ReflectionResult:
        now = datetime.now(timezone.utc)
        beliefs: list[BeliefMemory] = []
        insights: list[InsightObject] = []

        for memory in memories:
            text = memory.content.lower()
            if memory.type in (MemoryType.EPISODIC, MemoryType.SEMANTIC) and any(
                term in text for term in PREFERENCE_TERMS
            ):
                beliefs.append(
                    BeliefMemory(
                        content=f"Inferred belief from reflection: {memory.content}",
                        importance=min(1.0, max(0.55, memory.importance)),
                        created_at=now,
                        last_accessed=now,
                        access_count=0,
                        schema_version="2.0",
                        entities=memory.entities,
                        relations=memory.relations,
                        emotional_valence=memory.emotional_valence,
                        emotional_intensity=memory.emotional_intensity,
                        source=MemorySource.REFLECTION,
                        confidence=min(1.0, max(0.55, memory.importance)),
                        reinforced_count=1,
                    )
                )

        entity_frequency: dict[str, int] = {}
        for memory in memories:
            for entity in memory.entities:
                entity_frequency[entity] = entity_frequency.get(entity, 0) + 1

        frequent_entities = sorted(
            [entity for entity, count in entity_frequency.items() if count >= 2]
        )
        if frequent_entities:
            confidence = min(0.90, 0.60 + (0.05 * len(frequent_entities)))
            insight = InsightObject(
                content=(
                    "Reflection pattern: repeated focus on entities "
                    + ", ".join(frequent_entities)
                ),
                confidence=confidence,
                source_memory_ids=[memory.id for memory in memories[:8]],
                generated_at=now,
            )
            insights.append(insight)

        return ReflectionResult(synthesized_beliefs=beliefs, insights=insights)
