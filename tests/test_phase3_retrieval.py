from __future__ import annotations

from embeddings import HashingTextEmbedder
from ingestion import IngestionPipeline
from retrieval import RetrievalPipeline
from storage import JSONMemoryStore, VectorIndexStore


def test_retrieval_prioritizes_relevant_entity_memories(tmp_path):
    json_store = JSONMemoryStore(root=tmp_path / "store")
    vector_store = VectorIndexStore(sqlite_path=tmp_path / "store" / "vectors.sqlite")
    embedder = HashingTextEmbedder()

    ingestion = IngestionPipeline(
        json_store=json_store,
        vector_store=vector_store,
        embedder=embedder,
    )

    first = ingestion.ingest_dict(
        {
            "user_message": "Database migration project is active and we are tracking schema changes.",
            "assistant_message": "Captured as active project status.",
            "active_projects": ["proj_database_migration"],
        }
    )
    ingestion.ingest_dict(
        {
            "user_message": "Marketing campaign draft was reviewed.",
            "assistant_message": "Captured campaign update.",
            "active_projects": ["proj_marketing_campaign"],
        }
    )

    retrieval = RetrievalPipeline(
        json_store=json_store,
        vector_store=vector_store,
        embedder=embedder,
    )

    result = retrieval.retrieve("How is the database migration going?")

    assert result.degraded is False
    assert len(result.selected) >= 1
    assert "database" in result.selected[0].memory.content.lower()

    assert first.memory_id is not None
    touched = json_store.get_memory(first.memory_id)
    assert touched is not None
    assert touched.access_count >= 1
