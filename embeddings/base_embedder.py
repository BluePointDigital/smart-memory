"""Base embedding interfaces and factory helpers."""

from __future__ import annotations

import os
from typing import Protocol

import numpy as np


class TextEmbedder(Protocol):
    """Simple embedder contract for ingestion/retrieval components."""

    model_name: str
    dimension: int

    def embed(self, text: str) -> np.ndarray:
        """Return a normalized embedding vector."""


def get_embedder_backend() -> str:
    """Return configured embedder backend name."""

    return os.getenv("COGNITIVE_EMBEDDER", "nomic").strip().lower()
