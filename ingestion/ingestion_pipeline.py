"""Revision-aware ingestion pipeline for Smart Memory v3."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from embeddings import TextEmbedder, create_default_embedder
from entities import EntityAliasResolver, RelationshipIndex
from memory_lanes import CoreMemoryManager, WorkingMemoryManager
from prompt_engine.entity_extractor import extract_entities
from prompt_engine.schemas import MemoryType, RevisionAction
from revision import MemoryRevisionEngine
from smart_memory_config import SmartMemoryV3Config
from storage import JSONMemoryStore, SQLiteMemoryStore, VectorIndexStore

from .heuristic_filter import HeuristicDecision, evaluate_heuristics
from .importance_llm import ImportanceLLMScorer, clamp_importance
from .importance_scorer import ImportanceBreakdown, score_importance
from .memory_builder import build_memory_object
from .memory_classifier import classify_memory_type


class IncomingInteraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_message: str = Field(min_length=1)
    assistant_message: str = ""
    timestamp: datetime | None = None
    source: str = "conversation"
    participants: list[str] = Field(default_factory=lambda: ["user", "assistant"])
    active_projects: list[str] = Field(default_factory=list)
    source_session_id: str = "unknown"
    source_message_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class IngestionPipelineConfig:
    minimum_importance_to_store: float = 0.45
    min_words_for_heuristic: int = 8
    enable_llm_refinement: bool = True
    llm_trigger_count_threshold: int = 2
    llm_min_heuristic_score: float = 0.30
    semantic_dedup_threshold: float = 0.85
    v3: SmartMemoryV3Config = field(default_factory=SmartMemoryV3Config)


@dataclass(frozen=True)
class IngestionResult:
    stored: bool
    reason: str
    triggers: list[str]
    importance: float
    memory_id: str | None
    memory_type: MemoryType | None
    llm_used: bool = False
    action: str = RevisionAction.ADD.value
    target_memory_ids: list[str] = field(default_factory=list)


class IngestionPipeline:
    """Main ingestion orchestrator with deterministic revision behavior."""

    def __init__(
        self,
        *,
        json_store: JSONMemoryStore | SQLiteMemoryStore | None = None,
        vector_store: VectorIndexStore | None = None,
        embedder: TextEmbedder | None = None,
        entity_resolver: EntityAliasResolver | None = None,
        llm_scorer: ImportanceLLMScorer | None = None,
        config: IngestionPipelineConfig = IngestionPipelineConfig(),
    ) -> None:
        self.json_store = json_store or SQLiteMemoryStore(config.v3.storage.sqlite_path)
        self.vector_store = vector_store or VectorIndexStore(
            sqlite_path=getattr(self.json_store, "sqlite_path", config.v3.storage.sqlite_path)
        )
        self.embedder = embedder or create_default_embedder()
        self.entity_resolver = entity_resolver or EntityAliasResolver()
        self.llm_scorer = llm_scorer
        self.config = config
        self.revision_engine = MemoryRevisionEngine(memory_store=self.json_store, config=config.v3)
        self.core_lane = CoreMemoryManager(self.json_store)
        self.working_lane = WorkingMemoryManager(self.json_store, config=config.v3.lane_policy)
        self.relationship_index = RelationshipIndex(getattr(self.json_store, "sqlite_path", config.v3.storage.sqlite_path))

    def _should_refine_with_llm(
        self,
        *,
        heuristic: HeuristicDecision,
        heuristic_importance: float,
        system_generated_insight: bool,
    ) -> bool:
        if self.llm_scorer is None or not self.config.enable_llm_refinement:
            return False

        if system_generated_insight:
            return True

        if len(heuristic.triggers) >= self.config.llm_trigger_count_threshold:
            return True

        if heuristic_importance >= self.config.llm_min_heuristic_score:
            return True

        return False

    def _supports_semantic_dedup(self) -> bool:
        model_name = str(getattr(self.embedder, "model_name", "")).lower()
        return "hashing" not in model_name

    def _find_semantic_duplicate(self, vector: list[float]) -> tuple[str, float] | None:
        try:
            hits = self.vector_store.search(query_vector=vector, top_k=1)
        except Exception:
            return None

        if not hits:
            return None

        top = hits[0]
        if top.score <= self.config.semantic_dedup_threshold:
            return None

        return (top.memory_id, top.score)

    def _reinforce_existing_memory(self, memory_id: str, *, now: datetime) -> tuple[str, MemoryType] | None:
        existing = self.json_store.get_memory(memory_id)
        if existing is None:
            return None

        updates: dict[str, Any] = {
            "last_accessed_at": now,
            "updated_at": now,
            "access_count": existing.access_count + 1,
        }
        if hasattr(existing, "reinforced_count"):
            updates["reinforced_count"] = getattr(existing, "reinforced_count", 1) + 1

        reinforced = existing.model_copy(update=updates)
        self.json_store.update_memory(reinforced)
        return (str(reinforced.id), reinforced.memory_type)

    def ingest(self, interaction: IncomingInteraction) -> IngestionResult:
        system_generated_insight = bool(interaction.metadata.get("system_generated_insight", False))

        heuristic: HeuristicDecision = evaluate_heuristics(
            user_message=interaction.user_message,
            assistant_message=interaction.assistant_message,
            system_generated_insight=system_generated_insight,
            min_words=self.config.min_words_for_heuristic,
        )

        if hasattr(self.json_store, "add_audit_event"):
            self.json_store.add_audit_event(
                "candidate_extracted",
                reason="heuristic filter evaluated",
                source_session_id=interaction.source_session_id,
                source_message_ids=interaction.source_message_ids,
                payload={"triggers": heuristic.triggers},
            )

        if not heuristic.should_continue:
            return IngestionResult(
                stored=False,
                reason="no_heuristic_triggers",
                triggers=heuristic.triggers,
                importance=0.0,
                memory_id=None,
                memory_type=None,
                llm_used=False,
                action=RevisionAction.REJECT.value,
            )

        raw_entities = extract_entities(
            current_user_message=interaction.user_message,
            conversation_history=interaction.assistant_message,
            active_projects=interaction.active_projects,
        )
        entities = self.entity_resolver.canonicalize_many(raw_entities)

        importance_breakdown: ImportanceBreakdown = score_importance(
            user_message=interaction.user_message,
            assistant_message=interaction.assistant_message,
            entity_count=len(entities),
        )

        importance_score = importance_breakdown.score
        llm_used = False

        if self._should_refine_with_llm(
            heuristic=heuristic,
            heuristic_importance=importance_score,
            system_generated_insight=system_generated_insight,
        ):
            llm_score = self.llm_scorer.score_importance(
                user_message=interaction.user_message,
                assistant_message=interaction.assistant_message,
                heuristic_score=importance_score,
                entity_count=len(entities),
                triggers=heuristic.triggers,
            )
            importance_score = clamp_importance((importance_score * 0.6) + (llm_score * 0.4))
            llm_used = True

        if hasattr(self.json_store, "add_audit_event"):
            self.json_store.add_audit_event(
                "candidate_scored",
                reason="importance score computed",
                scores={"importance": round(importance_score, 6)},
                source_session_id=interaction.source_session_id,
                source_message_ids=interaction.source_message_ids,
            )

        if importance_score < self.config.minimum_importance_to_store:
            return IngestionResult(
                stored=False,
                reason="below_importance_threshold",
                triggers=heuristic.triggers,
                importance=importance_score,
                memory_id=None,
                memory_type=None,
                llm_used=llm_used,
                action=RevisionAction.REJECT.value,
            )

        memory_type = classify_memory_type(
            user_message=interaction.user_message,
            assistant_message=interaction.assistant_message,
        )

        memory = build_memory_object(
            memory_type=memory_type,
            user_message=interaction.user_message,
            assistant_message=interaction.assistant_message,
            importance=importance_score,
            source=interaction.source,
            timestamp=interaction.timestamp,
            participants=interaction.participants,
            active_projects=interaction.active_projects,
            entities_override=entities,
            entity_resolver=self.entity_resolver,
            source_session_id=interaction.source_session_id,
            source_message_ids=interaction.source_message_ids,
        )

        memory_id = str(memory.id)
        vector = self.embedder.embed(memory.content)

        duplicate = self._find_semantic_duplicate(vector) if self._supports_semantic_dedup() else None
        if duplicate is not None:
            existing_id, _score = duplicate
            reinforced = self._reinforce_existing_memory(
                existing_id,
                now=interaction.timestamp or datetime.now(timezone.utc),
            )
            if reinforced is not None:
                reinforced_id, reinforced_type = reinforced
                return IngestionResult(
                    stored=False,
                    reason="semantic_duplicate_reinforced",
                    triggers=heuristic.triggers,
                    importance=importance_score,
                    memory_id=reinforced_id,
                    memory_type=reinforced_type,
                    llm_used=llm_used,
                    action=RevisionAction.NOOP.value,
                    target_memory_ids=[reinforced_id],
                )

        revision_result = self.revision_engine.revise(memory)
        stored_memory = revision_result.stored_memory

        if stored_memory is not None:
            self.vector_store.upsert_vector(
                memory_id=str(stored_memory.id),
                vector=vector,
                model_name=self.embedder.model_name,
                payload={
                    "memory_id": str(stored_memory.id),
                    "memory_type": stored_memory.memory_type.value,
                    "importance_score": round(stored_memory.importance_score, 6),
                    "created_at": stored_memory.created_at.isoformat(),
                    "source": stored_memory.source.value,
                    "entities": stored_memory.entities,
                    "schema_version": stored_memory.schema_version,
                    "status": stored_memory.status.value,
                },
            )
            self.relationship_index.record_cooccurrence(stored_memory.entities, memory_id=str(stored_memory.id))
            self.core_lane.evaluate_memory(stored_memory)
            self.working_lane.evaluate_memory(stored_memory)

        return IngestionResult(
            stored=stored_memory is not None,
            reason=revision_result.audit_reason,
            triggers=heuristic.triggers,
            importance=importance_score,
            memory_id=str(stored_memory.id) if stored_memory is not None else (revision_result.target_memory_ids[0] if revision_result.target_memory_ids else None),
            memory_type=stored_memory.memory_type if stored_memory is not None else memory_type,
            llm_used=llm_used,
            action=revision_result.action.value,
            target_memory_ids=revision_result.target_memory_ids,
        )

    def ingest_dict(self, payload: dict[str, Any]) -> IngestionResult:
        interaction = IncomingInteraction.model_validate(payload)
        return self.ingest(interaction)

    def ingest_many(self, payloads: list[dict[str, Any]]) -> list[IngestionResult]:
        return [self.ingest_dict(payload) for payload in payloads]
