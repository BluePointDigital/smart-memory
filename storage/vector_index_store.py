"""SQLite vector index that stores memory id, embedding, and compact metadata payload."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np


@dataclass(frozen=True)
class VectorSearchResult:
    memory_id: str
    score: float


class VectorIndexStore:
    """Vector storage with cosine search using numpy."""

    def __init__(self, sqlite_path: str | Path = "data/memory_store/vector_index.sqlite") -> None:
        self.sqlite_path = Path(sqlite_path)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_column(self, connection: sqlite3.Connection, name: str, ddl: str) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(vectors)").fetchall()
        }
        if name not in columns:
            connection.execute(f"ALTER TABLE vectors ADD COLUMN {ddl}")

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS vectors (
                    memory_id TEXT PRIMARY KEY,
                    vector_json TEXT NOT NULL,
                    dimension INTEGER NOT NULL,
                    model_name TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(
                connection,
                "payload_json",
                "payload_json TEXT NOT NULL DEFAULT '{}'",
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_vectors_model
                ON vectors(model_name)
                """
            )

    def upsert_vector(
        self,
        *,
        memory_id: str,
        vector: list[float] | np.ndarray,
        model_name: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        arr = np.asarray(vector, dtype=np.float32)
        vector_payload = json.dumps(arr.tolist())
        metadata_payload = json.dumps(payload or {})
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO vectors(
                    memory_id,
                    vector_json,
                    dimension,
                    model_name,
                    payload_json,
                    created_at,
                    updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    vector_json = excluded.vector_json,
                    dimension = excluded.dimension,
                    model_name = excluded.model_name,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    memory_id,
                    vector_payload,
                    int(arr.shape[0]),
                    model_name,
                    metadata_payload,
                    now,
                    now,
                ),
            )

    def delete_vector(self, memory_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM vectors WHERE memory_id = ?", (memory_id,))

    def get_vector(self, memory_id: str) -> np.ndarray | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT vector_json FROM vectors WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()

        if row is None:
            return None

        return np.asarray(json.loads(row["vector_json"]), dtype=np.float32)

    def get_payload(self, memory_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM vectors WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()

        if row is None:
            return None

        return json.loads(row["payload_json"])

    def list_memory_ids(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute("SELECT memory_id FROM vectors").fetchall()
        return [row["memory_id"] for row in rows]

    def search(
        self,
        *,
        query_vector: list[float] | np.ndarray,
        top_k: int = 30,
        memory_ids: Iterable[str] | None = None,
    ) -> list[VectorSearchResult]:
        query = np.asarray(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query)
        if query_norm == 0.0:
            return []

        id_set = set(memory_ids) if memory_ids is not None else None
        candidates: list[VectorSearchResult] = []

        with self._connect() as connection:
            rows = connection.execute("SELECT memory_id, vector_json FROM vectors").fetchall()

        for row in rows:
            memory_id = row["memory_id"]
            if id_set is not None and memory_id not in id_set:
                continue

            vector = np.asarray(json.loads(row["vector_json"]), dtype=np.float32)
            if vector.shape[0] != query.shape[0]:
                continue

            denom = np.linalg.norm(vector) * query_norm
            if denom == 0.0:
                continue

            score = float(np.dot(query, vector) / denom)
            candidates.append(VectorSearchResult(memory_id=memory_id, score=score))

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[:top_k]
