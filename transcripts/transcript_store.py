"""SQLite-backed transcript storage for Smart Memory v3.1."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .transcript_models import MemoryEvidenceRecord, TranscriptMessage, TranscriptMessageInput, TranscriptSession


class TranscriptStore:
    def __init__(self, sqlite_path: str | Path = "data/memory_store/v3_memory.sqlite") -> None:
        self.sqlite_path = Path(sqlite_path)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    label TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS transcript_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    seq_num INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    tool_name TEXT,
                    parent_message_id TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS memory_evidence (
                    memory_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    span_start INTEGER,
                    span_end INTEGER,
                    evidence_kind TEXT NOT NULL,
                    confidence REAL,
                    PRIMARY KEY(memory_id, message_id, evidence_kind)
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_transcript_session_seq
                ON transcript_messages(session_id, seq_num);

                CREATE INDEX IF NOT EXISTS idx_transcript_session_created
                ON transcript_messages(session_id, created_at, seq_num);

                CREATE INDEX IF NOT EXISTS idx_memory_evidence_message
                ON memory_evidence(message_id);
                """
            )

    def _row_to_session(self, row: sqlite3.Row | None) -> TranscriptSession | None:
        if row is None:
            return None
        return TranscriptSession(
            session_id=str(row["session_id"]),
            started_at=str(row["started_at"]),
            ended_at=str(row["ended_at"]) if row["ended_at"] is not None else None,
            label=str(row["label"] or ""),
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def _row_to_message(self, row: sqlite3.Row | None) -> TranscriptMessage | None:
        if row is None:
            return None
        return TranscriptMessage(
            message_id=str(row["message_id"]),
            session_id=str(row["session_id"]),
            seq_num=int(row["seq_num"]),
            role=str(row["role"]),
            source_type=str(row["source_type"]),
            content=str(row["content"]),
            created_at=str(row["created_at"]),
            tool_name=str(row["tool_name"]) if row["tool_name"] is not None else None,
            parent_message_id=str(row["parent_message_id"]) if row["parent_message_id"] is not None else None,
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def create_session(
        self,
        *,
        session_id: str | None = None,
        label: str = "",
        metadata: dict | None = None,
        started_at: datetime | None = None,
    ) -> TranscriptSession:
        now = (started_at or datetime.now(timezone.utc)).isoformat()
        resolved_id = session_id or f"sess_{uuid4().hex}"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(session_id, started_at, ended_at, label, metadata_json)
                VALUES(?, ?, NULL, ?, ?)
                ON CONFLICT(session_id) DO NOTHING
                """,
                (resolved_id, now, label, json.dumps(metadata or {})),
            )
            row = connection.execute(
                "SELECT session_id, started_at, ended_at, label, metadata_json FROM sessions WHERE session_id = ?",
                (resolved_id,),
            ).fetchone()
        session = self._row_to_session(row)
        assert session is not None
        return session

    def ensure_session(
        self,
        *,
        session_id: str | None = None,
        label: str = "",
        metadata: dict | None = None,
        started_at: datetime | None = None,
    ) -> TranscriptSession:
        return self.create_session(session_id=session_id, label=label, metadata=metadata, started_at=started_at)

    def get_session(self, session_id: str) -> TranscriptSession | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT session_id, started_at, ended_at, label, metadata_json FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return self._row_to_session(row)

    def append_message(self, payload: TranscriptMessageInput) -> TranscriptMessage:
        session = self.ensure_session(
            session_id=payload.session_id,
            label=payload.label,
            metadata=payload.metadata,
            started_at=payload.created_at,
        )
        message_id = f"msg_{uuid4().hex}"
        created_at = (payload.created_at or datetime.now(timezone.utc)).isoformat()

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT COALESCE(MAX(seq_num), 0) AS max_seq FROM transcript_messages WHERE session_id = ?",
                (session.session_id,),
            ).fetchone()
            next_seq = int(row["max_seq"] or 0) + 1
            connection.execute(
                """
                INSERT INTO transcript_messages(
                    message_id, session_id, seq_num, role, source_type, content,
                    created_at, tool_name, parent_message_id, metadata_json
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    session.session_id,
                    next_seq,
                    payload.role,
                    payload.source_type,
                    payload.content,
                    created_at,
                    payload.tool_name,
                    payload.parent_message_id,
                    json.dumps(payload.metadata or {}),
                ),
            )
            connection.commit()
            stored = connection.execute(
                """
                SELECT message_id, session_id, seq_num, role, source_type, content,
                       created_at, tool_name, parent_message_id, metadata_json
                FROM transcript_messages
                WHERE message_id = ?
                """,
                (message_id,),
            ).fetchone()
        message = self._row_to_message(stored)
        assert message is not None
        return message

    def get_message(self, message_id: str) -> TranscriptMessage | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT message_id, session_id, seq_num, role, source_type, content,
                       created_at, tool_name, parent_message_id, metadata_json
                FROM transcript_messages
                WHERE message_id = ?
                """,
                (message_id,),
            ).fetchone()
        return self._row_to_message(row)

    def get_transcript(self, session_id: str, start: int | None = None, end: int | None = None) -> list[TranscriptMessage]:
        clauses = ["session_id = ?"]
        params: list[object] = [session_id]
        if start is not None:
            clauses.append("seq_num >= ?")
            params.append(int(start))
        if end is not None:
            clauses.append("seq_num <= ?")
            params.append(int(end))
        sql = """
            SELECT message_id, session_id, seq_num, role, source_type, content,
                   created_at, tool_name, parent_message_id, metadata_json
            FROM transcript_messages
            WHERE {where}
            ORDER BY seq_num ASC, message_id ASC
        """.format(where=" AND ".join(clauses))
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_message(row) for row in rows if self._row_to_message(row) is not None]

    def list_messages(self) -> list[TranscriptMessage]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT message_id, session_id, seq_num, role, source_type, content,
                       created_at, tool_name, parent_message_id, metadata_json
                FROM transcript_messages
                ORDER BY created_at ASC, session_id ASC, seq_num ASC, message_id ASC
                """
            ).fetchall()
        return [self._row_to_message(row) for row in rows if self._row_to_message(row) is not None]

    def get_messages_from(self, message_id: str) -> list[TranscriptMessage]:
        messages = self.list_messages()
        start_index = 0
        for index, message in enumerate(messages):
            if message.message_id == message_id:
                start_index = index
                break
        return messages[start_index:]

    def earliest_message_id_for_session(self, session_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT message_id FROM transcript_messages WHERE session_id = ? ORDER BY seq_num ASC, message_id ASC LIMIT 1",
                (session_id,),
            ).fetchone()
        return str(row["message_id"]) if row is not None else None

    def get_adjacent_context(self, message: TranscriptMessage, *, window: int = 1) -> str:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT content
                FROM transcript_messages
                WHERE session_id = ? AND seq_num BETWEEN ? AND ? AND message_id != ?
                ORDER BY seq_num ASC, message_id ASC
                """,
                (message.session_id, max(1, message.seq_num - window), message.seq_num + window, message.message_id),
            ).fetchall()
        return " ".join(str(row["content"]).strip() for row in rows if str(row["content"]).strip())

    def link_memory_evidence(
        self,
        *,
        memory_id: str,
        message_id: str,
        span_start: int | None = None,
        span_end: int | None = None,
        evidence_kind: str = "direct",
        confidence: float | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO memory_evidence(
                    memory_id, message_id, span_start, span_end, evidence_kind, confidence
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                (memory_id, message_id, span_start, span_end, evidence_kind, confidence),
            )

    def link_memory_evidence_batch(
        self,
        *,
        memory_id: str,
        message_ids: list[str],
        evidence_kind: str = "direct",
        confidence: float | None = None,
    ) -> None:
        for message_id in message_ids:
            self.link_memory_evidence(
                memory_id=memory_id,
                message_id=message_id,
                evidence_kind=evidence_kind,
                confidence=confidence,
            )

    def unlink_memory_evidence(self, memory_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM memory_evidence WHERE memory_id = ?", (memory_id,))

    def get_memory_evidence(self, memory_id: str) -> list[MemoryEvidenceRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT me.memory_id, me.message_id, me.span_start, me.span_end,
                       me.evidence_kind, me.confidence,
                       tm.session_id, tm.seq_num, tm.role, tm.source_type, tm.content,
                       tm.created_at, tm.tool_name, tm.parent_message_id, tm.metadata_json
                FROM memory_evidence me
                JOIN transcript_messages tm ON tm.message_id = me.message_id
                WHERE me.memory_id = ?
                ORDER BY tm.created_at ASC, tm.session_id ASC, tm.seq_num ASC, tm.message_id ASC
                """,
                (memory_id,),
            ).fetchall()
        records: list[MemoryEvidenceRecord] = []
        for row in rows:
            message = TranscriptMessage(
                message_id=str(row["message_id"]),
                session_id=str(row["session_id"]),
                seq_num=int(row["seq_num"]),
                role=str(row["role"]),
                source_type=str(row["source_type"]),
                content=str(row["content"]),
                created_at=str(row["created_at"]),
                tool_name=str(row["tool_name"]) if row["tool_name"] is not None else None,
                parent_message_id=str(row["parent_message_id"]) if row["parent_message_id"] is not None else None,
                metadata=json.loads(row["metadata_json"] or "{}"),
            )
            records.append(
                MemoryEvidenceRecord(
                    memory_id=str(row["memory_id"]),
                    message_id=str(row["message_id"]),
                    span_start=int(row["span_start"]) if row["span_start"] is not None else None,
                    span_end=int(row["span_end"]) if row["span_end"] is not None else None,
                    evidence_kind=str(row["evidence_kind"]),
                    confidence=float(row["confidence"]) if row["confidence"] is not None else None,
                    message=message,
                )
            )
        return records

    def evidence_snapshot(self, memory_id: str) -> tuple[list[str], int, str, str | None]:
        evidence = self.get_memory_evidence(memory_id)
        message_ids = [item.message_id for item in evidence]
        count = len(message_ids)
        if not evidence:
            return ([], 0, "", None)
        snippets = [item.message.content.strip() for item in evidence if item.message is not None]
        summary = " | ".join(snippets[:2])[:240]
        session_id = evidence[0].message.session_id if evidence[0].message is not None else None
        return (message_ids, count, summary, session_id)

    def affected_memory_ids_from_message(self, message_id: str) -> list[str]:
        message_ids = [message.message_id for message in self.get_messages_from(message_id)]
        if not message_ids:
            return []
        placeholders = ",".join("?" for _ in message_ids)
        sql = f"SELECT DISTINCT memory_id FROM memory_evidence WHERE message_id IN ({placeholders})"
        with self._connect() as connection:
            rows = connection.execute(sql, message_ids).fetchall()
        return [str(row["memory_id"]) for row in rows]
