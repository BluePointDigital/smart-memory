from __future__ import annotations

import numpy as np

from embeddings import HashingTextEmbedder
from ingestion import IngestionPipeline, IngestionPipelineConfig
from storage import SQLiteMemoryStore, VectorIndexStore


class StubSemanticEmbedder:
    model_name = "stub_semantic_embedder_v1"
    dimension = 8

    def embed(self, text: str) -> np.ndarray:
        vector = np.ones(self.dimension, dtype=np.float32)
        vector /= np.linalg.norm(vector)
        return vector


def test_ingestion_stores_transcript_backed_memory_above_threshold(tmp_path):
    sqlite_path = tmp_path / "store" / "memory.sqlite"
    store = SQLiteMemoryStore(sqlite_path=sqlite_path)
    vector_store = VectorIndexStore(sqlite_path=sqlite_path)
    pipeline = IngestionPipeline(
        memory_store=store,
        vector_store=vector_store,
        embedder=HashingTextEmbedder(),
        config=IngestionPipelineConfig(minimum_importance_to_store=0.45),
    )

    result = pipeline.ingest_dict(
        {
            "user_message": "We decided to start the database migration project next week and track milestones.",
            "assistant_message": "Noted: this is a project goal with concrete milestones.",
            "source": "conversation",
            "active_projects": ["proj_database_migration"],
        }
    )

    assert result.stored is True
    assert result.memory_id is not None
    assert result.session_id is not None
    assert len(result.transcript_message_ids) == 2

    memory = store.get_memory(result.memory_id)
    assert memory is not None
    assert memory.importance_score >= 0.45
    assert memory.schema_version == "3.1"
    assert memory.evidence_count >= 1
    assert memory.source_session_id == result.session_id

    evidence = pipeline.transcript_store.get_memory_evidence(result.memory_id)
    assert evidence
    assert {item.message_id for item in evidence}.issubset(set(result.transcript_message_ids))

    vector = vector_store.get_vector(result.memory_id)
    assert vector is not None
    assert len(vector) == 384

    payload = vector_store.get_payload(result.memory_id)
    assert payload is not None
    assert payload["memory_id"] == result.memory_id
    assert payload["schema_version"] == "3.1"
    assert payload["status"] == "active"
    assert payload["evidence_count"] >= 1
    assert "content" not in payload


def test_ingestion_semantic_dedup_reinforces_existing_memory_with_evidence(tmp_path):
    sqlite_path = tmp_path / "store" / "memory.sqlite"
    store = SQLiteMemoryStore(sqlite_path=sqlite_path)
    vector_store = VectorIndexStore(sqlite_path=sqlite_path)
    pipeline = IngestionPipeline(
        memory_store=store,
        vector_store=vector_store,
        embedder=StubSemanticEmbedder(),
        config=IngestionPipelineConfig(minimum_importance_to_store=0.45),
    )

    first = pipeline.ingest_dict(
        {
            "user_message": "I prefer local models for privacy-sensitive tasks.",
            "assistant_message": "Captured your preference.",
            "source": "conversation",
        }
    )
    second = pipeline.ingest_dict(
        {
            "user_message": "I prefer local models for private workflows.",
            "assistant_message": "Noted, still preferring local models.",
            "source": "conversation",
        }
    )

    assert first.stored is True
    assert first.memory_id is not None

    assert second.stored is False
    assert second.reason == "semantic_duplicate_reinforced"
    assert second.memory_id == first.memory_id
    assert second.action == "NOOP"

    reinforced = store.get_memory(first.memory_id)
    assert reinforced is not None
    assert reinforced.access_count >= 1
    assert reinforced.evidence_count >= 2

    evidence = pipeline.transcript_store.get_memory_evidence(first.memory_id)
    assert len(evidence) >= 2
