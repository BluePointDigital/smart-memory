"""Construct phase-1 memory objects from classified interactions."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Iterable

from entities import EntityAliasResolver
from prompt_engine.entity_extractor import extract_entities
from prompt_engine.schemas import (
    BeliefMemory,
    EpisodicMemory,
    GoalMemory,
    GoalStatus,
    LongTermMemory,
    MemorySource,
    MemoryType,
    RelationTriple,
    SemanticMemory,
)


POSITIVE_WORDS = {
    "good",
    "great",
    "excellent",
    "happy",
    "love",
    "win",
    "success",
    "progress",
}

NEGATIVE_WORDS = {
    "bad",
    "poor",
    "frustrated",
    "hate",
    "blocked",
    "fail",
    "issue",
    "problem",
}

RELATION_PATTERN = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_\-]{2,})\s+"
    r"(uses|depends_on|blocks|supports|interacts_with|relates_to)\s+"
    r"([A-Za-z][A-Za-z0-9_\-]{2,})\b",
    flags=re.IGNORECASE,
)


def _normalize_entity(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def detect_relations(text: str, resolver: EntityAliasResolver | None = None) -> list[RelationTriple]:
    relations: list[RelationTriple] = []
    seen: set[tuple[str, str, str]] = set()

    for subject, predicate, obj in RELATION_PATTERN.findall(text):
        if resolver:
            subject_id = resolver.resolve(subject)
            object_id = resolver.resolve(obj)
        else:
            subject_id = _normalize_entity(subject)
            object_id = _normalize_entity(obj)

        triple = (
            subject_id,
            predicate.strip().lower(),
            object_id,
        )
        if triple in seen:
            continue

        seen.add(triple)
        relations.append(
            RelationTriple(subject=triple[0], predicate=triple[1], object=triple[2])
        )

    return relations


def emotional_metadata(text: str) -> tuple[float, float]:
    tokens = [token.strip(".,!?;:").lower() for token in text.split()]
    if not tokens:
        return 0.0, 0.0

    positive = sum(1 for token in tokens if token in POSITIVE_WORDS)
    negative = sum(1 for token in tokens if token in NEGATIVE_WORDS)

    valence_raw = (positive - negative) / max(1, positive + negative)
    intensity_raw = (positive + negative) / max(1, len(tokens) / 2)

    valence = max(-1.0, min(1.0, valence_raw))
    intensity = max(0.0, min(1.0, intensity_raw))
    return valence, intensity


def parse_source(source: str | None) -> MemorySource:
    if source is None:
        return MemorySource.CONVERSATION

    normalized = source.strip().lower()
    for enum_value in MemorySource:
        if enum_value.value == normalized:
            return enum_value

    return MemorySource.CONVERSATION


def build_memory_object(
    *,
    memory_type: MemoryType,
    user_message: str,
    assistant_message: str = "",
    importance: float,
    source: str | None = None,
    timestamp: datetime | None = None,
    participants: Iterable[str] | None = None,
    active_projects: Iterable[str] | None = None,
    entities_override: list[str] | None = None,
    entity_resolver: EntityAliasResolver | None = None,
) -> LongTermMemory:
    """Create a typed long-term memory object using phase-1 schemas."""

    timestamp = timestamp or datetime.now(timezone.utc)
    text_for_entities = f"{user_message} {assistant_message}".strip()

    resolver = entity_resolver or EntityAliasResolver()

    if entities_override is not None:
        entities = resolver.canonicalize_many(entities_override)
    else:
        extracted = extract_entities(
            current_user_message=user_message,
            conversation_history=assistant_message,
            active_projects=active_projects,
        )
        entities = resolver.canonicalize_many(extracted)

    relations = detect_relations(text_for_entities, resolver=resolver)
    valence, intensity = emotional_metadata(text_for_entities)
    memory_source = parse_source(source)

    common = {
        "content": user_message.strip(),
        "importance": importance,
        "created_at": timestamp,
        "last_accessed": timestamp,
        "access_count": 0,
        "schema_version": "2.0",
        "entities": entities,
        "relations": relations,
        "emotional_valence": valence,
        "emotional_intensity": intensity,
        "source": memory_source,
    }

    if memory_type == MemoryType.SEMANTIC:
        confidence = min(1.0, max(0.45, importance))
        return SemanticMemory(confidence=confidence, **common)

    if memory_type == MemoryType.BELIEF:
        confidence = min(1.0, max(0.50, importance))
        return BeliefMemory(confidence=confidence, reinforced_count=1, **common)

    if memory_type == MemoryType.GOAL:
        priority = min(1.0, max(0.45, importance))
        return GoalMemory(status=GoalStatus.ACTIVE, priority=priority, **common)

    participant_ids = [resolver.resolve(participant) for participant in (participants or ["user", "assistant"])]
    return EpisodicMemory(participants=participant_ids, **common)
