"""Phase 3 retrieval pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from embeddings import TextEmbedder, create_default_embedder
from entities import EntityAliasResolver
from prompt_engine.schemas import LongTermMemory
from storage import JSONMemoryStore, VectorIndexStore

from .entity_detector import detect_entities_for_retrieval
from .reranker import RankedCandidate, RetrievalCandidate, rerank_candidates
from .time_filter import filter_by_time, parse_time_range


@dataclass(frozen=True)
class RetrievalPipelineConfig:
    candidate_pool_size: int = 30
    selected_size: int = 5


@dataclass(frozen=True)
class RetrievalResult:
    user_message: str
    entities: list[str]
    candidates: list[RetrievalCandidate]
    selected: list[RankedCandidate]
    degraded: bool
    error: str | None


class RetrievalPipeline:
    """Retrieve and rank long-term memories for context selection."""

    def __init__(
        self,
        *,
        json_store: JSONMemoryStore | None = None,
        vector_store: VectorIndexStore | None = None,
        embedder: TextEmbedder | None = None,
        entity_resolver: EntityAliasResolver | None = None,
        config: RetrievalPipelineConfig = RetrievalPipelineConfig(),
    ) -> None:
        self.json_store = json_store or JSONMemoryStore()
        self.vector_store = vector_store or VectorIndexStore()
        self.embedder = embedder or create_default_embedder()
        self.entity_resolver = entity_resolver or EntityAliasResolver()
        self.config = config

    def _mark_selected_as_accessed(
        self,
        selected: list[RankedCandidate],
        *,
        accessed_at: datetime,
    ) -> list[RankedCandidate]:
        """Persist access tracking for selected memories and return updated candidates."""

        updated_selected: list[RankedCandidate] = []

        for ranked in selected:
            memory = ranked.memory
            try:
                touched_memory = memory.model_copy(
                    update={
                        "last_accessed": accessed_at,
                        "access_count": memory.access_count + 1,
                    }
                )
                self.json_store.update_memory(touched_memory)
                updated_selected.append(
                    RankedCandidate(
                        memory=touched_memory,
                        score=ranked.score,
                        vector_score=ranked.vector_score,
                    )
                )
            except Exception:  # noqa: BLE001
                # Access tracking should not fail retrieval delivery.
                updated_selected.append(ranked)

        return updated_selected

    def retrieve(self, user_message: str, *, conversation_history: str = "") -> RetrievalResult:
        now = datetime.now(timezone.utc)

        detection = detect_entities_for_retrieval(
            user_message=user_message,
            conversation_history=conversation_history,
            resolver=self.entity_resolver,
        )

        try:
            query_vector = self.embedder.embed(user_message)
            vector_hits = self.vector_store.search(
                query_vector=query_vector,
                top_k=self.config.candidate_pool_size,
            )

            candidates: list[RetrievalCandidate] = []
            for hit in vector_hits:
                memory = self.json_store.get_memory(hit.memory_id)
                if memory is None:
                    continue
                candidates.append(RetrievalCandidate(memory=memory, vector_score=hit.score))

            time_range = parse_time_range(user_message, now=now)
            if time_range is not None:
                allowed_ids = {
                    memory.id
                    for memory in filter_by_time(
                        [candidate.memory for candidate in candidates],
                        time_range,
                    )
                }
                candidates = [
                    candidate for candidate in candidates if candidate.memory.id in allowed_ids
                ]

            selected = rerank_candidates(
                user_message=user_message,
                candidates=candidates,
                query_entities=detection.entities,
                top_k=self.config.selected_size,
            )
            selected = self._mark_selected_as_accessed(selected, accessed_at=now)

            return RetrievalResult(
                user_message=user_message,
                entities=detection.entities,
                candidates=candidates,
                selected=selected,
                degraded=False,
                error=None,
            )

        except Exception as error:  # noqa: BLE001
            return RetrievalResult(
                user_message=user_message,
                entities=detection.entities,
                candidates=[],
                selected=[],
                degraded=True,
                error=str(error),
            )

    def retrieve_candidates(
        self,
        user_message: str,
        *,
        entities: list[str] | None = None,
        max_candidates: int = 30,
    ) -> list[LongTermMemory]:
        """Return candidate memories for prompt-composer retrieval backend."""

        normalized_entities = (
            self.entity_resolver.canonicalize_many(entities) if entities else []
        )

        query_vector = self.embedder.embed(user_message)
        hits = self.vector_store.search(query_vector=query_vector, top_k=max_candidates)

        scored_memories: list[tuple[int, float, LongTermMemory]] = []
        for hit in hits:
            memory = self.json_store.get_memory(hit.memory_id)
            if memory is None:
                continue

            overlap = 0
            if normalized_entities:
                overlap = len(
                    set(entity.lower() for entity in normalized_entities)
                    & set(entity.lower() for entity in memory.entities)
                )

            # Sort by entity overlap first, then vector score.
            scored_memories.append((overlap, hit.score, memory))

        scored_memories.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [memory for _, __, memory in scored_memories[:max_candidates]]
