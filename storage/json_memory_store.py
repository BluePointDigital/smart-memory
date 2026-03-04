"""Canonical JSON store for long-term memory objects."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import UUID

from pydantic import TypeAdapter

from prompt_engine.schemas import LongTermMemory, MemoryType


LONG_TERM_MEMORY_ADAPTER = TypeAdapter(LongTermMemory)


class JSONMemoryStore:
    """Persists one canonical memory object per JSON file."""

    def __init__(self, root: str | Path = "data/memory_store") -> None:
        self.root = Path(root)
        self.memories_dir = self.root / "memories"
        self.archive_dir = self.root / "archive"

        self.memories_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def _memory_path(self, memory_id: UUID | str) -> Path:
        return self.memories_dir / f"{memory_id}.json"

    def save_memory(self, memory: LongTermMemory) -> Path:
        path = self._memory_path(memory.id)
        payload = memory.model_dump(mode="json")
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def get_memory(self, memory_id: UUID | str) -> LongTermMemory | None:
        path = self._memory_path(memory_id)
        if not path.exists():
            return None

        payload = json.loads(path.read_text(encoding="utf-8"))
        return LONG_TERM_MEMORY_ADAPTER.validate_python(payload)

    def update_memory(self, memory: LongTermMemory) -> Path:
        return self.save_memory(memory)

    def list_memories(
        self,
        *,
        types: Iterable[MemoryType] | None = None,
        limit: int | None = None,
        created_after: datetime | None = None,
    ) -> list[LongTermMemory]:
        type_filter = {memory_type.value for memory_type in types} if types else None

        memories: list[LongTermMemory] = []
        for path in sorted(self.memories_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))

            if type_filter and payload.get("type") not in type_filter:
                continue

            memory = LONG_TERM_MEMORY_ADAPTER.validate_python(payload)
            if created_after is not None and memory.created_at <= created_after:
                continue

            memories.append(memory)
            if limit is not None and len(memories) >= limit:
                break

        return memories

    def archive_memory(self, memory_id: UUID | str, reason: str) -> Path | None:
        source_path = self._memory_path(memory_id)
        if not source_path.exists():
            return None

        payload = json.loads(source_path.read_text(encoding="utf-8"))
        archived_payload = {
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "memory": payload,
        }

        target_path = self.archive_dir / f"{memory_id}.json"
        target_path.write_text(json.dumps(archived_payload, indent=2), encoding="utf-8")
        source_path.unlink()

        return target_path
