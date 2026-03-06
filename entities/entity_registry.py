"""SQLite-backed entity registry for Smart Memory v3.1."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .entity_normalizer import EntityNormalizer


@dataclass(frozen=True)
class EntityRecord:
    entity_id: str
    canonical_name: str
    entity_type: str | None = None


class EntityRegistry:
    def __init__(self, sqlite_path: str | Path = "data/memory_store/v3_memory.sqlite") -> None:
        self.sqlite_path = Path(sqlite_path)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.normalizer = EntityNormalizer()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
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
                """
            )

    def resolve(self, value: str) -> str:
        alias = self.normalizer.normalize_surface(value)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT entity_id FROM entity_aliases WHERE alias = ?",
                (alias,),
            ).fetchone()
            if row is not None:
                entity_id = str(row["entity_id"])
                return entity_id

        entity_type = self.normalizer.infer_type(value)
        entity_id = self.normalizer.stable_id(value, entity_type=entity_type)
        self.register(EntityRecord(entity_id=entity_id, canonical_name=value.strip(), entity_type=entity_type))
        self.add_alias(entity_id, value)
        return entity_id

    def register(self, entry: EntityRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO entity_registry(entity_id, canonical_name, entity_type, last_seen_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(entity_id) DO UPDATE SET
                    canonical_name=excluded.canonical_name,
                    entity_type=excluded.entity_type,
                    last_seen_at=excluded.last_seen_at
                """,
                (
                    entry.entity_id,
                    entry.canonical_name,
                    entry.entity_type,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def add_alias(self, entity_id: str, alias: str) -> None:
        normalized = self.normalizer.normalize_surface(alias)
        if not normalized:
            return
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO entity_aliases(alias, entity_id) VALUES(?, ?)",
                (normalized, entity_id),
            )

    def canonicalize_many(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            entity_id = self.resolve(value)
            if entity_id and entity_id not in seen:
                deduped.append(entity_id)
                seen.add(entity_id)
        return deduped

    def list_entity_ids(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute("SELECT entity_id FROM entity_registry ORDER BY entity_id").fetchall()
        return [str(row["entity_id"]) for row in rows]


