"""Entity detection helpers for retrieval biasing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from entities import EntityAliasResolver
from prompt_engine.entity_extractor import extract_entities


@dataclass(frozen=True)
class EntityDetectionResult:
    entities: list[str]


def detect_entities_for_retrieval(
    *,
    user_message: str,
    conversation_history: str = "",
    known_entities: Iterable[str] | None = None,
    resolver: EntityAliasResolver | None = None,
    max_entities: int = 25,
) -> EntityDetectionResult:
    resolver = resolver or EntityAliasResolver()

    extracted = extract_entities(
        current_user_message=user_message,
        conversation_history=conversation_history,
        active_projects=known_entities,
        max_entities=max_entities,
    )

    merged = list(extracted)
    if known_entities:
        merged.extend(list(known_entities))

    canonical = resolver.canonicalize_many(merged)
    return EntityDetectionResult(entities=canonical[:max_entities])
