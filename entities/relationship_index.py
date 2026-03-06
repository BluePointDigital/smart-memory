"""Lightweight transcript-derived entity relationship hints backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


class RelationshipIndex:
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS relationship_hints (
                    left_entity_id TEXT NOT NULL,
                    right_entity_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL DEFAULT 'related_to',
                    cooccurrence_count INTEGER NOT NULL DEFAULT 0,
                    last_seen_at TEXT NOT NULL,
                    memory_ids_json TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY(left_entity_id, right_entity_id, relation_type)
                )
                """
            )

    def record_cooccurrence(
        self,
        entities: Iterable[str],
        *,
        memory_id: str,
        relation_type: str = "related_to",
    ) -> None:
        unique = sorted({entity for entity in entities if entity})
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            for index, left_entity in enumerate(unique):
                for right_entity in unique[index + 1 :]:
                    row = connection.execute(
                        """
                        SELECT cooccurrence_count, memory_ids_json
                        FROM relationship_hints
                        WHERE left_entity_id = ? AND right_entity_id = ? AND relation_type = ?
                        """,
                        (left_entity, right_entity, relation_type),
                    ).fetchone()
                    memory_ids = [] if row is None else json.loads(row["memory_ids_json"])
                    if memory_id not in memory_ids:
                        memory_ids.insert(0, memory_id)
                    connection.execute(
                        """
                        INSERT INTO relationship_hints(
                            left_entity_id, right_entity_id, relation_type,
                            cooccurrence_count, last_seen_at, memory_ids_json
                        ) VALUES(?, ?, ?, ?, ?, ?)
                        ON CONFLICT(left_entity_id, right_entity_id, relation_type) DO UPDATE SET
                            cooccurrence_count = relationship_hints.cooccurrence_count + 1,
                            last_seen_at = excluded.last_seen_at,
                            memory_ids_json = excluded.memory_ids_json
                        """,
                        (
                            left_entity,
                            right_entity,
                            relation_type,
                            1,
                            now,
                            json.dumps(memory_ids[:25]),
                        ),
                    )

    def related_entities(self, entity_ids: Iterable[str], *, limit: int = 10) -> list[str]:
        ids = [entity_id for entity_id in entity_ids if entity_id]
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        sql = f"""
            SELECT left_entity_id, right_entity_id, cooccurrence_count
            FROM relationship_hints
            WHERE left_entity_id IN ({placeholders}) OR right_entity_id IN ({placeholders})
            ORDER BY cooccurrence_count DESC, last_seen_at DESC
        """
        with self._connect() as connection:
            rows = connection.execute(sql, ids + ids).fetchall()
        related: list[str] = []
        seen = set(ids)
        for row in rows:
            candidates = [str(row["left_entity_id"]), str(row["right_entity_id"])]
            for candidate in candidates:
                if candidate not in seen:
                    related.append(candidate)
                    seen.add(candidate)
                    if len(related) >= limit:
                        return related
        return related

