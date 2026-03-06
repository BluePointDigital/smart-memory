"""Evaluation metrics for Smart Memory v3.1."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvalMetrics:
    precision: float = 0.0
    recall: float = 0.0
    hit_ranking: list[str] = field(default_factory=list)
    incorrect_active_memory_count: int = 0
    stale_memory_leakage_count: int = 0
    token_budget_compliant: bool = True


@dataclass(frozen=True)
class EvalReport:
    mode: str
    suite_name: str
    case_id: str
    passed: bool
    metrics: EvalMetrics
    notes: list[str] = field(default_factory=list)
