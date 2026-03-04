"""Associative insight generation from high-importance memories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations

from prompt_engine.schemas import InsightObject, LongTermMemory


@dataclass(frozen=True)
class AssociativeInsightResult:
    insights: list[InsightObject]


class AssociativeInsightGenerator:
    """Generate deterministic cross-memory insights with curiosity triggers."""

    def _familiarity_score(self, memory: LongTermMemory) -> float:
        # Access count is used as a light familiarity proxy when no richer signal exists.
        return min(1.0, memory.access_count / 10.0)

    def _curiosity_score(self, memory: LongTermMemory) -> float:
        familiarity = self._familiarity_score(memory)
        return max(0.0, min(1.0, memory.emotional_intensity * (1.0 - familiarity)))

    def _build_working_question(self, memory: LongTermMemory) -> str:
        snippet = memory.content.strip().replace("\n", " ")[:120]
        lowered = memory.content.lower()

        if "frustrat" in lowered:
            return f"User was very frustrated by '{snippet}'. Did they resolve it?"
        if "blocked" in lowered or "issue" in lowered or "problem" in lowered:
            return f"There was a high-emotion blocker around '{snippet}'. Was it unblocked?"

        return f"High emotional signal detected around '{snippet}'. What changed since then?"

    def generate(self, memories: list[LongTermMemory]) -> AssociativeInsightResult:
        now = datetime.now(timezone.utc)
        high_priority = sorted(memories, key=lambda item: item.importance, reverse=True)[:8]

        insights: list[InsightObject] = []

        for left, right in combinations(high_priority, 2):
            shared_entities = sorted(set(left.entities) & set(right.entities))
            if not shared_entities and abs(left.importance - right.importance) > 0.25:
                continue

            confidence = 0.55
            if shared_entities:
                confidence += min(0.30, 0.08 * len(shared_entities))
            confidence += min(0.10, ((left.importance + right.importance) / 2) * 0.10)
            confidence = min(0.95, confidence)

            insight_text = (
                "Associative pattern detected between memories: "
                f"'{left.content[:80]}' and '{right.content[:80]}'."
            )
            if shared_entities:
                insight_text += f" Shared entities: {', '.join(shared_entities)}."

            insights.append(
                InsightObject(
                    content=insight_text,
                    confidence=confidence,
                    source_memory_ids=[left.id, right.id],
                    generated_at=now,
                )
            )

        # Curiosity trigger: high emotional intensity and low familiarity become working-question insights.
        for memory in high_priority:
            curiosity_score = self._curiosity_score(memory)
            if curiosity_score < 0.50:
                continue

            confidence = min(0.95, max(0.65, 0.60 + (curiosity_score * 0.35)))
            insights.append(
                InsightObject(
                    content=self._build_working_question(memory),
                    confidence=confidence,
                    source_memory_ids=[memory.id],
                    generated_at=now,
                )
            )

        insights.sort(key=lambda item: item.confidence, reverse=True)
        return AssociativeInsightResult(insights=insights[:12])
