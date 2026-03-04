"""Temporal query parsing and memory time filtering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

from prompt_engine.schemas import LongTermMemory


@dataclass(frozen=True)
class TimeRange:
    start: datetime
    end: datetime


DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def parse_time_range(query: str, now: datetime | None = None) -> TimeRange | None:
    now = now or datetime.now(timezone.utc)
    text = query.lower()

    if "yesterday" in text:
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return TimeRange(start=start, end=end)

    if "today" in text:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return TimeRange(start=start, end=end)

    if "last week" in text:
        end = now
        start = now - timedelta(days=7)
        return TimeRange(start=start, end=end)

    if "last month" in text:
        end = now
        start = now - timedelta(days=30)
        return TimeRange(start=start, end=end)

    match = DATE_PATTERN.search(query)
    if match:
        start = datetime.fromisoformat(match.group(1)).replace(tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        return TimeRange(start=start, end=end)

    return None


def filter_by_time(
    memories: list[LongTermMemory],
    time_range: TimeRange | None,
) -> list[LongTermMemory]:
    if time_range is None:
        return memories

    return [
        memory
        for memory in memories
        if time_range.start <= memory.created_at < time_range.end
    ]
