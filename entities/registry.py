"""Entity registry models and persistence."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class EntityAlias(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)


class EntityRegistry:
    """Persistent registry preventing entity-name fragmentation."""

    def __init__(self, path: str | Path = "data/entities/registry.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():
            self._write_default_registry()

    def _write_default_registry(self) -> None:
        defaults = [
            EntityAlias(
                entity_id="proj_smart_memory",
                canonical_name="Smart Memory",
                aliases=["smart-memory", "smart memory", "smartmemory", "smart memory v2"],
            )
        ]
        payload = [item.model_dump(mode="json") for item in defaults]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self) -> list[EntityAlias]:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return [EntityAlias.model_validate(item) for item in payload]

    def save(self, entries: list[EntityAlias]) -> None:
        payload = [entry.model_dump(mode="json") for entry in entries]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def register(self, entry: EntityAlias) -> None:
        entries = self.load()
        filtered = [item for item in entries if item.entity_id != entry.entity_id]
        filtered.append(entry)
        filtered.sort(key=lambda item: item.entity_id)
        self.save(filtered)

    def list_entity_ids(self) -> list[str]:
        return [entry.entity_id for entry in self.load()]
