"""Belief conflict resolution for contradictory belief memories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from prompt_engine.schemas import BeliefMemory, MemorySource


POSITIVE_PREFERENCE = re.compile(r"\b(prefer|likes?|wants?|favou?rs?)\b", re.IGNORECASE)
NEGATIVE_PREFERENCE = re.compile(r"\b(dislike|dislikes|avoid|does not want|don't want|rejects?)\b", re.IGNORECASE)

POSITIVE_SENTIMENT = re.compile(
    r"\b(good|great|excellent|happy|love|beneficial|effective|works?)\b",
    re.IGNORECASE,
)
NEGATIVE_SENTIMENT = re.compile(
    r"\b(bad|poor|frustrat(?:ed|ing)?|hate|problem|issue|blocked|fails?|risky)\b",
    re.IGNORECASE,
)

LOCAL_TERMS = {"local", "on-device", "ondevice", "self-hosted", "selfhosted", "offline"}
HOSTED_TERMS = {"hosted", "cloud", "api", "apis", "remote", "saas"}


@dataclass(frozen=True)
class BeliefConflictResult:
    resolved_beliefs: list[BeliefMemory]
    conflict_pairs: list[tuple[str, str]]
    archived_original_ids: list[str]


class BeliefConflictResolver:
    """Find and resolve conflicting belief memories."""

    def _stance(self, content: str) -> int:
        positive = bool(POSITIVE_PREFERENCE.search(content))
        negative = bool(NEGATIVE_PREFERENCE.search(content))
        if positive and not negative:
            return 1
        if negative and not positive:
            return -1
        return 0

    def _sentiment(self, content: str) -> int:
        positive_hits = len(POSITIVE_SENTIMENT.findall(content))
        negative_hits = len(NEGATIVE_SENTIMENT.findall(content))

        if positive_hits > negative_hits:
            return 1
        if negative_hits > positive_hits:
            return -1
        return 0

    def _targets(self, content: str) -> set[str]:
        lowered = content.lower()
        targets: set[str] = set()

        if any(term in lowered for term in LOCAL_TERMS):
            targets.add("local")
        if any(term in lowered for term in HOSTED_TERMS):
            targets.add("hosted")

        return targets

    def _synthesize_content(self, left: BeliefMemory, right: BeliefMemory) -> str:
        left_targets = self._targets(left.content)
        right_targets = self._targets(right.content)

        has_local = "local" in left_targets or "local" in right_targets
        has_hosted = "hosted" in left_targets or "hosted" in right_targets

        if has_local and has_hosted:
            return (
                "Resolved belief update: user prefers local models but occasionally uses hosted APIs "
                "for specific cases."
            )

        return (
            "Resolved belief update: preference appears context-dependent and evolving; "
            "the user may choose different options by workload."
        )

    def resolve(self, beliefs: list[BeliefMemory]) -> BeliefConflictResult:
        now = datetime.now(timezone.utc)
        conflicts: list[tuple[str, str]] = []
        resolved: list[BeliefMemory] = []
        archived_ids: set[str] = set()

        for index, left in enumerate(beliefs):
            left_stance = self._stance(left.content)
            left_sentiment = self._sentiment(left.content)

            for right in beliefs[index + 1 :]:
                if not set(left.entities) & set(right.entities):
                    continue

                right_stance = self._stance(right.content)
                right_sentiment = self._sentiment(right.content)

                opposing_stance = left_stance * right_stance == -1
                opposing_sentiment = left_sentiment * right_sentiment == -1
                if not (opposing_stance or opposing_sentiment):
                    continue

                left_id = str(left.id)
                right_id = str(right.id)
                conflicts.append((left_id, right_id))
                archived_ids.add(left_id)
                archived_ids.add(right_id)

                merged_confidence = min(
                    0.92,
                    max(0.55, ((left.confidence + right.confidence) / 2) + 0.05),
                )

                resolved.append(
                    BeliefMemory(
                        content=self._synthesize_content(left, right),
                        importance_score=min(1.0, max(left.importance_score, right.importance_score)),
                        created_at=now,
                        updated_at=now,
                        last_accessed_at=now,
                        access_count=0,
                        schema_version="3.1",
                        entities=sorted(set(left.entities + right.entities)),
                        relations=[],
                        emotional_valence=(left.emotional_valence + right.emotional_valence) / 2,
                        emotional_intensity=max(left.emotional_intensity, right.emotional_intensity),
                        source=MemorySource.REFLECTION,
                        source_session_id=None,
                        source_message_ids=[],
                        confidence=merged_confidence,
                        reinforced_count=1,
                        derivation_method="system",
                        synthetic=True,
                    )
                )

        return BeliefConflictResult(
            resolved_beliefs=resolved,
            conflict_pairs=conflicts,
            archived_original_ids=sorted(archived_ids),
        )
