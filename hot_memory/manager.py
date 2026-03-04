"""Hot-memory manager with update triggers and cooling behavior."""

from __future__ import annotations

from datetime import datetime, timezone

from prompt_engine.schemas import (
    AgentState,
    AgentStatus,
    HotMemory,
    InsightObject,
    LongTermMemory,
    MemoryType,
)

from .store import HotMemoryBundle, HotMemoryStore


ACTIVE_PROJECT_CAP = 10
WORKING_QUESTION_CAP = 10
TOP_OF_MIND_CAP = 20
INSIGHT_QUEUE_CAP = 10


class HotMemoryManager:
    """Applies deterministic trigger rules to maintain working memory."""

    def __init__(self, store: HotMemoryStore | None = None) -> None:
        self.store = store or HotMemoryStore()

    def _save(self, bundle: HotMemoryBundle) -> HotMemory:
        self.store.save_bundle(bundle)
        return bundle.hot_memory

    def _touch_agent_state(
        self,
        hot_memory: HotMemory,
        *,
        status: AgentStatus | None = None,
        background_task: str | None = None,
    ) -> HotMemory:
        now = datetime.now(timezone.utc)
        new_state = AgentState(
            status=status or hot_memory.agent_state.status,
            last_interaction_timestamp=now,
            last_background_task=background_task or hot_memory.agent_state.last_background_task,
        )

        return HotMemory(
            agent_state=new_state,
            active_projects=hot_memory.active_projects,
            working_questions=hot_memory.working_questions,
            top_of_mind=hot_memory.top_of_mind,
            insight_queue=hot_memory.insight_queue,
        )

    def _append_unique(self, items: list[str], value: str, max_items: int) -> list[str]:
        cleaned = value.strip()
        if not cleaned:
            return items

        new_items = [item for item in items if item != cleaned]
        new_items.insert(0, cleaned)
        return new_items[:max_items]

    def register_high_importance_memory(self, memory: LongTermMemory) -> HotMemory:
        bundle = self.store.load_bundle()
        hot = bundle.hot_memory

        self.store.add_memory_ref(str(memory.id))

        if memory.importance >= 0.80:
            summary = memory.content[:180]
            hot = HotMemory(
                agent_state=hot.agent_state,
                active_projects=hot.active_projects,
                working_questions=hot.working_questions,
                top_of_mind=self._append_unique(hot.top_of_mind, summary, TOP_OF_MIND_CAP),
                insight_queue=hot.insight_queue,
            )
            bundle.reinforcement.setdefault("top_of_mind", {})[summary] = datetime.now(timezone.utc).isoformat()

        if memory.type == MemoryType.GOAL and memory.entities:
            for entity in memory.entities:
                hot = HotMemory(
                    agent_state=hot.agent_state,
                    active_projects=self._append_unique(hot.active_projects, entity, ACTIVE_PROJECT_CAP),
                    working_questions=hot.working_questions,
                    top_of_mind=hot.top_of_mind,
                    insight_queue=hot.insight_queue,
                )
                bundle.reinforcement.setdefault("active_projects", {})[entity] = datetime.now(timezone.utc).isoformat()

        hot = self._touch_agent_state(hot, status=AgentStatus.ENGAGED)
        bundle.hot_memory = hot
        return self._save(bundle)

    def register_retrieval_hit(self, memory: LongTermMemory, threshold: int = 3) -> HotMemory:
        count = self.store.increment_retrieval(str(memory.id))
        bundle = self.store.load_bundle()
        hot = bundle.hot_memory

        if count >= threshold:
            summary = memory.content[:140]
            hot = HotMemory(
                agent_state=hot.agent_state,
                active_projects=hot.active_projects,
                working_questions=hot.working_questions,
                top_of_mind=self._append_unique(hot.top_of_mind, summary, TOP_OF_MIND_CAP),
                insight_queue=hot.insight_queue,
            )
            bundle.reinforcement.setdefault("top_of_mind", {})[summary] = datetime.now(timezone.utc).isoformat()

        bundle.hot_memory = self._touch_agent_state(hot, status=AgentStatus.ENGAGED)
        return self._save(bundle)

    def start_project(self, project_id: str) -> HotMemory:
        bundle = self.store.load_bundle()
        hot = bundle.hot_memory

        hot = HotMemory(
            agent_state=hot.agent_state,
            active_projects=self._append_unique(hot.active_projects, project_id, ACTIVE_PROJECT_CAP),
            working_questions=hot.working_questions,
            top_of_mind=hot.top_of_mind,
            insight_queue=hot.insight_queue,
        )
        bundle.reinforcement.setdefault("active_projects", {})[project_id] = datetime.now(timezone.utc).isoformat()

        bundle.hot_memory = self._touch_agent_state(hot, status=AgentStatus.ENGAGED)
        return self._save(bundle)

    def add_working_question(self, question: str) -> HotMemory:
        bundle = self.store.load_bundle()
        hot = bundle.hot_memory

        hot = HotMemory(
            agent_state=hot.agent_state,
            active_projects=hot.active_projects,
            working_questions=self._append_unique(hot.working_questions, question, WORKING_QUESTION_CAP),
            top_of_mind=hot.top_of_mind,
            insight_queue=hot.insight_queue,
        )
        bundle.reinforcement.setdefault("working_questions", {})[question] = datetime.now(timezone.utc).isoformat()

        bundle.hot_memory = self._touch_agent_state(hot, status=AgentStatus.ENGAGED)
        return self._save(bundle)

    def add_insight(self, insight: InsightObject, min_confidence: float = 0.65) -> HotMemory:
        bundle = self.store.load_bundle()
        hot = bundle.hot_memory

        if insight.confidence < min_confidence:
            return hot

        existing = [item for item in hot.insight_queue if item.id != insight.id]
        existing.insert(0, insight)

        hot = HotMemory(
            agent_state=hot.agent_state,
            active_projects=hot.active_projects,
            working_questions=hot.working_questions,
            top_of_mind=hot.top_of_mind,
            insight_queue=existing[:INSIGHT_QUEUE_CAP],
        )

        for memory_id in insight.source_memory_ids:
            self.store.add_memory_ref(str(memory_id))

        bundle.hot_memory = self._touch_agent_state(
            hot,
            status=AgentStatus.RETURNING,
            background_task="insight_generation",
        )
        return self._save(bundle)

    def cool(self, ttl_hours: int = 36) -> HotMemory:
        return self.store.cool(ttl_hours=ttl_hours)

    def get(self) -> HotMemory:
        return self.store.get_hot_memory()
