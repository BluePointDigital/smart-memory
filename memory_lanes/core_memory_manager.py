"""Core lane manager."""

from __future__ import annotations

from prompt_engine.schemas import BaseMemory, LaneName, MemoryStatus
from storage import SQLiteMemoryStore

from .lane_policy import LanePolicy


class CoreMemoryManager:
    def __init__(self, memory_store: SQLiteMemoryStore | None = None, *, policy: LanePolicy | None = None) -> None:
        self.memory_store = memory_store or SQLiteMemoryStore()
        self.policy = policy or LanePolicy()

    def evaluate_memory(self, memory: BaseMemory) -> bool:
        decision = self.policy.should_promote_to_core(memory)
        if decision.promote:
            self.memory_store.promote_memory(
                memory.id,
                LaneName.CORE,
                pinned=False,
                priority=decision.priority,
                reason=decision.reason,
            )
            self.memory_store.add_audit_event(
                "memory_promoted_to_lane",
                memory_ids=[str(memory.id)],
                action="PROMOTE",
                reason=decision.reason,
                source_session_id=memory.source_session_id,
                source_message_ids=memory.source_message_ids,
                payload={"lane": LaneName.CORE.value},
            )
            return True

        if memory.status in {MemoryStatus.SUPERSEDED, MemoryStatus.EXPIRED, MemoryStatus.ARCHIVED, MemoryStatus.REJECTED}:
            self.memory_store.demote_memory(memory.id, LaneName.CORE)
        return False

    def pin_to_core(self, memory_id: str) -> None:
        memory = self.memory_store.get_memory(memory_id)
        if memory is None or memory.synthetic or memory.evidence_count == 0 or memory.status != MemoryStatus.ACTIVE:
            return
        self.memory_store.promote_memory(memory.id, LaneName.CORE, pinned=True, priority=max(0.9, memory.pinned_priority), reason="manual_pin")

    def unpin_from_core(self, memory_id: str) -> None:
        self.memory_store.demote_memory(memory_id, LaneName.CORE)

    def get_contents(self) -> list[BaseMemory]:
        return self.memory_store.get_lane_contents(LaneName.CORE)
