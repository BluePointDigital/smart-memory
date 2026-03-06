"""Memory type classifier for ingestion."""

from __future__ import annotations

from prompt_engine.schemas import MemoryType


GOAL_TERMS = {
    "goal",
    "objective",
    "plan",
    "milestone",
    "todo",
    "launch",
    "ship",
    "roadmap",
}

PREFERENCE_TERMS = {
    "prefer",
    "i like",
    "i dislike",
    "favorite",
    "favourite",
    "rather than",
}

IDENTITY_TERMS = {
    "i am",
    "my role",
    "i work at",
    "i live in",
    "i'm",
}

TASK_STATE_TERMS = {
    "in progress",
    "blocked",
    "resolved",
    "completed",
    "next step",
    "open issue",
    "abandoned",
}

BELIEF_TERMS = {
    "i believe",
    "principle",
    "usually",
    "always",
    "never",
    "remember that",
}

SEMANTIC_TERMS = {
    "is",
    "are",
    "means",
    "defined",
    "fact",
}

EPISODIC_TERMS = {
    "happened",
    "worked on",
    "implemented",
    "reviewed",
    "discussed",
    "decided",
}


def classify_memory_type(
    *,
    user_message: str,
    assistant_message: str = "",
) -> MemoryType:
    """Classify an interaction into the best-fit v3 memory type."""

    text = f"{user_message} {assistant_message}".strip().lower()

    if any(term in text for term in PREFERENCE_TERMS):
        return MemoryType.PREFERENCE

    if any(term in text for term in IDENTITY_TERMS):
        return MemoryType.IDENTITY

    if any(term in text for term in TASK_STATE_TERMS):
        return MemoryType.TASK_STATE

    if any(term in text for term in GOAL_TERMS):
        return MemoryType.GOAL

    if any(term in text for term in BELIEF_TERMS):
        return MemoryType.BELIEF

    if any(term in text for term in EPISODIC_TERMS):
        return MemoryType.EPISODIC

    if any(term in text for term in SEMANTIC_TERMS):
        return MemoryType.SEMANTIC

    return MemoryType.EPISODIC
