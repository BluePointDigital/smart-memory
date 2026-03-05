from __future__ import annotations

import numpy as np

from embeddings import HashingTextEmbedder
from ingestion import IngestionPipeline, IngestionPipelineConfig
from storage import JSONMemoryStore, VectorIndexStore


class StubSemanticEmbedder:
    model_name = "stub_semantic_embedder_v1"
    dimension = 8

    def embed(self, text: str) -> np.ndarray:
        # Constant normalized vector to deterministically trigger high similarity.
        vector = np.ones(self.dimension, dtype=np.float32)
        vector /= np.linalg.norm(vector)
        return vector


def test_ingestion_stores_memory_above_threshold(tmp_path):
    json_store = JSONMemoryStore(root=tmp_path / "store")
    vector_store = VectorIndexStore(sqlite_path=tmp_path / "store" / "vectors.sqlite")
    pipeline = IngestionPipeline(
        json_store=json_store,
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

    memory = json_store.get_memory(result.memory_id)
    assert memory is not None
    assert memory.importance >= 0.45

    vector = vector_store.get_vector(result.memory_id)
    assert vector is not None
    assert len(vector) == 384

    # ID consistency: same memory id across JSON and vector payload metadata.
    payload = vector_store.get_payload(result.memory_id)
    assert payload is not None
    assert payload["memory_id"] == result.memory_id
    assert payload["schema_version"] == "2.0"
    assert "content" not in payload


def test_ingestion_semantic_dedup_reinforces_existing_memory(tmp_path):
    json_store = JSONMemoryStore(root=tmp_path / "store")
    vector_store = VectorIndexStore(sqlite_path=tmp_path / "store" / "vectors.sqlite")
    pipeline = IngestionPipeline(
        json_store=json_store,
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

    reinforced = json_store.get_memory(first.memory_id)
    assert reinforced is not None
    assert reinforced.access_count == 1
    if reinforced.type.value == "belief":
        assert reinforced.reinforced_count == 2
