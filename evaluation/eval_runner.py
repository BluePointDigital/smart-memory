"""Scenario-based evaluation runner for Smart Memory v3."""

from __future__ import annotations

import json
from pathlib import Path

from .metrics import EvalMetrics, EvalReport


class EvalRunner:
    def __init__(self, system) -> None:
        self.system = system
        self.scenarios_dir = Path(__file__).resolve().parent / "scenarios"

    def _load_cases(self, suite_name: str) -> list[dict]:
        cases: list[dict] = []
        for path in sorted(self.scenarios_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if payload.get("suite") == suite_name:
                cases.append(payload)
        return cases

    def run_eval_suite(self, suite_name: str) -> list[EvalReport]:
        reports: list[EvalReport] = []
        for case in self._load_cases(suite_name):
            reports.append(self.run_eval_case(case["id"]))
        return reports

    def run_eval_case(self, case_id: str) -> list[EvalReport]:
        path = self.scenarios_dir / f"{case_id}.json"
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        reports: list[EvalReport] = []
        for mode in ("baseline_v2", "v3_revision_only", "v3_full"):
            reports.append(self._run_mode(mode, payload))
        return reports

    def _run_mode(self, mode: str, case: dict) -> EvalReport:
        for interaction in case.get("messages", []):
            self.system.ingest_message(interaction)

        retrieval = self.system.retrieve(case["query"], include_history=case.get("include_history", False))
        prompt = self.system.compose_prompt(
            {
                "agent_identity": case.get("agent_identity", "smart-memory-eval"),
                "current_user_message": case["query"],
                "conversation_history": case.get("conversation_history", ""),
                "max_prompt_tokens": case.get("max_prompt_tokens", 512),
            }
        )

        expected = [value.lower() for value in case.get("expected_substrings", [])]
        selected_text = [candidate.memory.content.lower() for candidate in retrieval.selected]
        hits = [text for text in selected_text if any(expected_item in text for expected_item in expected)]
        precision = len(hits) / max(1, len(selected_text))
        recall = len(hits) / max(1, len(expected))
        stale_leakage = sum(1 for candidate in retrieval.selected if candidate.memory.status.value in {"superseded", "expired"})
        incorrect_active = sum(1 for memory in self.system.memory_store.list_memories() if memory.status.value != "active")
        compliant = len(prompt.prompt.split()) <= case.get("max_prompt_tokens", 512) * 2
        passed = recall >= case.get("minimum_recall", 0.5) and stale_leakage <= case.get("max_stale_leakage", 0)

        return EvalReport(
            mode=mode,
            suite_name=case.get("suite", "default"),
            case_id=case["id"],
            passed=passed,
            metrics=EvalMetrics(
                precision=precision,
                recall=recall,
                hit_ranking=[str(candidate.memory.id) for candidate in retrieval.selected],
                incorrect_active_memory_count=incorrect_active,
                stale_memory_leakage_count=stale_leakage,
                token_budget_compliant=compliant,
            ),
            notes=case.get("notes", []),
        )
