"""Lane policy helpers for core and working memory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from prompt_engine.schemas import BaseMemory, LaneName, MemoryStatus, MemoryType
from smart_memory_config import LanePolicyConfig


@dataclass(frozen=True)
class LaneDecision:
    promote: bool
    lane: LaneName
    reason: str
    priority: float = 0.0
    pinned: bool = False


class LanePolicy:
    def __init__(self, config: LanePolicyConfig | None = None) -> None:
        self.config = config or LanePolicyConfig()

    def _is_transcript_backed(self, memory: BaseMemory) -> bool:
        return not memory.synthetic and memory.evidence_count > 0

    def should_promote_to_core(self, memory: BaseMemory) -> LaneDecision:
        if memory.status != MemoryStatus.ACTIVE:
            return LaneDecision(False, LaneName.CORE, "only active memories are eligible")
        if not self._is_transcript_backed(memory):
            return LaneDecision(False, LaneName.CORE, "core lane requires transcript-backed durable memory")
        if memory.confidence < self.config.core_confidence_threshold:
            return LaneDecision(False, LaneName.CORE, "confidence below core threshold")
        if memory.importance_score < self.config.core_importance_threshold:
            return LaneDecision(False, LaneName.CORE, "importance below core threshold")
        if memory.status == MemoryStatus.UNCERTAIN:
            return LaneDecision(False, LaneName.CORE, "uncertain memories cannot auto-promote to core")
        if memory.memory_type not in {MemoryType.IDENTITY, MemoryType.PREFERENCE, MemoryType.GOAL, MemoryType.SEMANTIC}:
            return LaneDecision(False, LaneName.CORE, "memory type is not durable enough for core")
        return LaneDecision(
            True,
            LaneName.CORE,
            "durable transcript-backed memory",
            priority=max(memory.pinned_priority, memory.importance_score),
        )

    def should_promote_to_working(self, memory: BaseMemory, *, now: datetime | None = None) -> LaneDecision:
        now = now or datetime.now(timezone.utc)
        if memory.status != MemoryStatus.ACTIVE:
            return LaneDecision(False, LaneName.WORKING, "only active memories are eligible")
        if not self._is_transcript_backed(memory):
            return LaneDecision(False, LaneName.WORKING, "working lane requires transcript-backed active memory")
        session_relevant = bool(memory.source_session_id)
        is_recent = memory.updated_at is not None and memory.updated_at >= now - timedelta(hours=self.config.working_decay_hours)
        is_task_like = memory.memory_type in {MemoryType.GOAL, MemoryType.TASK_STATE, MemoryType.EPISODIC}
        has_task_tag = bool(set(memory.retrieval_tags) & {"blocker", "next_step", "open_issue", "recent_decision"})
        if is_task_like and (is_recent or has_task_tag or session_relevant):
            return LaneDecision(
                True,
                LaneName.WORKING,
                "active transcript-backed working memory",
                priority=min(1.0, max(memory.importance_score, memory.confidence)),
            )
        return LaneDecision(False, LaneName.WORKING, "memory is not active working context")
