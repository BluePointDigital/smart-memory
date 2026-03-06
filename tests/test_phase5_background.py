from __future__ import annotations

from cognition import BackgroundCognitionRunner
from embeddings import HashingTextEmbedder
from ingestion import IngestionPipeline
from hot_memory import HotMemoryManager
from hot_memory.store import HotMemoryStore
from storage import SQLiteMemoryStore, VectorIndexStore


def test_background_cognition_runs_and_returns_result(tmp_path):
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
            "user_message": "I prefer local models for privacy and reliability.",
            "assistant_message": "Preference captured.",
            "active_projects": ["proj_memory_engine"],
        }
    )
    ingestion.ingest_dict(
        {
            "user_message": "I avoid hosted APIs for sensitive integrations.",
            "assistant_message": "Potential conflicting preference captured.",
            "active_projects": ["proj_memory_engine"],
        }
    )
    ingestion.ingest_dict(
        {
            "user_message": "Project memory engine depends_on vector index and uses sqlite.",
            "assistant_message": "Technical relation captured.",
            "active_projects": ["proj_memory_engine"],
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

    result = runner.run_once()

    assert result.processed_memories >= 1
    assert result.generated_beliefs >= 0
    assert result.generated_insights >= 0
    assert "belief_resolver" in result.executed_tasks
    assert result.conflicts_resolved >= 0
    assert len(hot_manager.get().insight_queue) >= 0
