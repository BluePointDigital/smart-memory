"""Revision-aware write orchestration for Smart Memory v3.1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from prompt_engine.schemas import (
    BaseMemory,
    DecayPolicy,
    MemoryStatus,
    MemoryType,
    RevisionAction,
)
from smart_memory_config import SmartMemoryV3Config
from storage import SQLiteMemoryStore
from transcripts import TranscriptStore

from .conflict_detector import ConflictDetector
from .update_policy import RevisionDecision, UpdatePolicy


@dataclass(frozen=True)
class RevisionResult:
    action: RevisionAction
    stored_memory: BaseMemory | None
    target_memory_ids: list[str]
    audit_reason: str


class MemoryRevisionEngine:
    def __init__(
        self,
        *,
        memory_store: SQLiteMemoryStore | None = None,
        transcript_store: TranscriptStore | None = None,
        config: SmartMemoryV3Config | None = None,
    ) -> None:
        self.memory_store = memory_store or SQLiteMemoryStore()
        self.transcript_store = transcript_store or TranscriptStore(self.memory_store.sqlite_path)
        self.config = config or SmartMemoryV3Config()
        self.conflict_detector = ConflictDetector()
        self.update_policy = UpdatePolicy()

    def derive_facets(self, memory: BaseMemory) -> BaseMemory:
        subject_entity_id = memory.subject_entity_id or (memory.entities[0] if memory.entities else None)
        attribute_family = memory.attribute_family
        normalized_value = memory.normalized_value
        state_label = memory.state_label
        lowered = memory.content.lower()

        if memory.memory_type == MemoryType.PREFERENCE:
            attribute_family = attribute_family or "preference"
            if normalized_value is None:
                for marker in ("prefer", "like", "love", "dislike", "avoid"):
                    if marker in lowered:
                        normalized_value = lowered.split(marker, 1)[-1].strip().split(".")[0]
                        break
        elif memory.memory_type == MemoryType.IDENTITY:
            attribute_family = attribute_family or "identity"
            normalized_value = normalized_value or lowered
        elif memory.memory_type == MemoryType.GOAL:
            attribute_family = attribute_family or "goal"
            if state_label is None:
                if "complete" in lowered or "launched" in lowered or "done" in lowered:
                    state_label = "completed"
                elif "abandon" in lowered or "killed" in lowered or "cancel" in lowered:
                    state_label = "abandoned"
                else:
                    state_label = "active"
            if memory.decay_policy == DecayPolicy.NONE:
                memory = memory.model_copy(update={"decay_policy": DecayPolicy.GOAL_COMPLETION})
        elif memory.memory_type == MemoryType.TASK_STATE:
            attribute_family = attribute_family or "task_state"
            if state_label is None:
                for label in ("completed", "blocked", "resolved", "abandoned", "in_progress"):
                    if label.replace("_", " ") in lowered or label in lowered:
                        state_label = label
                        break
        elif memory.memory_type == MemoryType.BELIEF:
            attribute_family = attribute_family or "belief"
            normalized_value = normalized_value or lowered

        return memory.model_copy(
            update={
                "subject_entity_id": subject_entity_id,
                "attribute_family": attribute_family,
                "normalized_value": normalized_value,
                "state_label": state_label,
                "valid_from": memory.valid_from or memory.created_at,
            }
        )

    def _memory_signature(self, candidate: BaseMemory) -> str:
        parts = [
            candidate.memory_type.value,
            candidate.subject_entity_id or "",
            candidate.attribute_family or "",
            candidate.normalized_value or "",
            candidate.state_label or "",
            candidate.content.strip().lower(),
        ]
        return "|".join(parts)

    def _stable_memory_id(self, candidate: BaseMemory, *, candidate_index: int = 0):
        primary_message_id = candidate.source_message_ids[0] if candidate.source_message_ids else str(candidate.id)
        basis = f"{primary_message_id}|{candidate.derivation_method}|{self._memory_signature(candidate)}|{candidate_index}"
        return uuid5(NAMESPACE_URL, basis)

    def _sync_memory_evidence(self, memory: BaseMemory) -> BaseMemory:
        if memory.synthetic or not memory.source_message_ids:
            self.memory_store.update_memory(memory)
            return memory

        message_ids, count, summary, session_id = self.transcript_store.evidence_snapshot(str(memory.id))
        updated = memory.model_copy(
            update={
                "source_message_ids": message_ids,
                "source_session_id": session_id or memory.source_session_id,
                "evidence_count": count,
                "evidence_summary": summary or memory.evidence_summary,
            }
        )
        self.memory_store.update_memory(updated)
        return updated

    def _link_evidence(
        self,
        *,
        memory: BaseMemory,
        evidence_kind: str,
        message_ids: list[str] | None = None,
        confidence: float | None = None,
    ) -> BaseMemory:
        effective_message_ids = list(message_ids or memory.source_message_ids)
        if memory.synthetic or not effective_message_ids:
            self.memory_store.update_memory(memory)
            return memory
        self.transcript_store.link_memory_evidence_batch(
            memory_id=str(memory.id),
            message_ids=effective_message_ids,
            evidence_kind=evidence_kind,
            confidence=confidence,
        )
        return self._sync_memory_evidence(memory)

    def revise(
        self,
        candidate: BaseMemory,
        *,
        candidate_index: int = 0,
        rebuilt_at: datetime | None = None,
    ) -> RevisionResult:
        candidate = self.derive_facets(candidate)
        if not candidate.synthetic:
            candidate = candidate.model_copy(update={"id": self._stable_memory_id(candidate, candidate_index=candidate_index)})
        if rebuilt_at is not None:
            candidate = candidate.model_copy(update={"rebuilt_at": rebuilt_at})

        related = self.memory_store.list_related_memories(
            entities=candidate.entities,
            memory_type=candidate.memory_type,
            limit=10,
        )

        conflict = self.conflict_detector.detect(candidate=candidate, prior_memories=related)
        decision = self.update_policy.choose_action(
            candidate=candidate,
            conflict=conflict,
            merge_enabled=False,
        )
        return self._apply_decision(candidate, decision, rebuilt_at=rebuilt_at)

    def _apply_decision(
        self,
        candidate: BaseMemory,
        decision: RevisionDecision,
        *,
        rebuilt_at: datetime | None = None,
    ) -> RevisionResult:
        now = rebuilt_at or datetime.now(timezone.utc)
        stored_memory: BaseMemory | None = None
        evidence_message_ids = list(candidate.source_message_ids)

        if decision.action == RevisionAction.REJECT:
            self.memory_store.add_audit_event(
                "memory_rejected",
                memory_ids=[str(candidate.id)],
                action=decision.action.value,
                reason=decision.reason,
                source_session_id=candidate.source_session_id,
                source_message_ids=evidence_message_ids,
                payload={"synthetic": candidate.synthetic, "evidence_count": candidate.evidence_count},
            )
            return RevisionResult(decision.action, None, [], decision.reason)

        if decision.action == RevisionAction.NOOP:
            for memory_id in decision.target_memory_ids[:1]:
                target = self.memory_store.get_memory(memory_id)
                if target is None:
                    continue
                updated_target = self._link_evidence(
                    memory=target,
                    evidence_kind="noop_source",
                    message_ids=evidence_message_ids,
                    confidence=candidate.confidence,
                )
                updated_target = updated_target.model_copy(
                    update={
                        "updated_at": now,
                        "last_accessed_at": now,
                        "access_count": updated_target.access_count + 1,
                    }
                )
                self.memory_store.update_memory(updated_target)
            self.memory_store.add_audit_event(
                "revision_decision_made",
                memory_ids=[str(candidate.id)] + decision.target_memory_ids,
                action=decision.action.value,
                reason=decision.reason,
                source_session_id=candidate.source_session_id,
                source_message_ids=evidence_message_ids,
                payload={"conflict_targets": decision.target_memory_ids},
            )
            return RevisionResult(decision.action, None, decision.target_memory_ids, decision.reason)

        if decision.action == RevisionAction.UPDATE and decision.target_memory_ids:
            target = self.memory_store.get_memory(decision.target_memory_ids[0])
            if target is not None:
                stored_memory = target.model_copy(
                    update={
                        "updated_at": now,
                        "rebuilt_at": rebuilt_at,
                        "confidence": max(target.confidence, candidate.confidence),
                        "explanation": candidate.explanation or target.explanation,
                        "last_accessed_at": now,
                        "access_count": target.access_count + 1,
                    }
                )
                stored_memory = self._link_evidence(
                    memory=stored_memory,
                    evidence_kind="update_source",
                    message_ids=evidence_message_ids,
                    confidence=candidate.confidence,
                )
        elif decision.action == RevisionAction.EXPIRE and decision.target_memory_ids:
            for memory_id in decision.target_memory_ids:
                target = self.memory_store.get_memory(memory_id)
                if target is None:
                    continue
                expired = target.model_copy(update={"status": MemoryStatus.EXPIRED, "updated_at": now, "rebuilt_at": rebuilt_at})
                expired = self._link_evidence(
                    memory=expired,
                    evidence_kind="expired_by",
                    message_ids=evidence_message_ids,
                    confidence=candidate.confidence,
                )
                self.memory_store.update_memory(expired)
            stored_memory = None
        else:
            supersedes = []
            for memory_id in decision.target_memory_ids:
                target = self.memory_store.get_memory(memory_id)
                if target is None:
                    continue
                if decision.action in {RevisionAction.SUPERSEDE, RevisionAction.MERGE}:
                    target_status = MemoryStatus.SUPERSEDED if decision.action == RevisionAction.SUPERSEDE else MemoryStatus.ARCHIVED
                    updated = target.model_copy(update={"status": target_status, "updated_at": now, "rebuilt_at": rebuilt_at})
                    updated = self._link_evidence(
                        memory=updated,
                        evidence_kind="superseded_by" if decision.action == RevisionAction.SUPERSEDE else "merged_by",
                        message_ids=evidence_message_ids,
                        confidence=candidate.confidence,
                    )
                    self.memory_store.update_memory(updated)
                    supersedes.append(target.id)
            stored_memory = candidate.model_copy(
                update={
                    "revision_of": supersedes[0] if supersedes else candidate.revision_of,
                    "supersedes": supersedes,
                    "updated_at": now,
                    "status": MemoryStatus.ACTIVE,
                    "rebuilt_at": rebuilt_at,
                }
            )
            self.memory_store.save_memory(stored_memory)
            stored_memory = self._link_evidence(
                memory=stored_memory,
                evidence_kind="direct",
                message_ids=evidence_message_ids,
                confidence=candidate.confidence,
            )

        event_name = {
            RevisionAction.ADD: "memory_added",
            RevisionAction.UPDATE: "memory_updated",
            RevisionAction.SUPERSEDE: "memory_superseded",
            RevisionAction.EXPIRE: "memory_expired",
            RevisionAction.MERGE: "memory_merged",
        }.get(decision.action, "revision_decision_made")

        memory_ids = [str(stored_memory.id)] if stored_memory is not None else []
        memory_ids.extend(decision.target_memory_ids)
        self.memory_store.add_audit_event(
            event_name,
            memory_ids=memory_ids,
            action=decision.action.value,
            reason=decision.reason,
            source_session_id=candidate.source_session_id,
            source_message_ids=evidence_message_ids,
            payload={
                "memory_type": candidate.memory_type.value,
                "status": candidate.status.value,
                "lane_eligibility": [lane.value for lane in candidate.lane_eligibility],
                "conflict_targets": decision.target_memory_ids,
                "derivation_method": candidate.derivation_method,
            },
        )
        return RevisionResult(decision.action, stored_memory, decision.target_memory_ids, decision.reason)


