"""Transcript-first models for Smart Memory v3.1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import Field, field_validator

from prompt_engine.schemas import StrictModel


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class TranscriptSession(StrictModel):
    session_id: str = Field(min_length=1)
    started_at: datetime
    ended_at: datetime | None = None
    label: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("started_at", "ended_at", mode="before")
    @classmethod
    def _normalize_datetime(cls, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise TypeError("Expected datetime or ISO datetime string")
        return _ensure_timezone(value)


class TranscriptMessage(StrictModel):
    message_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    seq_num: int = Field(ge=1)
    role: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    content: str = Field(min_length=1)
    created_at: datetime
    tool_name: str | None = None
    parent_message_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("created_at", mode="before")
    @classmethod
    def _normalize_datetime(cls, value: Any) -> datetime:
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise TypeError("Expected datetime or ISO datetime string")
        return _ensure_timezone(value)


class TranscriptMessageInput(StrictModel):
    session_id: str | None = None
    role: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    content: str = Field(min_length=1)
    created_at: datetime | None = None
    tool_name: str | None = None
    parent_message_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    label: str = ""

    @field_validator("created_at", mode="before")
    @classmethod
    def _normalize_datetime(cls, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise TypeError("Expected datetime or ISO datetime string")
        return _ensure_timezone(value)


class MemoryEvidenceRecord(StrictModel):
    memory_id: str = Field(min_length=1)
    message_id: str = Field(min_length=1)
    span_start: int | None = Field(default=None, ge=0)
    span_end: int | None = Field(default=None, ge=0)
    evidence_kind: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    message: TranscriptMessage | None = None


class RebuildReport(StrictModel):
    scope: str = Field(min_length=1)
    session_id: str | None = None
    rebuilt_messages: int = Field(ge=0)
    rebuilt_memories: int = Field(ge=0)
    cleared_memories: int = Field(ge=0)
    started_at: datetime
    finished_at: datetime
    duration_ms: int = Field(ge=0)

    @field_validator("started_at", "finished_at", mode="before")
    @classmethod
    def _normalize_datetime(cls, value: Any) -> datetime:
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise TypeError("Expected datetime or ISO datetime string")
        return _ensure_timezone(value)
