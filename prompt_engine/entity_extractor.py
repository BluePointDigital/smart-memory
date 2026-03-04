"""Entity extraction helpers for memory retrieval queries.

This is intentionally lightweight for Phase 0/1 and can be swapped for an LLM/NER extractor later.
"""

from __future__ import annotations

import re
from typing import Iterable


TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{2,}")
STOPWORDS = {
    "the",
    "and",
    "for",
    "that",
    "with",
    "this",
    "from",
    "have",
    "what",
    "when",
    "where",
    "which",
    "about",
    "would",
    "should",
    "could",
    "please",
    "after",
    "before",
    "project",
    "memory",
}


def _normalize_entity(token: str) -> str:
    return token.strip().lower().replace("-", "_")


def extract_entities(
    current_user_message: str,
    conversation_history: str = "",
    active_projects: Iterable[str] | None = None,
    max_entities: int = 20,
) -> list[str]:
    """Extract canonical entity ids from user and immediate context."""

    candidates: list[str] = []

    for token in TOKEN_PATTERN.findall(current_user_message):
        entity = _normalize_entity(token)
        if entity not in STOPWORDS:
            candidates.append(entity)

    for token in TOKEN_PATTERN.findall(conversation_history):
        entity = _normalize_entity(token)
        if entity not in STOPWORDS:
            candidates.append(entity)

    if active_projects:
        for project in active_projects:
            for token in TOKEN_PATTERN.findall(project):
                entity = _normalize_entity(token)
                if entity not in STOPWORDS:
                    candidates.append(entity)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)
        if len(deduped) >= max_entities:
            break

    return deduped
