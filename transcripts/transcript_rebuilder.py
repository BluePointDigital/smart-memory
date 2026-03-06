"""Transcript replay and rebuild helpers for Smart Memory v3.1."""

from __future__ import annotations

from datetime import datetime, timezone

from hot_memory import HotMemoryManager
from memory_lanes import WorkingMemoryManager
from storage import SQLiteMemoryStore

from .transcript_models import RebuildReport
from .transcript_store import TranscriptStore


class TranscriptRebuilder:
    def __init__(
        self,
        *,
        memory_store: SQLiteMemoryStore,
        transcript_store: TranscriptStore,
        ingestion_pipeline,
        hot_memory_manager: HotMemoryManager | None = None,
        working_lane_manager: WorkingMemoryManager | None = None,
    ) -> None:
        self.memory_store = memory_store
        self.transcript_store = transcript_store
        self.ingestion_pipeline = ingestion_pipeline
        self.hot_memory_manager = hot_memory_manager
        self.working_lane_manager = working_lane_manager

    def _reset_hot_memory(self) -> None:
        if self.hot_memory_manager is None:
            return
        self.hot_memory_manager.store.reset()

    def _rebuild_hot_projection(self) -> None:
        if self.hot_memory_manager is None or self.working_lane_manager is None:
            return
        hot_memory = self.working_lane_manager.to_hot_memory(insights=[])
        self.hot_memory_manager.store.set_hot_memory(hot_memory)

    def _full_replay(self) -> tuple[int, int]:
        messages = self.transcript_store.list_messages()
        rebuilt_memories = 0
        for message in messages:
            result = self.ingestion_pipeline.ingest_transcript_message(message, replay_mode=True)
            rebuilt_memories += len(result.memory_ids)
        self._rebuild_hot_projection()
        return (len(messages), self.memory_store.count_memories())

    def rebuild_from_transcripts(self, session_id: str | None = None) -> RebuildReport:
        started_at = datetime.now(timezone.utc)
        cleared = self.memory_store.clear_derived_state(preserve_audit=True)
        self._reset_hot_memory()
        rebuilt_messages, rebuilt_memories = self._full_replay()
        finished_at = datetime.now(timezone.utc)
        self.memory_store.add_audit_event(
            "rebuild_completed",
            action="REBUILD",
            reason="replayed transcript-backed derived state",
            source_session_id=session_id,
            payload={
                "scope": "session" if session_id else "full",
                "implementation": "full_replay",
                "rebuilt_messages": rebuilt_messages,
                "rebuilt_memories": rebuilt_memories,
                "cleared_memories": cleared,
            },
        )
        return RebuildReport(
            scope="session" if session_id else "full",
            session_id=session_id,
            rebuilt_messages=rebuilt_messages,
            rebuilt_memories=rebuilt_memories,
            cleared_memories=cleared,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=max(0, int((finished_at - started_at).total_seconds() * 1000)),
        )

    def rebuild_memory_state(self, full: bool = True) -> RebuildReport:
        if not full:
            return self.rebuild_from_transcripts()
        return self.rebuild_from_transcripts()

    def rederive_memory_for_message(self, message_id: str) -> RebuildReport:
        message = self.transcript_store.get_message(message_id)
        session_id = message.session_id if message is not None else None
        report = self.rebuild_from_transcripts(session_id=session_id)
        self.memory_store.add_audit_event(
            "message_rederived",
            action="REBUILD",
            reason="replayed transcript-derived state from message request",
            source_session_id=session_id,
            source_message_ids=[message_id],
            payload={"requested_message_id": message_id, "implementation": "full_replay"},
        )
        return report
