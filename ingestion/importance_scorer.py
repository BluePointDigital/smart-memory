"""Importance scoring for long-term memory eligibility."""

from __future__ import annotations

from dataclasses import dataclass


DECISION_TERMS = {
    "decide",
    "decision",
    "agreed",
    "conclusion",
    "final",
    "resolved",
}

GOAL_TERMS = {
    "goal",
    "objective",
    "plan",
    "milestone",
    "todo",
    "roadmap",
    "start",
    "begin",
}

PREFERENCE_TERMS = {
    "prefer",
    "preference",
    "value",
    "principle",
    "always",
    "never",
}

EMOTIONAL_TERMS = {
    "love",
    "hate",
    "frustrated",
    "excited",
    "worried",
    "critical",
    "important",
}


@dataclass(frozen=True)
class ImportanceBreakdown:
    score: float
    components: dict[str, float]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def score_importance(
    *,
    user_message: str,
    assistant_message: str = "",
    entity_count: int = 0,
) -> ImportanceBreakdown:
    """Compute deterministic importance score in [0.0, 1.0]."""

    text = f"{user_message} {assistant_message}".strip().lower()
    words = user_message.split()

    length_component = _clamp(len(words) / 40.0, 0.0, 0.25)
    entity_component = _clamp(entity_count * 0.03, 0.0, 0.20)
    question_component = 0.12 if "?" in user_message else 0.0

    decision_component = 0.20 if any(term in text for term in DECISION_TERMS) else 0.0
    goal_component = 0.18 if any(term in text for term in GOAL_TERMS) else 0.0
    preference_component = 0.16 if any(term in text for term in PREFERENCE_TERMS) else 0.0

    emotional_hits = sum(1 for term in EMOTIONAL_TERMS if term in text)
    emotional_component = _clamp(emotional_hits * 0.04, 0.0, 0.16)

    components = {
        "length": length_component,
        "entities": entity_component,
        "question": question_component,
        "decision": decision_component,
        "goal": goal_component,
        "preference": preference_component,
        "emotion": emotional_component,
    }

    score = _clamp(sum(components.values()))
    return ImportanceBreakdown(score=score, components=components)
