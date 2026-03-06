"""Background cognition runner orchestrating Phase 5 agents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from embeddings import TextEmbedder, create_default_embedder
from hot_memory import HotMemoryManager
from prompt_engine.schemas import BeliefMemory, LongTermMemory
from storage import SQLiteMemoryStore, VectorIndexStore

from .associative_insight_generator import AssociativeInsightGenerator
from .belief_conflict_resolver import BeliefConflictResolver, BeliefConflictResult
from .decay_agent import DecayAgent, DecayResult
from .memory_consolidation_agent import ConsolidationResult, MemoryConsolidationAgent
from .reflection_agent import ReflectionAgent, ReflectionResult
from .scheduler import CognitionCadence, CognitionScheduleState


@dataclass(frozen=True)
class BackgroundCognitionConfig:
    recent_memory_limit: int = 200
    insight_confidence_threshold: float = 0.65
    cadence: CognitionCadence = CognitionCadence()


@dataclass(frozen=True)
class BackgroundCognitionResult:
    processed_memories: int
    generated_beliefs: int
    generated_insights: int
    consolidated_memories: int
    archived_memories: int
    conflicts_resolved: int
    executed_tasks: list[str]


class BackgroundCognitionRunner:
    """Runs reflection, consolidation, decay, and conflict resolution."""

    def __init__(
        self,
        *,
        memory_store: SQLiteMemoryStore | None = None,
        json_store: SQLiteMemoryStore | None = None,
        vector_store: VectorIndexStore | None = None,
        hot_memory_manager: HotMemoryManager | None = None,
        embedder: TextEmbedder | None = None,
        config: BackgroundCognitionConfig = BackgroundCognitionConfig(),
    ) -> None:
        self.memory_store = memory_store or json_store or SQLiteMemoryStore()
        self.json_store = self.memory_store
        self.vector_store = vector_store or VectorIndexStore(sqlite_path=self.memory_store.sqlite_path)
        self.hot_memory = hot_memory_manager or HotMemoryManager()
        self.embedder = embedder or create_default_embedder()
        self.config = config

        self.reflection = ReflectionAgent()
        self.consolidation = MemoryConsolidationAgent()
        self.decay = DecayAgent()
        self.conflict_resolver = BeliefConflictResolver()
        self.associative = AssociativeInsightGenerator()

    def _persist_memory(self, memory: LongTermMemory) -> None:
        memory_id = str(memory.id)
        self.memory_store.save_memory(memory)
        self.vector_store.upsert_vector(
            memory_id=memory_id,
            vector=self.embedder.embed(memory.content),
            model_name=self.embedder.model_name,
            payload={
                "memory_id": memory_id,
                "memory_type": memory.type.value,
                "importance_score": round(memory.importance_score, 6),
                "created_at": memory.created_at.isoformat(),
                "source": memory.source.value,
                "entities": memory.entities,
                "schema_version": memory.schema_version,
                "status": memory.status.value,
                "synthetic": memory.synthetic,
            },
        )

    def _default_reflection(self) -> ReflectionResult:
        return ReflectionResult(synthesized_beliefs=[], insights=[])

    def _default_consolidation(self) -> ConsolidationResult:
        return ConsolidationResult(summary_memories=[], consolidated_memory_ids=[])

    def _default_conflicts(self) -> BeliefConflictResult:
        return BeliefConflictResult(
            resolved_beliefs=[],
            conflict_pairs=[],
            archived_original_ids=[],
        )

    def _default_decay(self, memories: list[LongTermMemory]) -> DecayResult:
        return DecayResult(
            updated_memories=memories,
            archive_ids=[],
            vector_prune_ids=[],
        )

    def _run_with_tasks(
        self,
        *,
        memories: list[LongTermMemory],
        execute_reflection: bool,
        execute_associative: bool,
        execute_consolidation: bool,
        execute_decay: bool,
        execute_belief_resolver: bool,
    ) -> BackgroundCognitionResult:
        reflection_result = self.reflection.analyze(memories) if execute_reflection else self._default_reflection()
        associative_result = (
            self.associative.generate(memories)
            if execute_associative
            else self.associative.generate([])
        )

        belief_memories = [memory for memory in memories if isinstance(memory, BeliefMemory)]
        belief_memories.extend(reflection_result.synthesized_beliefs)
        conflict_result = (
            self.conflict_resolver.resolve(belief_memories)
            if execute_belief_resolver
            else self._default_conflicts()
        )

        consolidation_result = (
            self.consolidation.consolidate(memories)
            if execute_consolidation
            else self._default_consolidation()
        )

        now = datetime.now(timezone.utc)
        decay_result = self.decay.decay(memories, now=now) if execute_decay else self._default_decay(memories)

        generated_belief_count = 0
        for belief in reflection_result.synthesized_beliefs:
            self._persist_memory(belief)
            generated_belief_count += 1

        for belief in conflict_result.resolved_beliefs:
            self._persist_memory(belief)
            generated_belief_count += 1

        for summary_memory in consolidation_result.summary_memories:
            self._persist_memory(summary_memory)

        all_insights = reflection_result.insights + associative_result.insights
        accepted_insights = [
            insight
            for insight in all_insights
            if insight.confidence >= self.config.insight_confidence_threshold
        ]
        for insight in accepted_insights:
            self.hot_memory.add_insight(
                insight,
                min_confidence=self.config.insight_confidence_threshold,
            )

        conflict_archive_ids = set(conflict_result.archived_original_ids)
        consolidation_archive_ids = set(consolidation_result.consolidated_memory_ids)
        decay_archive_ids = set(decay_result.archive_ids)

        archived_ids = set()
        archived_ids.update(conflict_archive_ids)
        archived_ids.update(consolidation_archive_ids)
        archived_ids.update(decay_archive_ids)

        vector_prune_ids = set(decay_result.vector_prune_ids)
        vector_prune_ids.update(archived_ids)

        for memory in decay_result.updated_memories:
            memory_id = str(memory.id)
            if memory_id in archived_ids:
                reason = "decayed_low_importance"
                if memory_id in conflict_archive_ids:
                    reason = "belief_conflict_resolved"
                elif memory_id in consolidation_archive_ids:
                    reason = "consolidated"
                self.memory_store.archive_memory(memory.id, reason=reason)
            else:
                self.memory_store.update_memory(memory)

            if memory_id in vector_prune_ids:
                self.vector_store.delete_vector(memory_id)

        self.hot_memory.cool(ttl_hours=36)

        executed_tasks: list[str] = []
        if execute_reflection:
            executed_tasks.append("reflection")
        if execute_associative:
            executed_tasks.append("associative_insight")
        if execute_consolidation:
            executed_tasks.append("consolidation")
        if execute_decay:
            executed_tasks.append("decay")
        if execute_belief_resolver:
            executed_tasks.append("belief_resolver")

        return BackgroundCognitionResult(
            processed_memories=len(memories),
            generated_beliefs=generated_belief_count,
            generated_insights=len(accepted_insights),
            consolidated_memories=len(consolidation_result.summary_memories),
            archived_memories=len(archived_ids),
            conflicts_resolved=len(conflict_result.conflict_pairs),
            executed_tasks=executed_tasks,
        )

    def run_once(self) -> BackgroundCognitionResult:
        memories = self.memory_store.list_memories(limit=self.config.recent_memory_limit)
        memories = sorted(memories, key=lambda item: item.created_at, reverse=True)

        return self._run_with_tasks(
            memories=memories,
            execute_reflection=True,
            execute_associative=True,
            execute_consolidation=True,
            execute_decay=True,
            execute_belief_resolver=True,
        )

    def run_scheduled(
        self,
        schedule_state: CognitionScheduleState | None = None,
    ) -> BackgroundCognitionResult:
        schedule_state = schedule_state or CognitionScheduleState()
        now = datetime.now(timezone.utc)

        execute_reflection = schedule_state.is_due(
            task_name="reflection",
            interval_hours=self.config.cadence.reflection_hours,
            now=now,
        )
        execute_associative = schedule_state.is_due(
            task_name="associative_insight",
            interval_hours=self.config.cadence.associative_hours,
            now=now,
        )
        execute_consolidation = schedule_state.is_due(
            task_name="consolidation",
            interval_hours=self.config.cadence.consolidation_hours,
            now=now,
        )
        execute_decay = schedule_state.is_due(
            task_name="decay",
            interval_hours=self.config.cadence.decay_hours,
            now=now,
        )
        execute_belief_resolver = schedule_state.is_due(
            task_name="belief_resolver",
            interval_hours=self.config.cadence.belief_resolver_hours,
            now=now,
        )

        memories = self.memory_store.list_memories(limit=self.config.recent_memory_limit)
        memories = sorted(memories, key=lambda item: item.created_at, reverse=True)

        result = self._run_with_tasks(
            memories=memories,
            execute_reflection=execute_reflection,
            execute_associative=execute_associative,
            execute_consolidation=execute_consolidation,
            execute_decay=execute_decay,
            execute_belief_resolver=execute_belief_resolver,
        )

        if execute_reflection:
            schedule_state.mark_run("reflection", now=now)
        if execute_associative:
            schedule_state.mark_run("associative_insight", now=now)
        if execute_consolidation:
            schedule_state.mark_run("consolidation", now=now)
        if execute_decay:
            schedule_state.mark_run("decay", now=now)
        if execute_belief_resolver:
            schedule_state.mark_run("belief_resolver", now=now)

        return result

