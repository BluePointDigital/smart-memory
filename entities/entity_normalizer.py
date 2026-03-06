"""Deterministic entity normalization helpers."""

from __future__ import annotations

import re

from smart_memory_config import EntityNormalizationConfig


WHITESPACE_RE = re.compile(r"\s+")
NON_ALNUM_RE = re.compile(r"[^a-z0-9_ ]+")


TYPE_PREFIXES = {
    "person": "person",
    "company": "company",
    "project": "project",
    "product": "product",
    "location": "location",
    "task": "task",
}


class EntityNormalizer:
    def __init__(self, config: EntityNormalizationConfig | None = None) -> None:
        self.config = config or EntityNormalizationConfig()

    def normalize_surface(self, value: str) -> str:
        normalized = value.strip().lower().replace("-", " ").replace("_", " ")
        normalized = NON_ALNUM_RE.sub("", normalized)
        normalized = WHITESPACE_RE.sub(" ", normalized)
        return normalized[: self.config.max_entity_length].strip()

    def infer_type(self, value: str) -> str | None:
        lowered = self.normalize_surface(value)
        if not self.config.infer_types:
            return None
        for key, entity_type in TYPE_PREFIXES.items():
            if lowered.startswith(f"{key} "):
                return entity_type
        if lowered.startswith("proj ") or lowered.startswith("project "):
            return "project"
        if lowered.startswith("task "):
            return "task"
        return None

    def stable_id(self, value: str, *, entity_type: str | None = None) -> str:
        surface = self.normalize_surface(value).replace(" ", "_")
        prefix = entity_type or self.infer_type(value)
        if prefix:
            return f"{prefix}_{surface}"
        return surface
