"""Action selection policies for memory revision."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_engine.schemas import BaseMemory, RevisionAction

from .conflict_detector import ConflictResult


@dataclass(frozen=True)
class RevisionDecision:
    action: RevisionAction
    target_memory_ids: list[str]
    confidence: float
    reason: str


class UpdatePolicy:
    def choose_action(
        self,
        *,
        candidate: BaseMemory,
        conflict: ConflictResult,
        similarity_score: float = 0.0,
        merge_enabled: bool = False,
    ) -> RevisionDecision:
        if candidate.status.name == "REJECTED":
            return RevisionDecision(
                action=RevisionAction.REJECT,
                target_memory_ids=[],
                confidence=1.0,
                reason="candidate was explicitly rejected before revision",
            )

        if not conflict.has_conflict:
            return RevisionDecision(
                action=RevisionAction.ADD,
                target_memory_ids=[],
                confidence=0.65,
                reason="no matching active memory requires revision",
            )

        if conflict.recommended_action == RevisionAction.MERGE and not merge_enabled:
            return RevisionDecision(
                action=RevisionAction.NOOP if similarity_score >= 0.95 else RevisionAction.SUPERSEDE,
                target_memory_ids=conflict.target_memory_ids,
                confidence=conflict.confidence,
                reason="merge is disabled by default; falling back to noop or supersede",
            )

        if conflict.recommended_action == RevisionAction.UPDATE:
            return RevisionDecision(
                action=RevisionAction.UPDATE,
                target_memory_ids=conflict.target_memory_ids,
                confidence=conflict.confidence,
                reason="metadata-only update is safe",
            )

        return RevisionDecision(
            action=conflict.recommended_action,
            target_memory_ids=conflict.target_memory_ids,
            confidence=conflict.confidence,
            reason=conflict.reason,
        )
