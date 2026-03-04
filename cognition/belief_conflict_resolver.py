"""Belief conflict resolution for contradictory belief memories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from prompt_engine.schemas import BeliefMemory, MemorySource


POSITIVE_PREFERENCE = re.compile(r"\b(prefer|likes?|wants?|favou?rs?)\b", re.IGNORECASE)
NEGATIVE_PREFERENCE = re.compile(r"\b(dislike|dislikes|avoid|does not want|don't want|rejects?)\b", re.IGNORECASE)

LOCAL_TERMS = {"local", "on-device", "ondevice", "self-hosted", "selfhosted", "offline"}
HOSTED_TERMS = {"hosted", "cloud", "api", "apis", "remote", "saas"}


@dataclass(frozen=True)
class BeliefConflictResult:
    resolved_beliefs: list[BeliefMemory]
    conflict_pairs: list[tuple[str, str]]
    archived_original_ids: list[str]


class BeliefConflictResolver:
    """Find and resolve conflicting preference beliefs."""

    def _stance(self, content: str) -> int:
        positive = bool(POSITIVE_PREFERENCE.search(content))
        negative = bool(NEGATIVE_PREFERENCE.search(content))
        if positive and not negative:
            return 1
        if negative and not positive:
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
            left_targets = self._targets(left.content)

            for right in beliefs[index + 1 :]:
                if not set(left.entities) & set(right.entities):
                    continue

                right_stance = self._stance(right.content)
                right_targets = self._targets(right.content)

                contradiction = left_stance * right_stance == -1
                if not contradiction:
                    continue

                # Strong conflict when targets overlap or represent local-vs-hosted tension.
                target_overlap = bool(left_targets & right_targets)
                local_vs_hosted = (
                    "local" in left_targets and "hosted" in right_targets
                ) or (
                    "hosted" in left_targets and "local" in right_targets
                )

                if not target_overlap and not local_vs_hosted:
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
                        importance=min(1.0, max(left.importance, right.importance)),
                        created_at=now,
                        last_accessed=now,
                        access_count=0,
                        schema_version="2.0",
                        entities=sorted(set(left.entities + right.entities)),
                        relations=[],
                        emotional_valence=(left.emotional_valence + right.emotional_valence) / 2,
                        emotional_intensity=max(left.emotional_intensity, right.emotional_intensity),
                        source=MemorySource.REFLECTION,
                        confidence=merged_confidence,
                        reinforced_count=1,
                    )
                )

        return BeliefConflictResult(
            resolved_beliefs=resolved,
            conflict_pairs=conflicts,
            archived_original_ids=sorted(archived_ids),
        )
