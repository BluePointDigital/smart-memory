"""Working lane manager with hot-memory projection support."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from prompt_engine.schemas import AgentState, AgentStatus, BaseMemory, HotMemory, InsightObject, LaneName, MemoryStatus
from smart_memory_config import LanePolicyConfig
from storage import SQLiteMemoryStore

from .lane_policy import LanePolicy


class WorkingMemoryManager:
    def __init__(
        self,
        memory_store: SQLiteMemoryStore | None = None,
        *,
        policy: LanePolicy | None = None,
        config: LanePolicyConfig | None = None,
    ) -> None:
        self.memory_store = memory_store or SQLiteMemoryStore()
        self.policy = policy or LanePolicy(config=config)
        self.config = config or LanePolicyConfig()

    def evaluate_memory(self, memory: BaseMemory) -> bool:
        decision = self.policy.should_promote_to_working(memory)
        if decision.promote:
            self.memory_store.promote_memory(
                memory.id,
                LaneName.WORKING,
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
                payload={"lane": LaneName.WORKING.value},
            )
            return True

        if memory.status in {MemoryStatus.SUPERSEDED, MemoryStatus.EXPIRED, MemoryStatus.ARCHIVED, MemoryStatus.REJECTED}:
            self.memory_store.demote_memory(memory.id, LaneName.WORKING)
        return False

    def demote_stale(self, *, now: datetime | None = None) -> list[str]:
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=self.config.working_decay_hours)
        demoted: list[str] = []
        for memory in self.memory_store.get_lane_contents(LaneName.WORKING):
            if memory.updated_at is not None and memory.updated_at < cutoff:
                self.memory_store.demote_memory(memory.id, LaneName.WORKING)
                demoted.append(str(memory.id))
        return demoted

    def get_contents(self) -> list[BaseMemory]:
        return self.memory_store.get_lane_contents(LaneName.WORKING)

    def to_hot_memory(self, *, insights: list[InsightObject] | None = None) -> HotMemory:
        now = datetime.now(timezone.utc)
        lane_memories = [memory for memory in self.get_contents() if not memory.synthetic and memory.evidence_count > 0]
        active_projects: list[str] = []
        working_questions: list[str] = []
        top_of_mind: list[str] = []

        for memory in lane_memories:
            if memory.subject_entity_id and memory.subject_entity_id not in active_projects:
                active_projects.append(memory.subject_entity_id)
            if "question" in memory.retrieval_tags or "?" in memory.content:
                working_questions.append(memory.content[:160])
            top_of_mind.append(memory.content[:180])

        return HotMemory(
            agent_state=AgentState(
                status=AgentStatus.ENGAGED,
                last_interaction_timestamp=now,
                last_background_task="working_lane_projection",
            ),
            active_projects=active_projects[:10],
            working_questions=working_questions[:10],
            top_of_mind=top_of_mind[:20],
            insight_queue=(insights or [])[:10],
        )
