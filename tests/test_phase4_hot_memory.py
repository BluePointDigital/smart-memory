from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hot_memory import HotMemoryManager
from hot_memory.store import HotMemoryStore
from prompt_engine.schemas import EpisodicMemory, MemorySource


def test_hot_memory_cooling_removes_stale_items(tmp_path):
    store = HotMemoryStore(path=tmp_path / "hot" / "hot_memory.json")
    manager = HotMemoryManager(store=store)

    manager.start_project("proj_alpha")
    bundle = store.load_bundle()
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
    bundle.reinforcement["active_projects"]["proj_alpha"] = stale_time
    store.save_bundle(bundle)

    cooled = manager.cool(ttl_hours=36)
    assert "proj_alpha" not in cooled.active_projects


def test_hot_memory_caps_are_enforced(tmp_path):
    store = HotMemoryStore(path=tmp_path / "hot" / "hot_memory.json")
    manager = HotMemoryManager(store=store)

    for i in range(30):
        manager.start_project(f"proj_{i}")
        manager.add_working_question(f"question_{i}")

        memory = EpisodicMemory(
            content=f"high importance summary {i}",
            importance_score=0.9,
            entities=[f"proj_{i}"],
            relations=[],
            emotional_valence=0.0,
            emotional_intensity=0.0,
            source=MemorySource.CONVERSATION,
            source_session_id=f"sess_{i}",
            source_message_ids=[f"msg_{i}"],
            evidence_count=1,
            participants=["user", "assistant"],
        )
        manager.register_high_importance_memory(memory)

    hot = manager.get()
    assert len(hot.active_projects) <= 10
    assert len(hot.working_questions) <= 10
    assert len(hot.top_of_mind) <= 20
    assert len(hot.insight_queue) <= 10
