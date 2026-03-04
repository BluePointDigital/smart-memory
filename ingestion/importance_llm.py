"""Optional LLM importance scorer contract.

The ingestion pipeline calls this only after lightweight heuristic gating.
"""

from __future__ import annotations

from typing import Protocol


class ImportanceLLMScorer(Protocol):
    def score_importance(
        self,
        *,
        user_message: str,
        assistant_message: str,
        heuristic_score: float,
        entity_count: int,
        triggers: list[str],
    ) -> float:
        """Return refined importance in [0.0, 1.0]."""


def clamp_importance(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
