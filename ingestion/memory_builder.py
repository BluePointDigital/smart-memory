"""Construct v3.1 memory objects from transcript-backed interactions."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Iterable

from entities import EntityAliasResolver
from prompt_engine.entity_extractor import extract_entities
from prompt_engine.schemas import (
    BeliefMemory,
    DecayPolicy,
    EpisodicMemory,
    GoalMemory,
    GoalStatus,
    IdentityMemory,
    LaneName,
    LongTermMemory,
    MemorySource,
    MemoryType,
    PreferenceMemory,
    RelationTriple,
    SemanticMemory,
    TaskStateMemory,
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

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "have",
    "will",
    "your",
    "about",
}

RELATION_PATTERN = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_\-]{2,})\s+"
    r"(uses|depends_on|blocks|supports|interacts_with|relates_to|blocked_by)\s+"
    r"([A-Za-z][A-Za-z0-9_\-]{2,})\b",
    flags=re.IGNORECASE,
)


def _normalize_entity(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def _extract_keywords(text: str, *, max_keywords: int = 8) -> list[str]:
    tokens = []
    for token in text.lower().split():
        cleaned = token.strip(".,!?;:()[]{}\"'")
        if len(cleaned) < 3 or cleaned in STOPWORDS:
            continue
        if cleaned not in tokens:
            tokens.append(cleaned)
        if len(tokens) >= max_keywords:
            break
    return tokens


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

        triple = (subject_id, predicate.strip().lower(), object_id)
        if triple in seen:
            continue

        seen.add(triple)
        relations.append(RelationTriple(subject=triple[0], predicate=triple[1], object=triple[2]))

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


def _default_lane_eligibility(memory_type: MemoryType) -> list[LaneName]:
    if memory_type in {MemoryType.IDENTITY, MemoryType.PREFERENCE}:
        return [LaneName.CORE, LaneName.RETRIEVED]
    if memory_type in {MemoryType.GOAL, MemoryType.TASK_STATE}:
        return [LaneName.WORKING, LaneName.RETRIEVED]
    return [LaneName.RETRIEVED]


def _default_confidence(memory_type: MemoryType, importance: float) -> float:
    floor = {
        MemoryType.IDENTITY: 0.75,
        MemoryType.PREFERENCE: 0.70,
        MemoryType.GOAL: 0.60,
        MemoryType.TASK_STATE: 0.60,
        MemoryType.BELIEF: 0.55,
        MemoryType.SEMANTIC: 0.50,
        MemoryType.EPISODIC: 0.45,
    }.get(memory_type, 0.50)
    return min(1.0, max(floor, importance))


def _decay_policy(memory_type: MemoryType, text: str) -> DecayPolicy:
    lowered = text.lower()
    if memory_type == MemoryType.GOAL:
        return DecayPolicy.GOAL_COMPLETION
    if memory_type == MemoryType.TASK_STATE:
        return DecayPolicy.SESSION_BOUND
    if any(term in lowered for term in {"tomorrow", "next week", "appointment", "temporary"}):
        return DecayPolicy.TIME_SENSITIVE
    return DecayPolicy.NONE


def _retrieval_tags(memory_type: MemoryType, text: str) -> list[str]:
    lowered = text.lower()
    tags: list[str] = []
    if memory_type == MemoryType.TASK_STATE:
        for marker, tag in {
            "blocked": "blocker",
            "next step": "next_step",
            "open issue": "open_issue",
            "decided": "recent_decision",
            "completed": "completed",
        }.items():
            if marker in lowered and tag not in tags:
                tags.append(tag)
    if memory_type == MemoryType.GOAL and "launch" in lowered:
        tags.append("project_goal")
    return tags


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
    source_session_id: str | None = None,
    source_message_ids: list[str] | None = None,
    derivation_method: str = "transcript_message",
    synthetic: bool = False,
    explanation: str = "ingested from transcript",
) -> LongTermMemory:
    """Create a typed long-term memory object using v3.1 schemas."""

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
    confidence = _default_confidence(memory_type, importance)
    message_ids = list(source_message_ids or [])

    common = {
        "content": user_message.strip(),
        "importance_score": importance,
        "created_at": timestamp,
        "updated_at": timestamp,
        "last_accessed_at": timestamp,
        "access_count": 0,
        "schema_version": "3.1",
        "entities": entities,
        "keywords": _extract_keywords(text_for_entities),
        "confidence": confidence,
        "status": "active",
        "revision_of": None,
        "supersedes": [],
        "valid_from": timestamp,
        "valid_to": None,
        "decay_policy": _decay_policy(memory_type, text_for_entities),
        "lane_eligibility": _default_lane_eligibility(memory_type),
        "pinned_priority": min(1.0, max(0.0, importance)),
        "retrieval_tags": _retrieval_tags(memory_type, text_for_entities),
        "explanation": explanation,
        "relations": relations,
        "emotional_valence": valence,
        "emotional_intensity": intensity,
        "source": memory_source,
        "source_session_id": source_session_id,
        "source_message_ids": message_ids,
        "derivation_method": derivation_method,
        "evidence_summary": user_message.strip()[:240],
        "evidence_count": len(message_ids),
        "synthetic": synthetic,
    }

    if memory_type == MemoryType.SEMANTIC:
        return SemanticMemory(**common)

    if memory_type == MemoryType.BELIEF:
        return BeliefMemory(reinforced_count=1, **common)

    if memory_type == MemoryType.GOAL:
        return GoalMemory(goal_status=GoalStatus.ACTIVE, priority=min(1.0, max(0.45, importance)), **common)

    if memory_type == MemoryType.PREFERENCE:
        return PreferenceMemory(**common)

    if memory_type == MemoryType.IDENTITY:
        return IdentityMemory(**common)

    if memory_type == MemoryType.TASK_STATE:
        return TaskStateMemory(**common)

    participant_ids = [resolver.resolve(participant) for participant in (participants or ["user", "assistant"])]
    return EpisodicMemory(participants=participant_ids, **common)
