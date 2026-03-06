from __future__ import annotations

from cognitive_memory_system import CognitiveMemorySystem
from smart_memory_config import SmartMemoryV3Config, StorageConfig


def test_rebuild_from_transcripts_preserves_active_memory_state(tmp_path):
    config = SmartMemoryV3Config(storage=StorageConfig(sqlite_path=str(tmp_path / "memory.sqlite"), json_root=str(tmp_path / "json")))
    system = CognitiveMemorySystem(config=config)

    first = system.ingest_interaction(
        {
            "user_message": "I prefer tea for morning work.",
            "assistant_message": "Captured your preference.",
            "source_session_id": "sess_pref_a",
        }
    )
    second = system.ingest_interaction(
        {
            "user_message": "I prefer coffee now instead of tea.",
            "assistant_message": "Updated preference noted.",
            "source_session_id": "sess_pref_b",
        }
    )

    before = system.retrieve("What drink do I prefer now?")
    before_ids = [str(item.memory.id) for item in before.selected]
    assert second.memory_id is not None
    assert system.get_memory_evidence(second.memory_id)

    report = system.rebuild_all_memory_state()
    after = system.retrieve("What drink do I prefer now?")
    after_ids = [str(item.memory.id) for item in after.selected]

    assert report.rebuilt_messages >= 4
    assert before_ids == after_ids
    assert any("coffee" in item.memory.content.lower() for item in after.selected)
    assert all(item.memory.status.value == "active" for item in after.selected)


def test_eval_runner_emits_transcript_first_modes(tmp_path):
    config = SmartMemoryV3Config(storage=StorageConfig(sqlite_path=str(tmp_path / "eval.sqlite"), json_root=str(tmp_path / "json")))
    system = CognitiveMemorySystem(config=config)
    reports = system.run_eval_case("preference_change")

    modes = {report.mode for report in reports}
    assert modes == {"live_ingest", "full_replay", "partial_replay", "evidence_backed"}
    assert all(report.metrics.token_budget_compliant for report in reports if report.mode != "evidence_backed")
    assert any(report.passed for report in reports)
