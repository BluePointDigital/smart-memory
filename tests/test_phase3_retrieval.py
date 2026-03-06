from __future__ import annotations

from embeddings import HashingTextEmbedder
from ingestion import IngestionPipeline
from retrieval import RetrievalPipeline
from storage import SQLiteMemoryStore, VectorIndexStore


def test_retrieval_prioritizes_relevant_entity_memories(tmp_path):
    sqlite_path = tmp_path / "store" / "memory.sqlite"
    store = SQLiteMemoryStore(sqlite_path=sqlite_path)
    vector_store = VectorIndexStore(sqlite_path=sqlite_path)
    embedder = HashingTextEmbedder()

    ingestion = IngestionPipeline(
        memory_store=store,
        vector_store=vector_store,
        embedder=embedder,
    )

    first = ingestion.ingest_dict(
        {
            "user_message": "Database migration project is active and we are tracking schema changes.",
            "assistant_message": "Captured as active project status.",
            "active_projects": ["proj_database_migration"],
            "source_session_id": "sess_db",
        }
    )
    ingestion.ingest_dict(
        {
            "user_message": "Marketing campaign draft was reviewed.",
            "assistant_message": "Captured campaign update.",
            "active_projects": ["proj_marketing_campaign"],
            "source_session_id": "sess_mkt",
        }
    )

    retrieval = RetrievalPipeline(
        memory_store=store,
        vector_store=vector_store,
        embedder=embedder,
    )

    result = retrieval.retrieve("How is the database migration going?")

    assert result.degraded is False
    assert len(result.selected) >= 1
    assert "database" in result.selected[0].memory.content.lower()

    assert first.memory_id is not None
    touched = store.get_memory(first.memory_id)
    assert touched is not None
    assert touched.access_count >= 1
