"""Transcript-first evaluation runner for Smart Memory v3.1."""

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
            reports.extend(self.run_eval_case(case["id"]))
        return reports

    def run_eval_case(self, case_id: str) -> list[EvalReport]:
        path = self.scenarios_dir / f"{case_id}.json"
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        reports: list[EvalReport] = []

        live_result = None
        for interaction in payload.get("messages", []):
            live_result = self.system.ingest_message(interaction)

        retrieval = self.system.retrieve(payload["query"], include_history=case_id.endswith("history") or payload.get("include_history", False))
        prompt = self.system.compose_prompt(
            {
                "agent_identity": payload.get("agent_identity", "smart-memory-eval"),
                "current_user_message": payload["query"],
                "conversation_history": payload.get("conversation_history", ""),
                "max_prompt_tokens": payload.get("max_prompt_tokens", 512),
            }
        )
        reports.append(self._build_report("live_ingest", payload, retrieval, prompt))

        self.system.rebuild_all_memory_state()
        replay_retrieval = self.system.retrieve(payload["query"], include_history=payload.get("include_history", False))
        replay_prompt = self.system.compose_prompt(
            {
                "agent_identity": payload.get("agent_identity", "smart-memory-eval"),
                "current_user_message": payload["query"],
                "conversation_history": payload.get("conversation_history", ""),
                "max_prompt_tokens": payload.get("max_prompt_tokens", 512),
            }
        )
        reports.append(self._build_report("full_replay", payload, replay_retrieval, replay_prompt))

        session_id = payload.get("session_id_for_partial_replay") or (live_result.session_id if live_result is not None else None)
        partial_report = self.system.rebuild_from_transcripts(session_id=session_id)
        partial_retrieval = self.system.retrieve(payload["query"], include_history=payload.get("include_history", False))
        partial_prompt = self.system.compose_prompt(
            {
                "agent_identity": payload.get("agent_identity", "smart-memory-eval"),
                "current_user_message": payload["query"],
                "conversation_history": payload.get("conversation_history", ""),
                "max_prompt_tokens": payload.get("max_prompt_tokens", 512),
            }
        )
        partial_eval = self._build_report("partial_replay", payload, partial_retrieval, partial_prompt)
        partial_eval.notes.append(f"rebuild_scope={partial_report.scope}")
        reports.append(partial_eval)

        reports.append(self._build_evidence_report(payload, replay_retrieval))
        return reports

    def _build_report(self, mode: str, case: dict, retrieval, prompt) -> EvalReport:
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
            notes=list(case.get("notes", [])),
        )

    def _build_evidence_report(self, case: dict, retrieval) -> EvalReport:
        focus_substring = (case.get("focus_substring") or next(iter(case.get("expected_substrings", [])), "")).lower()
        focus_memory = None
        for candidate in retrieval.selected:
            if focus_substring and focus_substring in candidate.memory.content.lower():
                focus_memory = candidate.memory
                break
        if focus_memory is None and retrieval.selected:
            focus_memory = retrieval.selected[0].memory

        evidence = [] if focus_memory is None else self.system.get_memory_evidence(str(focus_memory.id))
        passed = focus_memory is not None and len(evidence) > 0
        return EvalReport(
            mode="evidence_backed",
            suite_name=case.get("suite", "default"),
            case_id=case["id"],
            passed=passed,
            metrics=EvalMetrics(
                precision=1.0 if passed else 0.0,
                recall=1.0 if passed else 0.0,
                hit_ranking=[str(focus_memory.id)] if focus_memory is not None else [],
                incorrect_active_memory_count=0,
                stale_memory_leakage_count=0,
                token_budget_compliant=True,
            ),
            notes=[f"evidence_rows={len(evidence)}"],
        )
