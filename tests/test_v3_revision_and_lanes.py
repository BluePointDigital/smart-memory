from __future__ import annotations

from embeddings import HashingTextEmbedder
from ingestion import IngestionPipeline
from ingestion.memory_builder import build_memory_object
from memory_lanes import CoreMemoryManager, WorkingMemoryManager
from prompt_engine.schemas import LaneName, MemoryType
from retrieval import RetrievalPipeline
from storage import SQLiteMemoryStore, VectorIndexStore
from transcripts import TranscriptMessageInput, TranscriptStore


def test_preference_change_supersedes_prior_memory(tmp_path):
    sqlite_path = tmp_path / "store" / "v3.sqlite"
    store = SQLiteMemoryStore(sqlite_path=sqlite_path)
    vector_store = VectorIndexStore(sqlite_path=sqlite_path)
    embedder = HashingTextEmbedder()

    pipeline = IngestionPipeline(
        memory_store=store,
        vector_store=vector_store,
        embedder=embedder,
    )

    first = pipeline.ingest_dict(
        {
            "user_message": "I prefer tea for morning work.",
            "assistant_message": "Preference captured.",
            "source_session_id": "session_a",
        }
    )
    second = pipeline.ingest_dict(
        {
            "user_message": "I prefer coffee now instead of tea.",
            "assistant_message": "Updated preference captured.",
            "source_session_id": "session_b",
        }
    )

    assert first.stored is True
    assert second.action == "SUPERSEDE"
    prior = store.get_memory(first.memory_id)
    current = store.get_memory(second.memory_id)
    assert prior is not None and prior.status.value == "superseded"
    assert current is not None and current.status.value == "active"
    assert "coffee" in current.content.lower()
    assert current.evidence_count >= 1

    retrieval = RetrievalPipeline(memory_store=store, vector_store=vector_store, embedder=embedder)
    result = retrieval.retrieve("What do I prefer now?")
    assert result.selected
    assert any("coffee" in item.memory.content.lower() for item in result.selected)
    assert all("tea for morning work" not in item.memory.content.lower() for item in result.selected)


def test_core_and_working_lane_managers_promote_expected_memories(tmp_path):
    sqlite_path = tmp_path / "store" / "v3.sqlite"
    store = SQLiteMemoryStore(sqlite_path=sqlite_path)
    transcript_store = TranscriptStore(sqlite_path=sqlite_path)

    identity_message = transcript_store.append_message(
        TranscriptMessageInput(
            session_id="session_identity",
            role="user",
            source_type="conversation",
            content="I am James, the maintainer of Smart Memory.",
        )
    )
    task_message = transcript_store.append_message(
        TranscriptMessageInput(
            session_id="session_task",
            role="user",
            source_type="conversation",
            content="Database migration is blocked on schema review.",
        )
    )

    identity_memory = build_memory_object(
        memory_type=MemoryType.IDENTITY,
        user_message="I am James, the maintainer of Smart Memory.",
        importance=0.95,
        source_session_id="session_identity",
        source_message_ids=[identity_message.message_id],
    )
    task_memory = build_memory_object(
        memory_type=MemoryType.TASK_STATE,
        user_message="Database migration is blocked on schema review.",
        importance=0.92,
        source_session_id="session_task",
        source_message_ids=[task_message.message_id],
    )

    store.save_memory(identity_memory)
    store.save_memory(task_memory)
    transcript_store.link_memory_evidence_batch(memory_id=str(identity_memory.id), message_ids=[identity_message.message_id])
    transcript_store.link_memory_evidence_batch(memory_id=str(task_memory.id), message_ids=[task_message.message_id])

    core = CoreMemoryManager(store)
    working = WorkingMemoryManager(store)
    assert core.evaluate_memory(identity_memory) is True
    assert working.evaluate_memory(task_memory) is True

    core_ids = {str(memory.id) for memory in store.get_lane_contents(LaneName.CORE)}
    working_ids = {str(memory.id) for memory in store.get_lane_contents(LaneName.WORKING)}
    assert str(identity_memory.id) in core_ids
    assert str(task_memory.id) in working_ids
