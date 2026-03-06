"""Integrated cognitive memory system facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cognition import BackgroundCognitionResult, BackgroundCognitionRunner, CognitionScheduleState
from embeddings import create_default_embedder
from entities import EntityAliasResolver
from evaluation import EvalRunner
from hot_memory import HotMemoryManager
from ingestion import IngestionPipeline, IngestionResult
from memory_lanes import CoreMemoryManager, WorkingMemoryManager
from prompt_engine import PromptComposer, PromptComposerOutput, PromptComposerRequest
from retrieval import PromptComposerRetrievalBackend, RetrievalPipeline, RetrievalResult
from revision import MemoryRevisionEngine, RevisionResult
from smart_memory_config import SmartMemoryV3Config
from storage import SQLiteMemoryStore, VectorIndexStore


@dataclass(frozen=True)
class CognitiveMemorySystemResult:
    ingestion: IngestionResult | None
    retrieval: RetrievalResult | None
    prompt: PromptComposerOutput | None
    background: BackgroundCognitionResult | None


class CognitiveMemorySystem:
    """Top-level API for the full cognitive memory architecture."""

    def __init__(self, *, config: SmartMemoryV3Config | None = None) -> None:
        config = config or SmartMemoryV3Config()
        embedder = create_default_embedder()
        memory_store = SQLiteMemoryStore(config.storage.sqlite_path)
        vector_store = VectorIndexStore(sqlite_path=memory_store.sqlite_path)
        entity_resolver = EntityAliasResolver()

        self.memory_store = memory_store
        self.vector_store = vector_store
        self.entity_resolver = entity_resolver

        self.ingestion = IngestionPipeline(
            json_store=memory_store,
            vector_store=vector_store,
            embedder=embedder,
            entity_resolver=entity_resolver,
        )
        self.retrieval = RetrievalPipeline(
            json_store=memory_store,
            vector_store=vector_store,
            embedder=embedder,
            entity_resolver=entity_resolver,
        )
        self.revision = MemoryRevisionEngine(memory_store=memory_store, config=config)
        self.core_lane = CoreMemoryManager(memory_store)
        self.working_lane = WorkingMemoryManager(memory_store, config=config.lane_policy)
        self.hot_memory = HotMemoryManager()
        self.background = BackgroundCognitionRunner(
            json_store=memory_store,
            vector_store=vector_store,
            hot_memory_manager=self.hot_memory,
            embedder=embedder,
        )
        self.eval_runner = EvalRunner(self)

        backend = PromptComposerRetrievalBackend(self.retrieval)
        self.composer = PromptComposer(retrieval_backend=backend)

    def ingest_message(self, payload: dict[str, Any]) -> IngestionResult:
        return self.ingestion.ingest_dict(payload)

    def ingest_candidate_memory(self, payload: dict[str, Any]) -> IngestionResult:
        return self.ingest_message(payload)

    def revise_memory(self, memory_payload: dict[str, Any]) -> RevisionResult:
        from prompt_engine.schemas import validate_long_term_memory

        memory = validate_long_term_memory(memory_payload)
        return self.revision.revise(memory)

    def ingest_interaction(self, payload: dict[str, Any]) -> IngestionResult:
        result = self.ingest_message(payload)
        if result.memory_id:
            memory = self.memory_store.get_memory(result.memory_id)
            if memory is not None:
                self.hot_memory.register_high_importance_memory(memory)
        return result

    def retrieve(self, query: str, *, include_history: bool = False, entity_scope: list[str] | None = None) -> RetrievalResult:
        return self.retrieval.retrieve(query, include_history=include_history, entity_scope=entity_scope or [])

    def retrieve_context(self, user_message: str, conversation_history: str = "") -> RetrievalResult:
        result = self.retrieval.retrieve(user_message=user_message, conversation_history=conversation_history)
        for ranked in result.selected:
            self.hot_memory.register_retrieval_hit(ranked.memory)
        return result

    def retrieve_for_task(self, task_context: str):
        return self.retrieval.retrieve_for_task(task_context)

    def pin_to_core(self, memory_id: str) -> None:
        self.core_lane.pin_to_core(memory_id)

    def unpin_from_core(self, memory_id: str) -> None:
        self.core_lane.unpin_from_core(memory_id)

    def get_lane_contents(self, lane_name: str):
        from prompt_engine.schemas import LaneName

        return self.memory_store.get_lane_contents(LaneName(lane_name))

    def promote_memory(self, memory_id: str, lane_name: str) -> None:
        from prompt_engine.schemas import LaneName

        self.memory_store.promote_memory(memory_id, LaneName(lane_name), reason="manual_promote")

    def demote_memory(self, memory_id: str, lane_name: str) -> None:
        from prompt_engine.schemas import LaneName

        self.memory_store.demote_memory(memory_id, LaneName(lane_name))

    def get_memory_history(self, memory_id: str):
        return self.memory_store.get_memory_history(memory_id)

    def get_active_version(self, memory_id: str):
        return self.memory_store.get_active_version(memory_id)

    def get_revision_chain(self, memory_id: str):
        return self.memory_store.get_revision_chain(memory_id)

    def compose_prompt(self, request_payload: dict[str, Any]) -> PromptComposerOutput:
        payload = dict(request_payload)
        if "hot_memory" not in payload:
            payload["hot_memory"] = self.working_lane.to_hot_memory(insights=self.hot_memory.get().insight_queue).model_dump(mode="json")
        if "core_memories" not in payload:
            payload["core_memories"] = [memory.model_dump(mode="json") for memory in self.core_lane.get_contents()]
        if "working_memories" not in payload:
            payload["working_memories"] = [memory.model_dump(mode="json") for memory in self.working_lane.get_contents()]

        request = PromptComposerRequest.model_validate(payload)
        output = self.composer.compose(request)
        self.memory_store.add_audit_event(
            "context_assembled",
            memory_ids=[str(trace.memory_id) for trace in output.memory_traces],
            action="COMPOSE",
            reason="prompt assembled",
            scores={"selected_memory_count": len(output.selected_memories)},
            payload={"interaction_state": output.interaction_state.value},
        )
        return output

    def run_background_cycle(self, *, scheduled: bool = True) -> BackgroundCognitionResult:
        if scheduled:
            return self.background.run_scheduled(CognitionScheduleState())
        return self.background.run_once()

    def run_eval_suite(self, suite_name: str):
        return self.eval_runner.run_eval_suite(suite_name)

    def run_eval_case(self, case_id: str):
        return self.eval_runner.run_eval_case(case_id)

    def process_turn(self, *, ingestion_payload: dict[str, Any], prompt_request_payload: dict[str, Any]) -> CognitiveMemorySystemResult:
        ingestion_result = self.ingest_interaction(ingestion_payload)
        retrieval_result = self.retrieve_context(
            user_message=prompt_request_payload.get("current_user_message", ""),
            conversation_history=prompt_request_payload.get("conversation_history", ""),
        )
        prompt_result = self.compose_prompt(prompt_request_payload)

        return CognitiveMemorySystemResult(
            ingestion=ingestion_result,
            retrieval=retrieval_result,
            prompt=prompt_result,
            background=None,
        )
