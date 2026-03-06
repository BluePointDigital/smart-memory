"""Retrieval pipeline with status-aware filtering and lane/entity boosts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from embeddings import TextEmbedder, create_default_embedder
from entities import EntityAliasResolver, RelationshipIndex
from prompt_engine.schemas import BaseMemory, LaneName, MemoryStatus
from smart_memory_config import SmartMemoryV3Config
from storage import SQLiteMemoryStore, VectorIndexStore

from .entity_detector import detect_entities_for_retrieval
from .reranker import RankedCandidate, RetrievalCandidate, rerank_candidates
from .time_filter import filter_by_time, parse_time_range


@dataclass(frozen=True)
class RetrievalPipelineConfig:
    candidate_pool_size: int = 30
    selected_size: int = 5
    v3: SmartMemoryV3Config = field(default_factory=SmartMemoryV3Config)


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
        memory_store: SQLiteMemoryStore | None = None,
        json_store: SQLiteMemoryStore | None = None,
        vector_store: VectorIndexStore | None = None,
        embedder: TextEmbedder | None = None,
        entity_resolver: EntityAliasResolver | None = None,
        config: RetrievalPipelineConfig = RetrievalPipelineConfig(),
    ) -> None:
        self.memory_store = memory_store or json_store or SQLiteMemoryStore(config.v3.storage.sqlite_path)
        self.json_store = self.memory_store
        self.vector_store = vector_store or VectorIndexStore(sqlite_path=self.memory_store.sqlite_path)
        self.embedder = embedder or create_default_embedder()
        self.entity_resolver = entity_resolver or EntityAliasResolver()
        self.relationship_index = RelationshipIndex(self.memory_store.sqlite_path)
        self.config = config

    def _lane_boosts(self) -> dict[str, float]:
        boosts: dict[str, float] = {}
        for lane_name, boost in ((LaneName.CORE, 1.0), (LaneName.WORKING, 0.75)):
            for memory in self.memory_store.get_lane_contents(lane_name):
                boosts[str(memory.id)] = max(boosts.get(str(memory.id), 0.0), boost)
        return boosts

    def _mark_selected_as_accessed(self, selected: list[RankedCandidate], *, accessed_at: datetime) -> list[RankedCandidate]:
        updated_selected: list[RankedCandidate] = []
        for ranked in selected:
            memory = ranked.memory
            try:
                touched_memory = memory.model_copy(
                    update={
                        "last_accessed_at": accessed_at,
                        "updated_at": accessed_at,
                        "access_count": memory.access_count + 1,
                    }
                )
                self.memory_store.update_memory(touched_memory)
                updated_selected.append(RankedCandidate(memory=touched_memory, score=ranked.score, vector_score=ranked.vector_score))
            except Exception:
                updated_selected.append(ranked)
        return updated_selected

    def _status_allowed(self, memory: BaseMemory, *, include_history: bool) -> bool:
        rules = self.config.v3.retrieval_status
        if memory.status == MemoryStatus.ACTIVE:
            return rules.active
        if memory.status == MemoryStatus.UNCERTAIN:
            return rules.uncertain
        if memory.status == MemoryStatus.ARCHIVED:
            return include_history or rules.archived
        if memory.status == MemoryStatus.SUPERSEDED:
            return include_history or rules.superseded
        if memory.status == MemoryStatus.EXPIRED:
            return include_history or rules.expired
        if memory.status == MemoryStatus.REJECTED:
            return rules.rejected
        return False

    def retrieve(
        self,
        user_message: str,
        *,
        conversation_history: str = "",
        include_history: bool = False,
        entity_scope: list[str] | None = None,
    ) -> RetrievalResult:
        now = datetime.now(timezone.utc)

        detection = detect_entities_for_retrieval(
            user_message=user_message,
            conversation_history=conversation_history,
            known_entities=entity_scope,
            resolver=self.entity_resolver,
        )
        expanded_entities = list(detection.entities)
        expanded_entities.extend(self.relationship_index.related_entities(detection.entities, limit=5))
        expanded_entities = self.entity_resolver.canonicalize_many(expanded_entities)

        try:
            query_vector = self.embedder.embed(user_message)
            vector_hits = self.vector_store.search(query_vector=query_vector, top_k=self.config.candidate_pool_size)
            lane_boosts = self._lane_boosts()

            candidates: list[RetrievalCandidate] = []
            for hit in vector_hits:
                memory = self.memory_store.get_memory(hit.memory_id)
                if memory is None:
                    continue
                if not self._status_allowed(memory, include_history=include_history):
                    continue
                if not include_history and memory.valid_to is not None and memory.valid_to < now:
                    continue
                candidates.append(
                    RetrievalCandidate(
                        memory=memory,
                        vector_score=hit.score,
                        lane_boost=lane_boosts.get(str(memory.id), 0.0),
                    )
                )

            time_range = parse_time_range(user_message, now=now)
            if time_range is not None:
                allowed_ids = {
                    memory.id
                    for memory in filter_by_time([candidate.memory for candidate in candidates], time_range)
                }
                candidates = [candidate for candidate in candidates if candidate.memory.id in allowed_ids]

            selected = rerank_candidates(
                user_message=user_message,
                candidates=candidates,
                query_entities=expanded_entities,
                weights=self.config.v3.retrieval_weights,
                top_k=self.config.selected_size,
                now=now,
            )
            selected = self._mark_selected_as_accessed(selected, accessed_at=now)

            self.memory_store.add_audit_event(
                "retrieval_executed",
                memory_ids=[str(item.memory.id) for item in selected],
                action="RETRIEVE",
                reason="status-aware retrieval executed",
                scores={"candidate_count": len(candidates), "selected_count": len(selected)},
                payload={"query": user_message, "include_history": include_history},
            )

            return RetrievalResult(
                user_message=user_message,
                entities=expanded_entities,
                candidates=candidates,
                selected=selected,
                degraded=False,
                error=None,
            )

        except Exception as error:
            return RetrievalResult(
                user_message=user_message,
                entities=expanded_entities,
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
        include_history: bool = False,
    ) -> list[BaseMemory]:
        result = self.retrieve(
            user_message,
            conversation_history="",
            include_history=include_history,
            entity_scope=entities,
        )
        return [candidate.memory for candidate in result.selected[:max_candidates]] or [candidate.memory for candidate in result.candidates[:max_candidates]]

    def retrieve_for_task(self, task_context: str) -> list[BaseMemory]:
        return self.retrieve_candidates(task_context, entities=[], max_candidates=self.config.selected_size)
