"""Embedding interfaces and backend implementations."""

from __future__ import annotations

from .base_embedder import TextEmbedder, get_embedder_backend
from .hashing_embedder import HashingTextEmbedder
from .nomic_embedder import NomicTextEmbedder


def create_default_embedder() -> TextEmbedder:
    """Create configured embedder with robust fallback behavior."""

    backend = get_embedder_backend()

    if backend == "hashing":
        return HashingTextEmbedder()

    # Default path: local semantic embeddings via Nomic.
    try:
        return NomicTextEmbedder()
    except Exception:
        # Fallback keeps system functional when model deps are unavailable.
        return HashingTextEmbedder()


__all__ = [
    "HashingTextEmbedder",
    "NomicTextEmbedder",
    "TextEmbedder",
    "create_default_embedder",
    "get_embedder_backend",
]
