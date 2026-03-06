"""Migration helpers from legacy JSON stores into the v3 SQLite backend."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from entities import EntityAliasResolver
from ingestion.memory_builder import build_memory_object
from prompt_engine.schemas import BaseMemory, MemoryType, validate_long_term_memory
from storage import JSONMemoryStore, SQLiteMemoryStore


@dataclass(frozen=True)
class MigrationReport:
    total_migrated: int
    total_rejected: int
    total_missing_fields_repaired: int
    total_entity_refs_extracted: int


class V3Migration:
    def __init__(
        self,
        *,
        legacy_root: str | Path = "data/memory_store",
        sqlite_path: str | Path = "data/memory_store/v3_memory.sqlite",
    ) -> None:
        self.legacy_store = JSONMemoryStore(legacy_root)
        self.sqlite_store = SQLiteMemoryStore(sqlite_path)
        self.entity_resolver = EntityAliasResolver()

    def migrate(self) -> MigrationReport:
        migrated = 0
        rejected = 0
        repaired = 0
        entity_refs = 0

        for legacy_memory in self.legacy_store.list_memories():
            try:
                memory = self._upgrade_memory(legacy_memory)
                self.sqlite_store.save_memory(memory)
                migrated += 1
                repaired += 1
                entity_refs += len(memory.entities)
            except Exception:
                rejected += 1
        return MigrationReport(migrated, rejected, repaired, entity_refs)

    def _upgrade_memory(self, memory: BaseMemory) -> BaseMemory:
        payload = memory.model_dump(mode="json")
        payload.setdefault("status", "active")
        payload.setdefault("lane_eligibility", self._infer_lane_eligibility(memory.memory_type))
        payload.setdefault("explanation", "migrated_from_v2")
        payload.setdefault("source_session_id", "legacy_unknown")
        payload.setdefault("source_message_ids", [])
        payload["entities"] = self.entity_resolver.canonicalize_many(payload.get("entities", []))
        return validate_long_term_memory(payload)

    def _infer_lane_eligibility(self, memory_type: MemoryType) -> list[str]:
        if memory_type in {MemoryType.IDENTITY, MemoryType.PREFERENCE}:
            return ["core", "retrieved"]
        if memory_type in {MemoryType.GOAL, MemoryType.TASK_STATE}:
            return ["working", "retrieved"]
        return ["retrieved"]
