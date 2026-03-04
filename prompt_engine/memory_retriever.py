"""Memory retrieval orchestration with graceful degradation.

This module wraps any retrieval backend with timeout and validation guarantees.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol, Sequence

from pydantic import TypeAdapter

from .schemas import LongTermMemory


LONG_TERM_MEMORY_LIST = TypeAdapter(list[LongTermMemory])


class RetrievalBackend(Protocol):
    def retrieve(
        self,
        query: str,
        *,
        entities: Sequence[str],
        max_candidates: int,
    ) -> list[LongTermMemory] | list[dict]:
        """Return up to max_candidates candidate memories."""


@dataclass
class RetrievalResult:
    candidates: list[LongTermMemory]
    degraded: bool
    error: str | None
    elapsed_ms: int


def retrieve_with_fallback(
    query: str,
    entities: Sequence[str],
    backend: RetrievalBackend | None,
    *,
    max_candidates: int = 30,
    timeout_ms: int = 500,
) -> RetrievalResult:
    """Retrieve memory candidates, degrading safely on timeout/failure."""

    started = perf_counter()

    if backend is None:
        elapsed = int((perf_counter() - started) * 1000)
        return RetrievalResult(
            candidates=[],
            degraded=True,
            error="retrieval backend unavailable",
            elapsed_ms=elapsed,
        )

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                backend.retrieve,
                query,
                entities=entities,
                max_candidates=max_candidates,
            )
            raw_candidates = future.result(timeout=timeout_ms / 1000)

        validated = LONG_TERM_MEMORY_LIST.validate_python(raw_candidates)
        elapsed = int((perf_counter() - started) * 1000)

        return RetrievalResult(
            candidates=validated[:max_candidates],
            degraded=False,
            error=None,
            elapsed_ms=elapsed,
        )
    except TimeoutError:
        elapsed = int((perf_counter() - started) * 1000)
        return RetrievalResult(
            candidates=[],
            degraded=True,
            error=f"retrieval timeout after {timeout_ms}ms",
            elapsed_ms=elapsed,
        )
    except Exception as error:  # noqa: BLE001
        elapsed = int((perf_counter() - started) * 1000)
        return RetrievalResult(
            candidates=[],
            degraded=True,
            error=str(error),
            elapsed_ms=elapsed,
        )
