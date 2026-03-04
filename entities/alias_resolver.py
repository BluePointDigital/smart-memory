"""Entity alias resolution utilities."""

from __future__ import annotations

import re

from .registry import EntityRegistry


WHITESPACE_RE = re.compile(r"\s+")


def _normalize_alias(value: str) -> str:
    normalized = value.strip().lower().replace("-", " ").replace("_", " ")
    normalized = WHITESPACE_RE.sub(" ", normalized)
    return normalized


def _normalize_entity_id(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


class EntityAliasResolver:
    """Maps user/entity aliases to canonical entity ids."""

    def __init__(self, registry: EntityRegistry | None = None) -> None:
        self.registry = registry or EntityRegistry()

    def resolve(self, value: str) -> str:
        normalized = _normalize_alias(value)

        for entry in self.registry.load():
            if normalized == _normalize_alias(entry.canonical_name):
                return entry.entity_id
            for alias in entry.aliases:
                if normalized == _normalize_alias(alias):
                    return entry.entity_id

        return _normalize_entity_id(value)

    def canonicalize_many(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            resolved = self.resolve(value)
            if resolved and resolved not in seen:
                deduped.append(resolved)
                seen.add(resolved)
        return deduped
