"""Fast rule-based filtering for memory-worthy interactions."""

from __future__ import annotations

from dataclasses import dataclass
import re


EMOTIONAL_TERMS = {
    "love",
    "hate",
    "frustrated",
    "excited",
    "worried",
    "concerned",
    "happy",
    "upset",
    "angry",
    "important",
    "critical",
}

DECISION_TERMS = {
    "prefer",
    "like",
    "dislike",
    "avoid",
    "goal",
    "launch",
    "launched",
    "blocked",
    "completed",
    "resolved",
    "abandoned",
    "decided",
    "now",
    "instead",
    "changed",
    "stopped",
    "switched",
}

NAMED_ENTITY_PATTERN = re.compile(r"\b[A-Z][a-z]{2,}\b")
PROJECT_PATTERN = re.compile(r"\bproj[_\-][a-z0-9_\-]+\b", flags=re.IGNORECASE)


@dataclass(frozen=True)
class HeuristicDecision:
    should_continue: bool
    triggers: list[str]


def evaluate_heuristics(
    *,
    user_message: str,
    assistant_message: str = "",
    system_generated_insight: bool = False,
    min_words: int = 8,
) -> HeuristicDecision:
    """Check lightweight triggers before heavier ingestion steps."""

    triggers: list[str] = []
    text = f"{user_message} {assistant_message}".strip()
    words = user_message.split()
    text_lower = text.lower()

    if len(words) >= min_words:
        triggers.append("length_threshold")

    if NAMED_ENTITY_PATTERN.search(text):
        triggers.append("named_entity")

    if PROJECT_PATTERN.search(text):
        triggers.append("project_reference")

    if any(term in text_lower for term in EMOTIONAL_TERMS):
        triggers.append("emotional_language")

    if any(term in text_lower for term in DECISION_TERMS):
        triggers.append("decision_marker")

    if "?" in user_message:
        triggers.append("user_question")

    if system_generated_insight:
        triggers.append("system_generated_insight")

    return HeuristicDecision(should_continue=bool(triggers), triggers=triggers)
