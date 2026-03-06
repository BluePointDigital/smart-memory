"""Conflict detection for revision-aware memory writes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from prompt_engine.schemas import BaseMemory, MemoryType, RevisionAction


CHANGE_MARKERS = {"now", "instead", "no longer", "used to", "changed", "stopped", "switched"}
NEGATION_MARKERS = {"not", "never", "no", "dont", "don't", "avoid"}
TASK_STATES = {"in_progress", "blocked", "completed", "resolved", "abandoned"}


@dataclass(frozen=True)
class ConflictResult:
    has_conflict: bool
    conflict_type: str | None
    target_memory_ids: list[str]
    recommended_action: RevisionAction
    confidence: float
    reason: str


class ConflictDetector:
    def _tokens(self, text: str) -> set[str]:
        return {
            token.lower().strip('.,!?;:()[]{}"\'')
            for token in text.split()
            if len(token) >= 2
        }

    def _overlap(self, left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / max(1, min(len(left), len(right)))

    def _same_subject(self, candidate: BaseMemory, prior: BaseMemory) -> bool:
        if candidate.subject_entity_id and prior.subject_entity_id:
            return candidate.subject_entity_id == prior.subject_entity_id
        return bool(set(candidate.entities) & set(prior.entities))

    def _same_family(self, candidate: BaseMemory, prior: BaseMemory) -> bool:
        if candidate.attribute_family and prior.attribute_family:
            return candidate.attribute_family == prior.attribute_family
        return candidate.memory_type == prior.memory_type

    def _contains_change_marker(self, content: str) -> bool:
        lowered = content.lower()
        return any(marker in lowered for marker in CHANGE_MARKERS)

    def _has_negation_conflict(self, candidate: BaseMemory, prior: BaseMemory) -> bool:
        candidate_tokens = self._tokens(candidate.content)
        prior_tokens = self._tokens(prior.content)
        has_negation = bool(candidate_tokens & NEGATION_MARKERS) or bool(prior_tokens & NEGATION_MARKERS)
        return has_negation and self._overlap(candidate_tokens, prior_tokens) >= 0.4

    def _goal_conflict(self, candidate: BaseMemory, prior: BaseMemory) -> tuple[bool, str | None]:
        if candidate.memory_type != MemoryType.GOAL or prior.memory_type != MemoryType.GOAL:
            return (False, None)
        if candidate.state_label in {"completed", "abandoned"} and prior.state_label in {None, "active", "planned"}:
            return (True, f"goal_{candidate.state_label}")
        return (False, None)

    def _task_conflict(self, candidate: BaseMemory, prior: BaseMemory) -> tuple[bool, str | None]:
        if candidate.memory_type != MemoryType.TASK_STATE and prior.memory_type != MemoryType.TASK_STATE:
            return (False, None)
        if candidate.state_label and prior.state_label and candidate.state_label != prior.state_label:
            if candidate.state_label in TASK_STATES and prior.state_label in TASK_STATES:
                return (True, "task_state_transition")
        return (False, None)

    def detect(
        self,
        *,
        candidate: BaseMemory,
        prior_memories: list[BaseMemory],
        now: datetime | None = None,
    ) -> ConflictResult:
        now = now or datetime.now(timezone.utc)
        targets: list[str] = []
        detected_type: str | None = None
        confidence = 0.0
        reason = "no meaningful conflict detected"
        action = RevisionAction.ADD

        for prior in prior_memories:
            if not self._same_subject(candidate, prior) or not self._same_family(candidate, prior):
                continue

            if prior.valid_to is not None and prior.valid_to < now:
                targets.append(str(prior.id))
                detected_type = "time_bound_expired"
                confidence = max(confidence, 0.9)
                action = RevisionAction.EXPIRE
                reason = "prior memory expired by validity window"
                continue

            same_value = candidate.normalized_value and prior.normalized_value and candidate.normalized_value == prior.normalized_value
            lexical_overlap = self._overlap(self._tokens(candidate.content), self._tokens(prior.content))

            if same_value and lexical_overlap >= 0.95:
                targets.append(str(prior.id))
                detected_type = "equivalent_duplicate"
                confidence = max(confidence, 0.98)
                action = RevisionAction.NOOP
                reason = "candidate repeats an already active semantic value"
                continue

            if candidate.memory_type == MemoryType.PREFERENCE and prior.memory_type == MemoryType.PREFERENCE:
                if same_value:
                    targets.append(str(prior.id))
                    detected_type = "equivalent_duplicate"
                    confidence = max(confidence, 0.98)
                    action = RevisionAction.NOOP
                    reason = "preference already stored"
                    continue
                if self._contains_change_marker(candidate.content) or candidate.normalized_value != prior.normalized_value:
                    targets.append(str(prior.id))
                    detected_type = "preference_change"
                    confidence = max(confidence, 0.91)
                    action = RevisionAction.SUPERSEDE
                    reason = "same subject and preference family with changed value"
                    continue

            if candidate.memory_type in {MemoryType.BELIEF, MemoryType.IDENTITY} and prior.memory_type == candidate.memory_type:
                if self._has_negation_conflict(candidate, prior) or (
                    candidate.normalized_value
                    and prior.normalized_value
                    and candidate.normalized_value != prior.normalized_value
                ):
                    targets.append(str(prior.id))
                    detected_type = "belief_negation" if candidate.memory_type == MemoryType.BELIEF else "identity_change"
                    confidence = max(confidence, 0.88)
                    action = RevisionAction.SUPERSEDE
                    reason = "same subject with a contradictory semantic value"
                    continue

            goal_conflict, goal_type = self._goal_conflict(candidate, prior)
            if goal_conflict:
                targets.append(str(prior.id))
                detected_type = goal_type
                confidence = max(confidence, 0.90)
                action = RevisionAction.SUPERSEDE
                reason = "goal lifecycle transitioned to a new state"
                continue

            task_conflict, task_type = self._task_conflict(candidate, prior)
            if task_conflict:
                targets.append(str(prior.id))
                detected_type = task_type
                confidence = max(confidence, 0.87)
                action = RevisionAction.SUPERSEDE
                reason = "task state transitioned to a new active state"
                continue

            if lexical_overlap >= 0.97 and same_value:
                targets.append(str(prior.id))
                detected_type = "merge_candidate"
                confidence = max(confidence, 0.97)
                action = RevisionAction.MERGE
                reason = "high-confidence duplicate semantics detected"

        if not targets:
            return ConflictResult(
                has_conflict=False,
                conflict_type=None,
                target_memory_ids=[],
                recommended_action=RevisionAction.ADD,
                confidence=0.0,
                reason="no related active conflict found",
            )

        return ConflictResult(
            has_conflict=True,
            conflict_type=detected_type,
            target_memory_ids=sorted(set(targets)),
            recommended_action=action,
            confidence=min(1.0, confidence),
            reason=reason,
        )
