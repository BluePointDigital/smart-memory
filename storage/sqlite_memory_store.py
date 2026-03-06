"""Canonical SQLite-backed memory store for Smart Memory v3."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

from prompt_engine.schemas import (
    BaseMemory,
    LaneName,
    MemoryStatus,
    MemoryType,
    validate_long_term_memory,
)

from .backend import MemoryBackend


class SQLiteMemoryStore(MemoryBackend):
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
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    importance_score REAL NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_accessed_at TEXT NOT NULL,
                    valid_from TEXT,
                    valid_to TEXT,
                    source_session_id TEXT NOT NULL,
                    subject_entity_id TEXT,
                    attribute_family TEXT,
                    normalized_value TEXT,
                    state_label TEXT,
                    pinned_priority REAL NOT NULL DEFAULT 0.0
                );

                CREATE TABLE IF NOT EXISTS memory_entities (
                    memory_id TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    PRIMARY KEY(memory_id, entity_id)
                );

                CREATE TABLE IF NOT EXISTS lane_memberships (
                    memory_id TEXT NOT NULL,
                    lane_name TEXT NOT NULL,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    priority REAL NOT NULL DEFAULT 0.0,
                    reason TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(memory_id, lane_name)
                );

                CREATE TABLE IF NOT EXISTS entity_registry (
                    entity_id TEXT PRIMARY KEY,
                    canonical_name TEXT NOT NULL,
                    entity_type TEXT,
                    last_seen_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS entity_aliases (
                    alias TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS relationship_hints (
                    left_entity_id TEXT NOT NULL,
                    right_entity_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL DEFAULT 'related_to',
                    cooccurrence_count INTEGER NOT NULL DEFAULT 0,
                    last_seen_at TEXT NOT NULL,
                    memory_ids_json TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY(left_entity_id, right_entity_id, relation_type)
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    memory_ids_json TEXT NOT NULL DEFAULT '[]',
                    action TEXT,
                    reason TEXT NOT NULL DEFAULT '',
                    scores_json TEXT NOT NULL DEFAULT '{}',
                    source_session_id TEXT,
                    source_message_ids_json TEXT NOT NULL DEFAULT '[]',
                    payload_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS schema_migrations (
                    name TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status);
                CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
                CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(source_session_id);
                CREATE INDEX IF NOT EXISTS idx_memories_subject ON memories(subject_entity_id);
                CREATE INDEX IF NOT EXISTS idx_lane_memberships_lane ON lane_memberships(lane_name);
                CREATE INDEX IF NOT EXISTS idx_memory_entities_entity ON memory_entities(entity_id);
                """
            )

    def _row_to_memory(self, row: sqlite3.Row | None) -> BaseMemory | None:
        if row is None:
            return None
        return validate_long_term_memory(json.loads(row["payload_json"]))

    def save_memory(self, memory: BaseMemory) -> Path:
        payload = memory.model_dump(mode="json")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories(
                    id, payload_json, memory_type, status, importance_score, confidence,
                    created_at, updated_at, last_accessed_at, valid_from, valid_to,
                    source_session_id, subject_entity_id, attribute_family,
                    normalized_value, state_label, pinned_priority
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    memory_type=excluded.memory_type,
                    status=excluded.status,
                    importance_score=excluded.importance_score,
                    confidence=excluded.confidence,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    last_accessed_at=excluded.last_accessed_at,
                    valid_from=excluded.valid_from,
                    valid_to=excluded.valid_to,
                    source_session_id=excluded.source_session_id,
                    subject_entity_id=excluded.subject_entity_id,
                    attribute_family=excluded.attribute_family,
                    normalized_value=excluded.normalized_value,
                    state_label=excluded.state_label,
                    pinned_priority=excluded.pinned_priority
                """,
                (
                    str(memory.id),
                    json.dumps(payload),
                    memory.memory_type.value,
                    memory.status.value,
                    memory.importance_score,
                    memory.confidence,
                    memory.created_at.isoformat(),
                    (memory.updated_at or memory.created_at).isoformat(),
                    (memory.last_accessed_at or memory.created_at).isoformat(),
                    memory.valid_from.isoformat() if memory.valid_from else None,
                    memory.valid_to.isoformat() if memory.valid_to else None,
                    memory.source_session_id,
                    memory.subject_entity_id,
                    memory.attribute_family,
                    memory.normalized_value,
                    memory.state_label,
                    memory.pinned_priority,
                ),
            )
            connection.execute("DELETE FROM memory_entities WHERE memory_id = ?", (str(memory.id),))
            for entity_id in memory.entities:
                connection.execute(
                    "INSERT OR IGNORE INTO memory_entities(memory_id, entity_id) VALUES(?, ?)",
                    (str(memory.id), entity_id),
                )
        return self.sqlite_path

    def get_memory(self, memory_id: UUID | str) -> BaseMemory | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM memories WHERE id = ?",
                (str(memory_id),),
            ).fetchone()
        return self._row_to_memory(row)

    def update_memory(self, memory: BaseMemory) -> Path:
        return self.save_memory(memory)

    def list_memories(
        self,
        *,
        types: Iterable[MemoryType] | None = None,
        statuses: Iterable[MemoryStatus] | None = None,
        limit: int | None = None,
        created_after: datetime | None = None,
        entity_id: str | None = None,
        lane_name: LaneName | None = None,
        source_session_id: str | None = None,
    ) -> list[BaseMemory]:
        query = ["SELECT DISTINCT m.payload_json FROM memories m"]
        params: list[Any] = []
        joins: list[str] = []
        where: list[str] = []

        if entity_id:
            joins.append("JOIN memory_entities me ON me.memory_id = m.id")
            where.append("me.entity_id = ?")
            params.append(entity_id)

        if lane_name:
            joins.append("JOIN lane_memberships lm ON lm.memory_id = m.id")
            where.append("lm.lane_name = ?")
            params.append(lane_name.value if isinstance(lane_name, LaneName) else str(lane_name))

        if types:
            type_values = [memory_type.value for memory_type in types]
            where.append(f"m.memory_type IN ({','.join('?' for _ in type_values)})")
            params.extend(type_values)

        if statuses:
            status_values = [status.value for status in statuses]
            where.append(f"m.status IN ({','.join('?' for _ in status_values)})")
            params.extend(status_values)

        if created_after is not None:
            where.append("m.created_at > ?")
            params.append(created_after.isoformat())

        if source_session_id is not None:
            where.append("m.source_session_id = ?")
            params.append(source_session_id)

        query.extend(joins)
        if where:
            query.append("WHERE " + " AND ".join(where))
        query.append("ORDER BY m.updated_at DESC, m.created_at DESC")
        if limit is not None:
            query.append(f"LIMIT {int(limit)}")

        sql = " ".join(query)
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [validate_long_term_memory(json.loads(row["payload_json"])) for row in rows]

    def archive_memory(self, memory_id: UUID | str, reason: str) -> Path | None:
        memory = self.get_memory(memory_id)
        if memory is None:
            return None
        archived = memory.model_copy(
            update={
                "status": MemoryStatus.ARCHIVED,
                "updated_at": datetime.now(timezone.utc),
                "explanation": reason or memory.explanation,
            }
        )
        self.save_memory(archived)
        self.add_audit_event(
            "memory_archived",
            memory_ids=[str(memory.id)],
            action="ARCHIVE",
            reason=reason,
            source_session_id=memory.source_session_id,
            source_message_ids=memory.source_message_ids,
        )
        return self.sqlite_path

    def get_lane_contents(self, lane_name: LaneName, *, limit: int | None = None) -> list[BaseMemory]:
        return self.list_memories(lane_name=lane_name, limit=limit)

    def promote_memory(
        self,
        memory_id: UUID | str,
        lane_name: LaneName,
        *,
        pinned: bool = False,
        priority: float = 0.0,
        reason: str = "",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO lane_memberships(memory_id, lane_name, pinned, priority, reason, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id, lane_name) DO UPDATE SET
                    pinned=excluded.pinned,
                    priority=excluded.priority,
                    reason=excluded.reason,
                    updated_at=excluded.updated_at
                """,
                (str(memory_id), lane_name.value, 1 if pinned else 0, float(priority), reason, now),
            )

    def demote_memory(self, memory_id: UUID | str, lane_name: LaneName) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM lane_memberships WHERE memory_id = ? AND lane_name = ?",
                (str(memory_id), lane_name.value),
            )

    def add_audit_event(
        self,
        event_type: str,
        *,
        memory_ids: list[str] | None = None,
        action: str | None = None,
        reason: str = "",
        scores: dict[str, Any] | None = None,
        source_session_id: str | None = None,
        source_message_ids: list[str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_events(
                    timestamp, event_type, memory_ids_json, action, reason, scores_json,
                    source_session_id, source_message_ids_json, payload_json
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    event_type,
                    json.dumps(memory_ids or []),
                    action,
                    reason,
                    json.dumps(scores or {}),
                    source_session_id,
                    json.dumps(source_message_ids or []),
                    json.dumps(payload or {}),
                ),
            )

    def list_related_memories(
        self,
        *,
        entities: list[str],
        memory_type: MemoryType | None = None,
        include_statuses: Iterable[MemoryStatus] | None = None,
        limit: int = 10,
    ) -> list[BaseMemory]:
        statuses = list(include_statuses or [MemoryStatus.ACTIVE, MemoryStatus.UNCERTAIN])
        if not entities:
            return self.list_memories(
                types=[memory_type] if memory_type else None,
                statuses=statuses,
                limit=limit,
            )

        query = """
            SELECT DISTINCT m.payload_json
            FROM memories m
            JOIN memory_entities me ON me.memory_id = m.id
            WHERE me.entity_id IN ({entity_placeholders}) AND m.status IN ({status_placeholders})
        """
        params: list[Any] = list(entities)
        entity_placeholders = ",".join("?" for _ in entities)
        status_placeholders = ",".join("?" for _ in statuses)
        params.extend([status.value for status in statuses])
        if memory_type is not None:
            query += " AND m.memory_type = ?"
            params.append(memory_type.value)
        query += " ORDER BY m.updated_at DESC LIMIT ?"
        params.append(limit)

        sql = query.format(entity_placeholders=entity_placeholders, status_placeholders=status_placeholders)
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [validate_long_term_memory(json.loads(row["payload_json"])) for row in rows]

    def get_memory_history(self, memory_id: UUID | str) -> list[BaseMemory]:
        target = self.get_memory(memory_id)
        if target is None:
            return []
        ids = {str(target.id)}
        if target.revision_of is not None:
            ids.add(str(target.revision_of))
        ids.update(str(value) for value in target.supersedes)

        with self._connect() as connection:
            rows = connection.execute("SELECT payload_json FROM memories").fetchall()
        histories: list[BaseMemory] = []
        for row in rows:
            memory = validate_long_term_memory(json.loads(row["payload_json"]))
            related = str(memory.id) in ids or str(memory.revision_of) in ids or any(str(item) in ids for item in memory.supersedes)
            if related:
                histories.append(memory)
        histories.sort(key=lambda item: item.created_at)
        return histories

    def get_active_version(self, memory_id: UUID | str) -> BaseMemory | None:
        target = self.get_memory(memory_id)
        if target is None:
            return None
        if target.status == MemoryStatus.ACTIVE:
            return target
        history = self.get_memory_history(memory_id)
        for memory in reversed(history):
            if memory.status == MemoryStatus.ACTIVE:
                return memory
        return None

    def get_revision_chain(self, memory_id: UUID | str) -> list[BaseMemory]:
        return self.get_memory_history(memory_id)

    def export_to_json(self, output_path: str | Path) -> Path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        bundle = {
            "memories": [memory.model_dump(mode="json") for memory in self.list_memories()],
            "core_lane": [memory.model_dump(mode="json") for memory in self.get_lane_contents(LaneName.CORE)],
            "working_lane": [memory.model_dump(mode="json") for memory in self.get_lane_contents(LaneName.WORKING)],
        }
        output.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        return output
