"""Entity alias resolution utilities."""

from __future__ import annotations

from .entity_registry import EntityRegistry


class EntityAliasResolver:
    """Maps entity aliases to canonical entity ids."""

    def __init__(self, registry: EntityRegistry | None = None) -> None:
        self.registry = registry or EntityRegistry()

    def resolve(self, value: str) -> str:
        return self.registry.resolve(value)

    def canonicalize_many(self, values: list[str]) -> list[str]:
        return self.registry.canonicalize_many(values)
