from __future__ import annotations

from cognition import BackgroundCognitionRunner, CognitionScheduleState
from embeddings import HashingTextEmbedder
from ingestion import IngestionPipeline
from hot_memory import HotMemoryManager
from hot_memory.store import HotMemoryStore
from storage import SQLiteMemoryStore, VectorIndexStore


def test_background_scheduler_respects_cadence(tmp_path):
    sqlite_path = tmp_path / "store" / "memory.sqlite"
    store = SQLiteMemoryStore(sqlite_path=sqlite_path)
    vector_store = VectorIndexStore(sqlite_path=sqlite_path)
    embedder = HashingTextEmbedder()

    ingestion = IngestionPipeline(
        memory_store=store,
        vector_store=vector_store,
        embedder=embedder,
    )

    ingestion.ingest_dict(
        {
            "user_message": "We decided to start proj_alpha and track goals.",
            "assistant_message": "Captured planning memory.",
            "active_projects": ["proj_alpha"],
        }
    )

    hot_store = HotMemoryStore(path=tmp_path / "hot" / "hot_memory.json")
    hot_manager = HotMemoryManager(store=hot_store)

    runner = BackgroundCognitionRunner(
        memory_store=store,
        vector_store=vector_store,
        hot_memory_manager=hot_manager,
        embedder=embedder,
    )

    schedule_state = CognitionScheduleState(path=tmp_path / "cognition" / "schedule.json")

    first = runner.run_scheduled(schedule_state=schedule_state)
    second = runner.run_scheduled(schedule_state=schedule_state)

    assert len(first.executed_tasks) >= 1
    assert len(second.executed_tasks) == 0
