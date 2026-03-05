"""Phase 2 ingestion pipeline.

Pipeline:
Incoming interaction
-> heuristic filter
-> entity extraction
-> importance scoring
-> (optional) LLM importance refinement
-> memory classification
-> memory object creation
-> embedding generation
-> persistence (JSON + vector index)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from embeddings import TextEmbedder, create_default_embedder
from entities import EntityAliasResolver
from prompt_engine.entity_extractor import extract_entities
from prompt_engine.schemas import MemoryType
from storage import JSONMemoryStore, VectorIndexStore

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
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class IngestionPipelineConfig:
    minimum_importance_to_store: float = 0.45
    min_words_for_heuristic: int = 8
    enable_llm_refinement: bool = True
    llm_trigger_count_threshold: int = 2
    llm_min_heuristic_score: float = 0.30
    semantic_dedup_threshold: float = 0.85


@dataclass(frozen=True)
class IngestionResult:
    stored: bool
    reason: str
    triggers: list[str]
    importance: float
    memory_id: str | None
    memory_type: MemoryType | None
    llm_used: bool = False


class IngestionPipeline:
    """Main ingestion orchestrator with deterministic behavior."""

    def __init__(
        self,
        *,
        json_store: JSONMemoryStore | None = None,
        vector_store: VectorIndexStore | None = None,
        embedder: TextEmbedder | None = None,
        entity_resolver: EntityAliasResolver | None = None,
        llm_scorer: ImportanceLLMScorer | None = None,
        config: IngestionPipelineConfig = IngestionPipelineConfig(),
    ) -> None:
        self.json_store = json_store or JSONMemoryStore()
        self.vector_store = vector_store or VectorIndexStore()
        self.embedder = embedder or create_default_embedder()
        self.entity_resolver = entity_resolver or EntityAliasResolver()
        self.llm_scorer = llm_scorer
        self.config = config

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
        # Hashing fallback is deterministic but too coarse for reliable semantic dedup.
        return "hashing" not in model_name

    def _find_semantic_duplicate(self, vector: list[float]) -> tuple[str, float] | None:
        try:
            hits = self.vector_store.search(query_vector=vector, top_k=1)
        except Exception:  # noqa: BLE001
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
            "last_accessed": now,
            "access_count": existing.access_count + 1,
        }

        if existing.type == MemoryType.BELIEF:
            updates["reinforced_count"] = existing.reinforced_count + 1

        reinforced = existing.model_copy(update=updates)
        self.json_store.update_memory(reinforced)
        return (str(reinforced.id), reinforced.type)

    def ingest(self, interaction: IncomingInteraction) -> IngestionResult:
        system_generated_insight = bool(
            interaction.metadata.get("system_generated_insight", False)
        )

        heuristic: HeuristicDecision = evaluate_heuristics(
            user_message=interaction.user_message,
            assistant_message=interaction.assistant_message,
            system_generated_insight=system_generated_insight,
            min_words=self.config.min_words_for_heuristic,
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

        if importance_score < self.config.minimum_importance_to_store:
            return IngestionResult(
                stored=False,
                reason="below_importance_threshold",
                triggers=heuristic.triggers,
                importance=importance_score,
                memory_id=None,
                memory_type=None,
                llm_used=llm_used,
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
                )

        self.json_store.save_memory(memory)

        self.vector_store.upsert_vector(
            memory_id=memory_id,
            vector=vector,
            model_name=self.embedder.model_name,
            payload={
                "memory_id": memory_id,
                "type": memory.type.value,
                "importance": round(memory.importance, 6),
                "created_at": memory.created_at.isoformat(),
                "source": memory.source.value,
                "entities": memory.entities,
                "schema_version": memory.schema_version,
            },
        )

        return IngestionResult(
            stored=True,
            reason="stored",
            triggers=heuristic.triggers,
            importance=importance_score,
            memory_id=memory_id,
            memory_type=memory_type,
            llm_used=llm_used,
        )

    def ingest_dict(self, payload: dict[str, Any]) -> IngestionResult:
        interaction = IncomingInteraction.model_validate(payload)
        return self.ingest(interaction)

    def ingest_many(self, payloads: list[dict[str, Any]]) -> list[IngestionResult]:
        results: list[IngestionResult] = []
        for payload in payloads:
            results.append(self.ingest_dict(payload))
        return results



