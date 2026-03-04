"""Entity registry package."""

from .alias_resolver import EntityAliasResolver
from .registry import EntityAlias, EntityRegistry

__all__ = ["EntityAlias", "EntityAliasResolver", "EntityRegistry"]
