"""Revision-aware write orchestration for Smart Memory v3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from prompt_engine.schemas import (
    BaseMemory,
    DecayPolicy,
    LaneName,
    MemoryStatus,
    MemoryType,
    RevisionAction,
)
from smart_memory_config import SmartMemoryV3Config
from storage import JSONMemoryStore, SQLiteMemoryStore

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
        memory_store: SQLiteMemoryStore | JSONMemoryStore | None = None,
        config: SmartMemoryV3Config | None = None,
    ) -> None:
        self.memory_store = memory_store or SQLiteMemoryStore()
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

    def revise(self, candidate: BaseMemory) -> RevisionResult:
        candidate = self.derive_facets(candidate)
        related = self.memory_store.list_related_memories(
            entities=candidate.entities,
            memory_type=candidate.memory_type,
            limit=10,
        ) if hasattr(self.memory_store, "list_related_memories") else self.memory_store.list_memories(limit=10)

        conflict = self.conflict_detector.detect(candidate=candidate, prior_memories=related)
        decision = self.update_policy.choose_action(
            candidate=candidate,
            conflict=conflict,
            merge_enabled=False,
        )
        return self._apply_decision(candidate, decision)

    def _apply_decision(self, candidate: BaseMemory, decision: RevisionDecision) -> RevisionResult:
        now = datetime.now(timezone.utc)
        stored_memory: BaseMemory | None = None

        if decision.action == RevisionAction.REJECT:
            self.memory_store.add_audit_event(
                "memory_rejected",
                memory_ids=[str(candidate.id)],
                action=decision.action.value,
                reason=decision.reason,
                source_session_id=candidate.source_session_id,
                source_message_ids=candidate.source_message_ids,
            )
            return RevisionResult(decision.action, None, [], decision.reason)

        if decision.action == RevisionAction.NOOP:
            self.memory_store.add_audit_event(
                "revision_decision_made",
                memory_ids=[str(candidate.id)] + decision.target_memory_ids,
                action=decision.action.value,
                reason=decision.reason,
                source_session_id=candidate.source_session_id,
                source_message_ids=candidate.source_message_ids,
            )
            return RevisionResult(decision.action, None, decision.target_memory_ids, decision.reason)

        if decision.action == RevisionAction.UPDATE and decision.target_memory_ids:
            target = self.memory_store.get_memory(decision.target_memory_ids[0])
            if target is not None:
                stored_memory = target.model_copy(
                    update={
                        "updated_at": now,
                        "confidence": max(target.confidence, candidate.confidence),
                        "explanation": candidate.explanation or target.explanation,
                        "last_accessed_at": now,
                        "access_count": target.access_count + 1,
                    }
                )
                self.memory_store.update_memory(stored_memory)
        elif decision.action == RevisionAction.EXPIRE and decision.target_memory_ids:
            for memory_id in decision.target_memory_ids:
                target = self.memory_store.get_memory(memory_id)
                if target is None:
                    continue
                expired = target.model_copy(update={"status": MemoryStatus.EXPIRED, "updated_at": now})
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
                    updated = target.model_copy(update={"status": target_status, "updated_at": now})
                    self.memory_store.update_memory(updated)
                    supersedes.append(target.id)
            stored_memory = candidate.model_copy(
                update={
                    "revision_of": supersedes[0] if supersedes else candidate.revision_of,
                    "supersedes": supersedes,
                    "updated_at": now,
                    "status": MemoryStatus.ACTIVE,
                }
            )
            self.memory_store.save_memory(stored_memory)

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
            source_message_ids=candidate.source_message_ids,
            payload={
                "memory_type": candidate.memory_type.value,
                "status": candidate.status.value,
                "lane_eligibility": [lane.value for lane in candidate.lane_eligibility],
            },
        )
        return RevisionResult(decision.action, stored_memory, decision.target_memory_ids, decision.reason)
