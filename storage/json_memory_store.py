"""Legacy JSON import/export store for long-term memory objects."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import UUID

from prompt_engine.schemas import BaseMemory, LaneName, MemoryStatus, MemoryType, validate_long_term_memory


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

    def save_memory(self, memory: BaseMemory) -> Path:
        path = self._memory_path(memory.id)
        payload = memory.model_dump(mode="json")
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def get_memory(self, memory_id: UUID | str) -> BaseMemory | None:
        path = self._memory_path(memory_id)
        if not path.exists():
            return None

        payload = json.loads(path.read_text(encoding="utf-8"))
        return validate_long_term_memory(payload)

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
        del lane_name
        type_filter = {memory_type.value for memory_type in types} if types else None
        status_filter = {status.value for status in statuses} if statuses else None

        memories: list[BaseMemory] = []
        for path in sorted(self.memories_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            memory_type = payload.get("memory_type", payload.get("type"))
            if type_filter and memory_type not in type_filter:
                continue

            memory = validate_long_term_memory(payload)
            if status_filter and memory.status.value not in status_filter:
                continue
            if created_after is not None and memory.created_at <= created_after:
                continue
            if entity_id is not None and entity_id not in memory.entities:
                continue
            if source_session_id is not None and memory.source_session_id != source_session_id:
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

    def get_lane_contents(self, lane_name: LaneName, *, limit: int | None = None) -> list[BaseMemory]:
        eligible = []
        for memory in self.list_memories(limit=limit):
            if lane_name in memory.lane_eligibility:
                eligible.append(memory)
        return eligible[:limit] if limit is not None else eligible

    def promote_memory(self, memory_id: UUID | str, lane_name: LaneName, *, pinned: bool = False, priority: float = 0.0, reason: str = "") -> None:
        del lane_name, pinned, priority, reason
        memory = self.get_memory(memory_id)
        if memory is None:
            return
        self.save_memory(memory)

    def demote_memory(self, memory_id: UUID | str, lane_name: LaneName) -> None:
        del memory_id, lane_name

    def add_audit_event(self, event_type: str, **_: object) -> None:
        del event_type

    def export_bundle(self) -> dict[str, object]:
        return {
            "memories": [memory.model_dump(mode="json") for memory in self.list_memories()],
        }
