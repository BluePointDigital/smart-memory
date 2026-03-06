from __future__ import annotations

from cognition import BackgroundCognitionRunner
from embeddings import HashingTextEmbedder
from ingestion import IngestionPipeline
from hot_memory import HotMemoryManager
from hot_memory.store import HotMemoryStore
from retrieval import RetrievalPipeline
from storage import SQLiteMemoryStore, VectorIndexStore


def test_simulate_200_messages_stability(tmp_path):
    sqlite_path = tmp_path / "store" / "memory.sqlite"
    store = SQLiteMemoryStore(sqlite_path=sqlite_path)
    vector_store = VectorIndexStore(sqlite_path=sqlite_path)
    embedder = HashingTextEmbedder()

    ingestion = IngestionPipeline(
        memory_store=store,
        vector_store=vector_store,
        embedder=embedder,
    )
    retrieval = RetrievalPipeline(
        memory_store=store,
        vector_store=vector_store,
        embedder=embedder,
    )

    hot_store = HotMemoryStore(path=tmp_path / "hot" / "hot_memory.json")
    hot_manager = HotMemoryManager(store=hot_store)
    runner = BackgroundCognitionRunner(
        memory_store=store,
        vector_store=vector_store,
        hot_memory_manager=hot_manager,
        embedder=embedder,
    )

    stored_count = 0
    for i in range(200):
        project = f"proj_stream_{i % 6}"
        message = (
            f"Iteration {i}: We decided to update {project} roadmap, track milestones, "
            f"and review architecture choices next week."
        )
        result = ingestion.ingest_dict(
            {
                "user_message": message,
                "assistant_message": "Captured planning update.",
                "active_projects": [project],
                "source_session_id": f"sess_{i % 6}",
            }
        )
        if result.stored:
            stored_count += 1

        if i % 50 == 0 and i > 0:
            runner.run_once()

    final_retrieval = retrieval.retrieve("What happened in proj_stream_2 last week?")
    transcript_messages = ingestion.transcript_store.list_messages()

    assert stored_count > 40
    assert len(vector_store.list_memory_ids()) > 20
    assert len(transcript_messages) == 400
    assert final_retrieval.degraded is False
    assert len(final_retrieval.selected) >= 1
