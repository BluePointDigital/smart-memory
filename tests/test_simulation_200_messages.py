from __future__ import annotations

from cognition import BackgroundCognitionRunner
from embeddings import HashingTextEmbedder
from ingestion import IngestionPipeline
from hot_memory import HotMemoryManager
from hot_memory.store import HotMemoryStore
from retrieval import RetrievalPipeline
from storage import JSONMemoryStore, VectorIndexStore


def test_simulate_200_messages_stability(tmp_path):
    json_store = JSONMemoryStore(root=tmp_path / "store")
    vector_store = VectorIndexStore(sqlite_path=tmp_path / "store" / "vectors.sqlite")
    embedder = HashingTextEmbedder()

    ingestion = IngestionPipeline(
        json_store=json_store,
        vector_store=vector_store,
        embedder=embedder,
    )
    retrieval = RetrievalPipeline(
        json_store=json_store,
        vector_store=vector_store,
        embedder=embedder,
    )

    hot_store = HotMemoryStore(path=tmp_path / "hot" / "hot_memory.json")
    hot_manager = HotMemoryManager(store=hot_store)
    runner = BackgroundCognitionRunner(
        json_store=json_store,
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
            }
        )
        if result.stored:
            stored_count += 1

        if i % 20 == 0:
            retrieved = retrieval.retrieve(f"How is {project} going?")
            for ranked in retrieved.selected:
                hot_manager.register_retrieval_hit(ranked.memory)

        if i % 50 == 0 and i > 0:
            runner.run_once()

    final_retrieval = retrieval.retrieve("What happened in proj_stream_2 last week?")
    final_hot = hot_manager.get()

    # Ingestion rate and index growth sanity.
    assert stored_count > 40
    assert len(vector_store.list_memory_ids()) > 20

    # Prompt-stability constraints.
    assert len(final_hot.active_projects) <= 10
    assert len(final_hot.top_of_mind) <= 20
    assert len(final_hot.insight_queue) <= 10

    # Retrieval still functional after workload.
    assert final_retrieval.degraded is False
    assert len(final_retrieval.selected) >= 1
