"""Prompt Composer orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .entity_extractor import extract_entities
from .memory_reranker import rerank_memories
from .memory_retriever import RetrievalBackend, retrieve_with_fallback
from .prompt_renderer import estimate_tokens, render_prompt
from .schemas import (
    InsightObject,
    InteractionState,
    LaneName,
    MemoryInclusionTrace,
    PromptComposerOutput,
    PromptComposerRequest,
)
from .state_detector import build_temporal_state
from .token_allocator import allocate_tokens


@dataclass(frozen=True)
class PromptComposerConfig:
    insight_confidence_threshold: float = 0.65
    allow_core_trim: bool = False


class PromptComposer:
    """Composable prompt engine with graceful degradation guarantees."""

    def __init__(self, retrieval_backend: RetrievalBackend | None = None, *, config: PromptComposerConfig | None = None) -> None:
        self.retrieval_backend = retrieval_backend
        self.config = config or PromptComposerConfig()

    def compose(self, request: PromptComposerRequest) -> PromptComposerOutput:
        now = datetime.now(timezone.utc)

        temporal_state = build_temporal_state(
            current_user_message=request.current_user_message,
            last_interaction_timestamp=request.last_interaction_timestamp,
            now=now,
        )

        entities = extract_entities(
            current_user_message=request.current_user_message,
            conversation_history=request.conversation_history,
            active_projects=request.hot_memory.active_projects,
        )

        retrieval = retrieve_with_fallback(
            query=request.current_user_message,
            entities=entities,
            backend=self.retrieval_backend,
            max_candidates=request.max_candidate_memories,
            timeout_ms=request.retrieval_timeout_ms,
        )

        selected_memories = rerank_memories(
            candidates=retrieval.candidates,
            query=request.current_user_message,
            entities=entities,
            top_k=request.max_selected_memories,
            now=now,
        )

        selected_insights = self._select_insights(
            queue=request.hot_memory.insight_queue,
            query=request.current_user_message,
            interaction_state=temporal_state.interaction_state,
            now=now,
        )

        token_allocation = allocate_tokens(
            total_tokens=request.max_prompt_tokens,
            interaction_state=temporal_state.interaction_state,
            include_retrieved_memory=bool(selected_memories),
            include_insights=bool(selected_insights),
            include_core_memory=bool(request.core_memories),
        )

        prompt = render_prompt(
            agent_identity=request.agent_identity,
            temporal_state=temporal_state,
            hot_memory=request.hot_memory,
            core_memories=request.core_memories,
            retrieved_memories=selected_memories,
            selected_insights=selected_insights,
            conversation_history=request.conversation_history,
            current_user_message=request.current_user_message,
            token_allocation=token_allocation,
            allow_core_trim=self.config.allow_core_trim,
        )

        traces: list[MemoryInclusionTrace] = []
        for memory in request.core_memories:
            traces.append(
                MemoryInclusionTrace(
                    memory_id=memory.id,
                    lane=LaneName.CORE,
                    memory_type=memory.memory_type,
                    status=memory.status,
                    inclusion_reason="core_lane",
                    token_estimate=estimate_tokens(memory.content),
                )
            )
        for memory in selected_memories:
            traces.append(
                MemoryInclusionTrace(
                    memory_id=memory.id,
                    lane=LaneName.RETRIEVED,
                    memory_type=memory.memory_type,
                    status=memory.status,
                    inclusion_reason="retrieval_match",
                    token_estimate=estimate_tokens(memory.content),
                )
            )

        degraded: list[str] = []
        if retrieval.degraded:
            degraded.append("memory_retrieval")

        return PromptComposerOutput(
            prompt=prompt,
            interaction_state=temporal_state.interaction_state,
            temporal_state=temporal_state,
            entities=entities,
            selected_memories=selected_memories,
            selected_insights=selected_insights,
            token_allocation=token_allocation,
            degraded_subsystems=degraded,
            memory_traces=traces,
            metadata={
                "retrieval_elapsed_ms": retrieval.elapsed_ms,
                "retrieval_error": retrieval.error,
                "candidate_count": len(retrieval.candidates),
                "selected_memory_count": len(selected_memories),
                "selected_insight_count": len(selected_insights),
            },
        )

    def _select_insights(
        self,
        *,
        queue: Iterable[InsightObject],
        query: str,
        interaction_state: InteractionState,
        now: datetime,
    ) -> list[InsightObject]:
        if interaction_state != InteractionState.RETURNING:
            return []

        query_terms = {term.lower() for term in query.split() if len(term) >= 3}
        selected: list[InsightObject] = []

        for insight in queue:
            if insight.confidence < self.config.insight_confidence_threshold:
                continue
            if insight.expires_at is not None and insight.expires_at < now:
                continue

            insight_terms = {term.lower() for term in insight.content.split() if len(term) >= 3}
            if query_terms and not (query_terms & insight_terms):
                continue

            selected.append(insight)

        return selected
