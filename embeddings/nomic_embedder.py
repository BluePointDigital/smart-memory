"""Local Nomic embedding model wrapper.

Requires:
- sentence-transformers
- model: nomic-ai/nomic-embed-text-v1.5
"""

from __future__ import annotations

import numpy as np


class NomicTextEmbedder:
    """SentenceTransformer-based local Nomic embedder."""

    def __init__(
        self,
        model_name: str = "nomic-ai/nomic-embed-text-v1.5",
        *,
        normalize_embeddings: bool = True,
        trust_remote_code: bool = True,
        device: str | None = None,
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:  # pragma: no cover - dependency-availability branch
            raise RuntimeError(
                "sentence-transformers is required for Nomic embeddings"
            ) from error

        self.model_name = model_name
        self._normalize_embeddings = normalize_embeddings

        kwargs = {"trust_remote_code": trust_remote_code}
        if device:
            kwargs["device"] = device

        self._model = SentenceTransformer(model_name, **kwargs)

        # Nomic v1.5 emits 768-dimensional embeddings.
        self.dimension = 768

    def embed(self, text: str) -> np.ndarray:
        if not text.strip():
            return np.zeros(self.dimension, dtype=np.float32)

        vector = self._model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=self._normalize_embeddings,
        )
        vector = np.asarray(vector, dtype=np.float32)

        if vector.ndim != 1:
            vector = vector.reshape(-1)

        if vector.shape[0] != self.dimension:
            self.dimension = int(vector.shape[0])

        return vector
