"""Memory re-ranking for candidate long-term memories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .schemas import LongTermMemory


@dataclass
class RankedMemory:
    memory: LongTermMemory
    score: float


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in text.split() if len(token) >= 3}


def _score_memory(
    memory: LongTermMemory,
    query_terms: set[str],
    entities: set[str],
    now: datetime,
) -> float:
    content_tokens = _tokenize(memory.content)
    memory_entities = {entity.lower() for entity in memory.entities}

    if query_terms:
        keyword_overlap = len(query_terms & content_tokens) / len(query_terms)
    else:
        keyword_overlap = 0.0

    if entities:
        entity_overlap = len(entities & memory_entities) / len(entities)
    else:
        entity_overlap = 0.0

    recency_boost = 0.0
    if memory.last_accessed >= now - timedelta(days=7):
        recency_boost = 0.05

    score = (
        (memory.importance * 0.45)
        + (keyword_overlap * 0.35)
        + (entity_overlap * 0.20)
        + recency_boost
    )

    return min(1.0, max(0.0, score))


def rerank_with_scores(
    candidates: list[LongTermMemory],
    query: str,
    entities: list[str],
    *,
    top_k: int = 5,
    minimum_score: float = 0.10,
    now: datetime | None = None,
) -> list[RankedMemory]:
    """Score and sort candidate memories."""

    now = now or datetime.now(timezone.utc)
    query_terms = _tokenize(query)
    entity_set = {entity.lower() for entity in entities}

    ranked: list[RankedMemory] = []
    for candidate in candidates:
        score = _score_memory(candidate, query_terms, entity_set, now)
        if score >= minimum_score:
            ranked.append(RankedMemory(memory=candidate, score=score))

    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked[:top_k]


def rerank_memories(
    candidates: list[LongTermMemory],
    query: str,
    entities: list[str],
    *,
    top_k: int = 5,
    minimum_score: float = 0.10,
    now: datetime | None = None,
) -> list[LongTermMemory]:
    """Return only selected memories after ranking."""

    ranked = rerank_with_scores(
        candidates,
        query,
        entities,
        top_k=top_k,
        minimum_score=minimum_score,
        now=now,
    )
    return [item.memory for item in ranked]
