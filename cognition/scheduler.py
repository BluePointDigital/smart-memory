"""Scheduling helpers for background cognition cadence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class CognitionCadence:
    reflection_hours: int = 4
    associative_hours: int = 4
    consolidation_hours: int = 12
    decay_hours: int = 24
    belief_resolver_hours: int = 24


class CognitionScheduleState:
    """Persistent schedule state for cognition task execution."""

    def __init__(self, path: str | Path = "data/cognition/schedule_state.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, state: dict[str, str]) -> None:
        self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def is_due(self, *, task_name: str, interval_hours: int, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        state = self.load()

        last_run_raw = state.get(task_name)
        if not last_run_raw:
            return True

        try:
            last_run = datetime.fromisoformat(last_run_raw)
        except ValueError:
            return True

        return now - last_run >= timedelta(hours=interval_hours)

    def mark_run(self, task_name: str, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        state = self.load()
        state[task_name] = now.isoformat()
        self.save(state)
