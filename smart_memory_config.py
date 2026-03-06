"""Configuration surface for the Smart Memory v3.1 runtime."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StorageConfig:
    sqlite_path: str = "data/memory_store/v3_memory.sqlite"
    json_root: str = "data/memory_store"


@dataclass(frozen=True)
class RetrievalWeightsConfig:
    semantic_similarity: float = 0.35
    keyword_overlap: float = 0.15
    entity_overlap: float = 0.15
    importance: float = 0.10
    recency: float = 0.10
    lane_boost: float = 0.10
    temporal_validity: float = 0.05


@dataclass(frozen=True)
class RetrievalStatusConfig:
    active: bool = True
    superseded: bool = False
    expired: bool = False
    uncertain: bool = True
    archived: bool = False
    rejected: bool = False


@dataclass(frozen=True)
class RevisionThresholdsConfig:
    minimum_importance_to_store: float = 0.45
    semantic_dedup_threshold: float = 0.85
    merge_similarity_threshold: float = 0.97
    noop_similarity_threshold: float = 0.95
    uncertain_conflict_threshold: float = 0.55


@dataclass(frozen=True)
class LaneBudgetConfig:
    core_tokens: int = 600
    working_tokens: int = 500


@dataclass(frozen=True)
class LanePolicyConfig:
    core_confidence_threshold: float = 0.80
    core_importance_threshold: float = 0.75
    working_decay_hours: int = 48
    allow_core_trim: bool = False


@dataclass(frozen=True)
class EntityNormalizationConfig:
    max_entity_length: int = 64
    infer_types: bool = True


@dataclass(frozen=True)
class SmartMemoryV3Config:
    storage: StorageConfig = field(default_factory=StorageConfig)
    retrieval_weights: RetrievalWeightsConfig = field(default_factory=RetrievalWeightsConfig)
    retrieval_status: RetrievalStatusConfig = field(default_factory=RetrievalStatusConfig)
    revision_thresholds: RevisionThresholdsConfig = field(default_factory=RevisionThresholdsConfig)
    lane_budgets: LaneBudgetConfig = field(default_factory=LaneBudgetConfig)
    lane_policy: LanePolicyConfig = field(default_factory=LanePolicyConfig)
    entity_normalization: EntityNormalizationConfig = field(default_factory=EntityNormalizationConfig)
    llm_revision_enabled: bool = False
