"""Transcript-first, revision-aware ingestion pipeline for Smart Memory v3.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from embeddings import TextEmbedder, create_default_embedder
from entities import EntityAliasResolver, EntityRegistry, RelationshipIndex
from memory_lanes import CoreMemoryManager, WorkingMemoryManager
from prompt_engine.entity_extractor import extract_entities
from prompt_engine.schemas import MemoryType, RevisionAction
from revision import MemoryRevisionEngine
from smart_memory_config import SmartMemoryV3Config
from storage import SQLiteMemoryStore, VectorIndexStore
from transcripts import TranscriptLogger, TranscriptMessage, TranscriptStore

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
    source_session_id: str | None = None
    source_message_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    label: str = ""


class TranscriptMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str | None = None
    role: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    content: str = Field(min_length=1)
    created_at: datetime | None = None
    tool_name: str | None = None
    parent_message_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    label: str = ""
    active_projects: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=lambda: ["user", "assistant"])


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
    memory_ids: list[str] = field(default_factory=list)
    session_id: str | None = None
    transcript_message_ids: list[str] = field(default_factory=list)


class IngestionPipeline:
    """Main ingestion orchestrator with transcript-first deterministic revision behavior."""

    def __init__(
        self,
        *,
        memory_store: SQLiteMemoryStore | None = None,
        json_store: SQLiteMemoryStore | None = None,
        vector_store: VectorIndexStore | None = None,
        embedder: TextEmbedder | None = None,
        entity_resolver: EntityAliasResolver | None = None,
        llm_scorer: ImportanceLLMScorer | None = None,
        config: IngestionPipelineConfig = IngestionPipelineConfig(),
    ) -> None:
        self.memory_store = memory_store or json_store or SQLiteMemoryStore(config.v3.storage.sqlite_path)
        self.json_store = self.memory_store
        self.vector_store = vector_store or VectorIndexStore(sqlite_path=self.memory_store.sqlite_path)
        self.embedder = embedder or create_default_embedder()
        registry = EntityRegistry(sqlite_path=self.memory_store.sqlite_path)
        self.entity_resolver = entity_resolver or EntityAliasResolver(registry=registry)
        self.llm_scorer = llm_scorer
        self.config = config
        self.transcript_store = TranscriptStore(self.memory_store.sqlite_path)
        self.transcript_logger = TranscriptLogger(self.transcript_store)
        self.revision_engine = MemoryRevisionEngine(
            memory_store=self.memory_store,
            transcript_store=self.transcript_store,
            config=config.v3,
        )
        self.core_lane = CoreMemoryManager(self.memory_store)
        self.working_lane = WorkingMemoryManager(self.memory_store, config=config.v3.lane_policy)
        self.relationship_index = RelationshipIndex(self.memory_store.sqlite_path)

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

    def _sync_existing_memory_evidence(self, memory_id: str, *, message_ids: list[str], confidence: float, now: datetime) -> tuple[str, MemoryType] | None:
        existing = self.memory_store.get_memory(memory_id)
        if existing is None:
            return None

        if message_ids and not existing.synthetic:
            self.transcript_store.link_memory_evidence_batch(
                memory_id=str(existing.id),
                message_ids=message_ids,
                evidence_kind="noop_source",
                confidence=confidence,
            )
            source_message_ids, evidence_count, evidence_summary, session_id = self.transcript_store.evidence_snapshot(str(existing.id))
        else:
            source_message_ids = existing.source_message_ids
            evidence_count = existing.evidence_count
            evidence_summary = existing.evidence_summary
            session_id = existing.source_session_id

        updates: dict[str, Any] = {
            "last_accessed_at": now,
            "updated_at": now,
            "access_count": existing.access_count + 1,
            "source_message_ids": source_message_ids,
            "source_session_id": session_id,
            "evidence_count": evidence_count,
            "evidence_summary": evidence_summary,
        }
        if hasattr(existing, "reinforced_count"):
            updates["reinforced_count"] = getattr(existing, "reinforced_count", 1) + 1

        reinforced = existing.model_copy(update=updates)
        self.memory_store.update_memory(reinforced)
        return (str(reinforced.id), reinforced.memory_type)

    def _apply_downstream_updates(self, stored_memory) -> None:
        vector = self.embedder.embed(stored_memory.content)
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
                "evidence_count": stored_memory.evidence_count,
                "synthetic": stored_memory.synthetic,
            },
        )
        self.relationship_index.record_cooccurrence(stored_memory.entities, memory_id=str(stored_memory.id))
        self.core_lane.evaluate_memory(stored_memory)
        self.working_lane.evaluate_memory(stored_memory)

    def _aggregate_results(
        self,
        *,
        session_id: str | None,
        transcript_message_ids: list[str],
        results: list[IngestionResult],
    ) -> IngestionResult:
        if not results:
            return IngestionResult(
                stored=False,
                reason="no_transcript_messages_processed",
                triggers=[],
                importance=0.0,
                memory_id=None,
                memory_type=None,
                session_id=session_id,
                transcript_message_ids=transcript_message_ids,
            )

        combined_triggers: list[str] = []
        seen_triggers: set[str] = set()
        memory_ids: list[str] = []
        seen_memory_ids: set[str] = set()
        target_memory_ids: list[str] = []
        seen_targets: set[str] = set()
        chosen_memory_id: str | None = None
        chosen_memory_type: MemoryType | None = None
        primary_result = next(
            (
                result
                for result in reversed(results)
                if result.stored or result.memory_id is not None or result.action != RevisionAction.REJECT.value
            ),
            results[-1],
        )
        action = primary_result.action
        reason = primary_result.reason
        llm_used = any(result.llm_used for result in results)
        importance = max((result.importance for result in results), default=0.0)
        stored = any(result.stored for result in results)

        for result in results:
            for trigger in result.triggers:
                if trigger not in seen_triggers:
                    combined_triggers.append(trigger)
                    seen_triggers.add(trigger)
            for memory_id in result.memory_ids or ([result.memory_id] if result.memory_id else []):
                if memory_id and memory_id not in seen_memory_ids:
                    memory_ids.append(memory_id)
                    seen_memory_ids.add(memory_id)
            for target_id in result.target_memory_ids:
                if target_id not in seen_targets:
                    target_memory_ids.append(target_id)
                    seen_targets.add(target_id)
            if result.memory_id is not None:
                chosen_memory_id = result.memory_id
                chosen_memory_type = result.memory_type

        return IngestionResult(
            stored=stored,
            reason=reason,
            triggers=combined_triggers,
            importance=importance,
            memory_id=chosen_memory_id,
            memory_type=chosen_memory_type,
            llm_used=llm_used,
            action=action,
            target_memory_ids=target_memory_ids,
            memory_ids=memory_ids,
            session_id=session_id,
            transcript_message_ids=transcript_message_ids,
        )

    def ingest_transcript_message(
        self,
        message: TranscriptMessage,
        *,
        active_projects: list[str] | None = None,
        participants: list[str] | None = None,
        replay_mode: bool = False,
    ) -> IngestionResult:
        active_projects = list(active_projects or [])
        participants = list(participants or ["user", "assistant"])
        adjacent_context = self.transcript_store.get_adjacent_context(message, window=1)
        system_generated_insight = bool(message.metadata.get("system_generated_insight", False))

        heuristic: HeuristicDecision = evaluate_heuristics(
            user_message=message.content,
            assistant_message=adjacent_context,
            system_generated_insight=system_generated_insight,
            min_words=self.config.min_words_for_heuristic,
        )

        self.memory_store.add_audit_event(
            "candidate_extracted",
            reason="transcript message evaluated for durable memory",
            source_session_id=message.session_id,
            source_message_ids=[message.message_id],
            payload={"triggers": heuristic.triggers, "role": message.role, "replay_mode": replay_mode},
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
                session_id=message.session_id,
                transcript_message_ids=[message.message_id],
            )

        raw_entities = extract_entities(
            current_user_message=message.content,
            conversation_history=adjacent_context,
            active_projects=active_projects,
        )
        entities = self.entity_resolver.canonicalize_many(raw_entities)

        importance_breakdown: ImportanceBreakdown = score_importance(
            user_message=message.content,
            assistant_message=adjacent_context,
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
                user_message=message.content,
                assistant_message=adjacent_context,
                heuristic_score=importance_score,
                entity_count=len(entities),
                triggers=heuristic.triggers,
            )
            importance_score = clamp_importance((importance_score * 0.6) + (llm_score * 0.4))
            llm_used = True

        self.memory_store.add_audit_event(
            "candidate_scored",
            reason="importance score computed from transcript-backed candidate",
            scores={"importance": round(importance_score, 6)},
            source_session_id=message.session_id,
            source_message_ids=[message.message_id],
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
                session_id=message.session_id,
                transcript_message_ids=[message.message_id],
            )

        memory_type = classify_memory_type(
            user_message=message.content,
            assistant_message=adjacent_context,
        )

        memory = build_memory_object(
            memory_type=memory_type,
            user_message=message.content,
            assistant_message=adjacent_context,
            importance=importance_score,
            source=message.source_type,
            timestamp=message.created_at,
            participants=participants,
            active_projects=active_projects,
            entities_override=entities,
            entity_resolver=self.entity_resolver,
            source_session_id=message.session_id,
            source_message_ids=[message.message_id],
            derivation_method="transcript_message",
            synthetic=False,
            explanation=f"derived from transcript {message.role} message",
        )

        vector = self.embedder.embed(memory.content)
        duplicate = self._find_semantic_duplicate(vector) if self._supports_semantic_dedup() else None
        if duplicate is not None:
            existing_id, _score = duplicate
            reinforced = self._sync_existing_memory_evidence(
                existing_id,
                message_ids=[message.message_id],
                confidence=memory.confidence,
                now=message.created_at,
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
                    memory_ids=[reinforced_id],
                    session_id=message.session_id,
                    transcript_message_ids=[message.message_id],
                )

        revision_result = self.revision_engine.revise(memory, rebuilt_at=message.created_at if replay_mode else None)
        stored_memory = revision_result.stored_memory

        if stored_memory is not None:
            self._apply_downstream_updates(stored_memory)

        resolved_memory_id = None
        resolved_memory_ids: list[str] = []
        if stored_memory is not None:
            resolved_memory_id = str(stored_memory.id)
            resolved_memory_ids = [resolved_memory_id]
        elif revision_result.target_memory_ids:
            resolved_memory_id = revision_result.target_memory_ids[0]
            resolved_memory_ids = list(revision_result.target_memory_ids)

        return IngestionResult(
            stored=stored_memory is not None,
            reason=revision_result.audit_reason,
            triggers=heuristic.triggers,
            importance=importance_score,
            memory_id=resolved_memory_id,
            memory_type=stored_memory.memory_type if stored_memory is not None else memory_type,
            llm_used=llm_used,
            action=revision_result.action.value,
            target_memory_ids=revision_result.target_memory_ids,
            memory_ids=resolved_memory_ids,
            session_id=message.session_id,
            transcript_message_ids=[message.message_id],
        )

    def ingest(self, interaction: IncomingInteraction) -> IngestionResult:
        appended = self.transcript_logger.append_interaction(
            session_id=interaction.source_session_id,
            user_message=interaction.user_message,
            assistant_message=interaction.assistant_message,
            created_at=interaction.timestamp,
            source_type=interaction.source,
            metadata=interaction.metadata,
            label=interaction.label,
        )
        results = [
            self.ingest_transcript_message(
                message,
                active_projects=interaction.active_projects,
                participants=interaction.participants,
            )
            for message in appended.messages
        ]
        return self._aggregate_results(
            session_id=appended.session.session_id,
            transcript_message_ids=[message.message_id for message in appended.messages],
            results=results,
        )

    def append_transcript_message(self, payload: dict[str, Any]) -> IngestionResult:
        request = TranscriptMessageRequest.model_validate(payload)
        appended = self.transcript_logger.append_message(
            session_id=request.session_id,
            role=request.role,
            source_type=request.source_type,
            content=request.content,
            created_at=request.created_at,
            tool_name=request.tool_name,
            parent_message_id=request.parent_message_id,
            metadata=request.metadata,
            label=request.label,
        )
        results = [
            self.ingest_transcript_message(
                message,
                active_projects=request.active_projects,
                participants=request.participants,
            )
            for message in appended.messages
        ]
        return self._aggregate_results(
            session_id=appended.session.session_id,
            transcript_message_ids=[message.message_id for message in appended.messages],
            results=results,
        )

    def ingest_dict(self, payload: dict[str, Any]) -> IngestionResult:
        interaction = IncomingInteraction.model_validate(payload)
        return self.ingest(interaction)

    def ingest_many(self, payloads: list[dict[str, Any]]) -> list[IngestionResult]:
        return [self.ingest_dict(payload) for payload in payloads]

