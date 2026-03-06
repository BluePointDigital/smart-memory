"""Storage backend interfaces for the Smart Memory v3.1 runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

from prompt_engine.schemas import BaseMemory, LaneName, MemoryStatus, MemoryType


class MemoryBackend(ABC):
    @abstractmethod
    def save_memory(self, memory: BaseMemory) -> Path | None:
        raise NotImplementedError

    @abstractmethod
    def get_memory(self, memory_id: UUID | str) -> BaseMemory | None:
        raise NotImplementedError

    @abstractmethod
    def update_memory(self, memory: BaseMemory) -> Path | None:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def archive_memory(self, memory_id: UUID | str, reason: str) -> Path | None:
        raise NotImplementedError

    @abstractmethod
    def get_lane_contents(self, lane_name: LaneName, *, limit: int | None = None) -> list[BaseMemory]:
        raise NotImplementedError

    @abstractmethod
    def promote_memory(
        self,
        memory_id: UUID | str,
        lane_name: LaneName,
        *,
        pinned: bool = False,
        priority: float = 0.0,
        reason: str = "",
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def demote_memory(self, memory_id: UUID | str, lane_name: LaneName) -> None:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError
