"""Deterministic fallback embedder.

Use this when a semantic model backend is unavailable.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

from .base_embedder import TextEmbedder


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-]{2,}")


class HashingTextEmbedder:
    """Feature-hash token embeddings for deterministic fallback retrieval."""

    def __init__(self, dimension: int = 384) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self.dimension = dimension
        self.model_name = f"hashing_bow_{dimension}d_v1"

    def _index_for_token(self, token: str) -> int:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], byteorder="big", signed=False) % self.dimension

    def _sign_for_token(self, token: str) -> float:
        digest = hashlib.sha256((token + "_sign").encode("utf-8")).digest()
        return 1.0 if (digest[0] % 2 == 0) else -1.0

    def embed(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimension, dtype=np.float32)
        tokens = TOKEN_PATTERN.findall(text.lower())

        if not tokens:
            return vector

        for token in tokens:
            index = self._index_for_token(token)
            sign = self._sign_for_token(token)
            vector[index] += sign

        norm = float(np.linalg.norm(vector))
        if norm > 0.0:
            vector /= norm

        return vector
