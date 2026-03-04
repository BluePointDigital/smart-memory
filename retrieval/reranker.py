"""Candidate memory re-ranking for retrieval context selection."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_engine.schemas import LongTermMemory


@dataclass(frozen=True)
class RetrievalCandidate:
    memory: LongTermMemory
    vector_score: float


@dataclass(frozen=True)
class RankedCandidate:
    memory: LongTermMemory
    score: float
    vector_score: float


def _tokenize(text: str) -> set[str]:
    return {token.lower().strip('.,!?;:()[]{}"\'') for token in text.split() if len(token) >= 3}


def _overlap_fraction(left: set[str], right: set[str]) -> float:
    if not left:
        return 0.0
    return len(left & right) / len(left)


def rerank_candidates(
    *,
    user_message: str,
    candidates: list[RetrievalCandidate],
    query_entities: list[str],
    top_k: int = 5,
) -> list[RankedCandidate]:
    query_terms = _tokenize(user_message)
    query_entity_set = {entity.lower() for entity in query_entities}

    ranked: list[RankedCandidate] = []
    for candidate in candidates:
        memory = candidate.memory
        content_terms = _tokenize(memory.content)
        memory_entities = {entity.lower() for entity in memory.entities}

        keyword_overlap = _overlap_fraction(query_terms, content_terms)
        entity_overlap = _overlap_fraction(query_entity_set, memory_entities)

        score = (
            (candidate.vector_score * 0.45)
            + (memory.importance * 0.25)
            + (keyword_overlap * 0.20)
            + (entity_overlap * 0.10)
        )

        ranked.append(
            RankedCandidate(memory=memory, score=min(1.0, max(0.0, score)), vector_score=candidate.vector_score)
        )

    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked[:top_k]
