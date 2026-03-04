"""Integrated cognitive memory system facade.

Connects:
- Phase 2 ingestion
- Phase 3 retrieval
- Phase 4 hot memory
- Phase 5 background cognition
- Prompt composition (Phase 0)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cognition import (
    BackgroundCognitionResult,
    BackgroundCognitionRunner,
    CognitionScheduleState,
)
from embeddings import create_default_embedder
from entities import EntityAliasResolver
from hot_memory import HotMemoryManager
from ingestion import IngestionPipeline, IngestionResult
from prompt_engine import PromptComposer, PromptComposerOutput, PromptComposerRequest
from retrieval import PromptComposerRetrievalBackend, RetrievalPipeline, RetrievalResult


@dataclass(frozen=True)
class CognitiveMemorySystemResult:
    ingestion: IngestionResult | None
    retrieval: RetrievalResult | None
    prompt: PromptComposerOutput | None
    background: BackgroundCognitionResult | None


class CognitiveMemorySystem:
    """Top-level API for the full cognitive memory architecture."""

    def __init__(self) -> None:
        embedder = create_default_embedder()
        entity_resolver = EntityAliasResolver()

        self.ingestion = IngestionPipeline(embedder=embedder, entity_resolver=entity_resolver)
        self.retrieval = RetrievalPipeline(embedder=embedder, entity_resolver=entity_resolver)
        self.hot_memory = HotMemoryManager()
        self.background = BackgroundCognitionRunner(
            hot_memory_manager=self.hot_memory,
            embedder=embedder,
        )

        backend = PromptComposerRetrievalBackend(self.retrieval)
        self.composer = PromptComposer(retrieval_backend=backend)

    def ingest_interaction(self, payload: dict[str, Any]) -> IngestionResult:
        result = self.ingestion.ingest_dict(payload)
        if not result.stored or not result.memory_id:
            return result

        memory = self.ingestion.json_store.get_memory(result.memory_id)
        if memory is not None:
            self.hot_memory.register_high_importance_memory(memory)
        return result

    def retrieve_context(self, user_message: str, conversation_history: str = "") -> RetrievalResult:
        result = self.retrieval.retrieve(
            user_message=user_message,
            conversation_history=conversation_history,
        )
        for ranked in result.selected:
            self.hot_memory.register_retrieval_hit(ranked.memory)
        return result

    def compose_prompt(self, request_payload: dict[str, Any]) -> PromptComposerOutput:
        payload = dict(request_payload)
        if "hot_memory" not in payload:
            payload["hot_memory"] = self.hot_memory.get().model_dump(mode="json")

        request = PromptComposerRequest.model_validate(payload)
        output = self.composer.compose(request)
        return output

    def run_background_cycle(self, *, scheduled: bool = True) -> BackgroundCognitionResult:
        if scheduled:
            return self.background.run_scheduled(CognitionScheduleState())
        return self.background.run_once()

    def process_turn(
        self,
        *,
        ingestion_payload: dict[str, Any],
        prompt_request_payload: dict[str, Any],
    ) -> CognitiveMemorySystemResult:
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
