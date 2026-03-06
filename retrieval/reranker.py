"""Candidate memory re-ranking for retrieval context selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from prompt_engine.schemas import BaseMemory, MemoryStatus
from smart_memory_config import RetrievalWeightsConfig


@dataclass(frozen=True)
class RetrievalCandidate:
    memory: BaseMemory
    vector_score: float
    lane_boost: float = 0.0


@dataclass(frozen=True)
class RankedCandidate:
    memory: BaseMemory
    score: float
    vector_score: float


STATUS_PENALTIES = {
    MemoryStatus.ACTIVE: 0.0,
    MemoryStatus.UNCERTAIN: -0.20,
    MemoryStatus.ARCHIVED: -0.35,
    MemoryStatus.SUPERSEDED: -1.0,
    MemoryStatus.EXPIRED: -1.0,
    MemoryStatus.REJECTED: -1.0,
}


def _tokenize(text: str) -> set[str]:
    return {token.lower().strip('.,!?;:()[]{}"\'') for token in text.split() if len(token) >= 3}


def _overlap_fraction(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left)


def rerank_candidates(
    *,
    user_message: str,
    candidates: list[RetrievalCandidate],
    query_entities: list[str],
    weights: RetrievalWeightsConfig | None = None,
    top_k: int = 5,
    now: datetime | None = None,
) -> list[RankedCandidate]:
    weights = weights or RetrievalWeightsConfig()
    now = now or datetime.now(timezone.utc)
    query_terms = _tokenize(user_message)
    query_entity_set = {entity.lower() for entity in query_entities}

    ranked: list[RankedCandidate] = []
    for candidate in candidates:
        memory = candidate.memory
        content_terms = _tokenize(memory.content)
        memory_entities = {entity.lower() for entity in memory.entities}

        keyword_overlap = _overlap_fraction(query_terms, content_terms)
        entity_overlap = _overlap_fraction(query_entity_set, memory_entities)
        recency_score = 1.0 if memory.updated_at and memory.updated_at >= now - timedelta(days=7) else 0.0
        temporal_validity = 1.0
        if memory.valid_to is not None and memory.valid_to < now:
            temporal_validity = 0.0

        score = (
            (candidate.vector_score * weights.semantic_similarity)
            + (keyword_overlap * weights.keyword_overlap)
            + (entity_overlap * weights.entity_overlap)
            + (memory.importance_score * weights.importance)
            + (recency_score * weights.recency)
            + (candidate.lane_boost * weights.lane_boost)
            + (temporal_validity * weights.temporal_validity)
            + STATUS_PENALTIES.get(memory.status, 0.0)
        )

        ranked.append(RankedCandidate(memory=memory, score=min(1.0, max(0.0, score)), vector_score=candidate.vector_score))

    ranked.sort(
        key=lambda item: (
            item.score,
            item.memory.importance_score,
            item.memory.updated_at or item.memory.created_at,
            str(item.memory.id),
        ),
        reverse=True,
    )
    return ranked[:top_k]
