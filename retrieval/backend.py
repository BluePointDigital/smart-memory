"""Prompt-composer retrieval backend adapter."""

from __future__ import annotations

from typing import Sequence

from prompt_engine.schemas import LongTermMemory

from .retrieval_pipeline import RetrievalPipeline


class PromptComposerRetrievalBackend:
    """Adapter implementing prompt_engine.memory_retriever.RetrievalBackend."""

    def __init__(self, pipeline: RetrievalPipeline | None = None) -> None:
        self.pipeline = pipeline or RetrievalPipeline()

    def retrieve(
        self,
        query: str,
        *,
        entities: Sequence[str],
        max_candidates: int,
    ) -> list[LongTermMemory]:
        return self.pipeline.retrieve_candidates(
            user_message=query,
            entities=list(entities),
            max_candidates=max_candidates,
        )
