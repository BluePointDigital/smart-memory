# Prompt Engine (Phase 0 + 1)

This package contains the cognitive prompt composer foundation described in `ARCHITECTURE.md`.

## Included Modules

- `schemas.py`: Canonical Pydantic contracts (Phase 1)
- `state_detector.py`: Interaction-state and temporal-state generation
- `entity_extractor.py`: Lightweight entity extraction
- `memory_retriever.py`: Retrieval wrapper with timeout and graceful fallback
- `memory_reranker.py`: Candidate scoring and top-k selection
- `token_allocator.py`: State-aware token budget allocation
- `prompt_renderer.py`: Prompt assembly with per-section clipping
- `composer.py`: Orchestrates the full pipeline

## Scope

- Data contracts and orchestration only.
- No storage engine, vector index, or background scheduler implementation in this phase.
