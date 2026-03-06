"""Persistent hot-memory state with reinforcement metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from prompt_engine.schemas import AgentState, AgentStatus, HotMemory


@dataclass
class HotMemoryBundle:
    hot_memory: HotMemory
    reinforcement: dict[str, dict[str, str]]
    retrieval_counts: dict[str, int]
    memory_refs: list[str]


class HotMemoryStore:
    """File-backed hot memory store for fast read/write."""

    def __init__(self, path: str | Path = "data/hot_memory/hot_memory.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _default_hot_memory(self) -> HotMemory:
        now = datetime.now(timezone.utc)
        return HotMemory(
            agent_state=AgentState(
                status=AgentStatus.IDLE,
                last_interaction_timestamp=now,
                last_background_task="none",
            ),
            active_projects=[],
            working_questions=[],
            top_of_mind=[],
            insight_queue=[],
        )

    def _default_bundle(self) -> HotMemoryBundle:
        return HotMemoryBundle(
            hot_memory=self._default_hot_memory(),
            reinforcement={
                "active_projects": {},
                "working_questions": {},
                "top_of_mind": {},
            },
            retrieval_counts={},
            memory_refs=[],
        )

    def load_bundle(self) -> HotMemoryBundle:
        if not self.path.exists():
            return self._default_bundle()

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        hot_memory = HotMemory.model_validate(payload["hot_memory"])

        reinforcement = payload.get("reinforcement", {})
        retrieval_counts = payload.get("retrieval_counts", {})
        memory_refs = payload.get("memory_refs", [])

        return HotMemoryBundle(
            hot_memory=hot_memory,
            reinforcement={
                "active_projects": dict(reinforcement.get("active_projects", {})),
                "working_questions": dict(reinforcement.get("working_questions", {})),
                "top_of_mind": dict(reinforcement.get("top_of_mind", {})),
            },
            retrieval_counts={key: int(value) for key, value in retrieval_counts.items()},
            memory_refs=[str(value) for value in memory_refs],
        )

    def save_bundle(self, bundle: HotMemoryBundle) -> None:
        payload = {
            "hot_memory": bundle.hot_memory.model_dump(mode="json"),
            "reinforcement": bundle.reinforcement,
            "retrieval_counts": bundle.retrieval_counts,
            "memory_refs": bundle.memory_refs,
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get_hot_memory(self) -> HotMemory:
        return self.load_bundle().hot_memory

    def set_hot_memory(self, hot_memory: HotMemory) -> None:
        bundle = self.load_bundle()
        bundle.hot_memory = hot_memory
        self.save_bundle(bundle)

    def reset(self) -> HotMemory:
        bundle = self._default_bundle()
        self.save_bundle(bundle)
        return bundle.hot_memory

    def add_memory_ref(self, memory_id: str, cap: int = 200) -> None:
        bundle = self.load_bundle()
        refs = [value for value in bundle.memory_refs if value != memory_id]
        refs.insert(0, memory_id)
        bundle.memory_refs = refs[:cap]
        self.save_bundle(bundle)

    def reinforce(self, section: str, item: str, at: datetime | None = None) -> None:
        bundle = self.load_bundle()
        at = at or datetime.now(timezone.utc)

        if section not in bundle.reinforcement:
            bundle.reinforcement[section] = {}

        bundle.reinforcement[section][item] = at.isoformat()
        self.save_bundle(bundle)

    def increment_retrieval(self, memory_id: str) -> int:
        bundle = self.load_bundle()
        bundle.retrieval_counts[memory_id] = bundle.retrieval_counts.get(memory_id, 0) + 1
        count = bundle.retrieval_counts[memory_id]

        refs = [value for value in bundle.memory_refs if value != memory_id]
        refs.insert(0, memory_id)
        bundle.memory_refs = refs[:200]

        self.save_bundle(bundle)
        return count

    def cool(self, *, ttl_hours: int = 36, now: datetime | None = None) -> HotMemory:
        bundle = self.load_bundle()
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=ttl_hours)

        def keep(section: str, values: list[str]) -> list[str]:
            result: list[str] = []
            for value in values:
                reinforced = bundle.reinforcement.get(section, {}).get(value)
                if reinforced is None:
                    continue
                try:
                    timestamp = datetime.fromisoformat(reinforced)
                except ValueError:
                    continue

                if timestamp >= cutoff:
                    result.append(value)
            return result

        hot = bundle.hot_memory
        hot = HotMemory(
            agent_state=hot.agent_state,
            active_projects=keep("active_projects", hot.active_projects),
            working_questions=keep("working_questions", hot.working_questions),
            top_of_mind=keep("top_of_mind", hot.top_of_mind),
            insight_queue=[
                insight
                for insight in hot.insight_queue
                if insight.expires_at is None or insight.expires_at >= now
            ],
        )

        bundle.hot_memory = hot
        self.save_bundle(bundle)
        return hot
