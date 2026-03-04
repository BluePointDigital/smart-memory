"""Memory type classifier for ingestion."""

from __future__ import annotations

from prompt_engine.schemas import MemoryType


GOAL_TERMS = {
    "goal",
    "objective",
    "plan",
    "milestone",
    "todo",
    "start",
    "begin",
    "launch",
}

BELIEF_TERMS = {
    "prefer",
    "i like",
    "i dislike",
    "value",
    "principle",
    "usually",
    "always",
    "never",
}

SEMANTIC_TERMS = {
    "is",
    "are",
    "means",
    "defined",
    "fact",
    "remember that",
}

EPISODIC_TERMS = {
    "completed",
    "finished",
    "did",
    "happened",
    "worked on",
    "implemented",
}


def classify_memory_type(
    *,
    user_message: str,
    assistant_message: str = "",
) -> MemoryType:
    """Classify an interaction into episodic, semantic, belief, or goal."""

    text = f"{user_message} {assistant_message}".strip().lower()

    if any(term in text for term in GOAL_TERMS):
        return MemoryType.GOAL

    if any(term in text for term in BELIEF_TERMS):
        return MemoryType.BELIEF

    if any(term in text for term in EPISODIC_TERMS):
        return MemoryType.EPISODIC

    if any(term in text for term in SEMANTIC_TERMS):
        return MemoryType.SEMANTIC

    return MemoryType.EPISODIC
