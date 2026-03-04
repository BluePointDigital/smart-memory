"""Memory consolidation agent for redundant memories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from prompt_engine.schemas import LongTermMemory, MemorySource, SemanticMemory


@dataclass(frozen=True)
class ConsolidationResult:
    summary_memories: list[SemanticMemory]
    consolidated_memory_ids: list[str]


class MemoryConsolidationAgent:
    """Create summary memories from clusters sharing major entities."""

    def consolidate(self, memories: list[LongTermMemory]) -> ConsolidationResult:
        groups: dict[str, list[LongTermMemory]] = {}

        for memory in memories:
            key = memory.entities[0] if memory.entities else "_ungrouped"
            groups.setdefault(key, []).append(memory)

        summaries: list[SemanticMemory] = []
        consolidated_ids: list[str] = []
        now = datetime.now(timezone.utc)

        for entity, group in groups.items():
            if entity == "_ungrouped" or len(group) < 3:
                continue

            top_items = sorted(group, key=lambda item: item.importance, reverse=True)[:5]
            summary_text = " ; ".join(item.content for item in top_items)
            avg_importance = sum(item.importance for item in top_items) / len(top_items)

            summaries.append(
                SemanticMemory(
                    content=f"Consolidated summary for {entity}: {summary_text}",
                    importance=min(1.0, max(0.55, avg_importance)),
                    created_at=now,
                    last_accessed=now,
                    access_count=0,
                    schema_version="2.0",
                    entities=sorted({ent for item in top_items for ent in item.entities}),
                    relations=[],
                    emotional_valence=0.0,
                    emotional_intensity=0.0,
                    source=MemorySource.REFLECTION,
                    confidence=min(1.0, max(0.60, avg_importance)),
                )
            )

            consolidated_ids.extend([str(item.id) for item in top_items])

        return ConsolidationResult(
            summary_memories=summaries,
            consolidated_memory_ids=consolidated_ids,
        )
