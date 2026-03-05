# Prompt Engine

This package contains the prompt composition layer used by Smart Memory v2.

## Included Modules

- `schemas.py`: Canonical Pydantic contracts
- `state_detector.py`: Interaction-state and temporal-state generation
- `entity_extractor.py`: Lightweight entity extraction
- `memory_retriever.py`: Retrieval wrapper with timeout and graceful fallback
- `memory_reranker.py`: Candidate scoring and top-k selection
- `token_allocator.py`: State-aware token budget allocation
- `prompt_renderer.py`: Prompt assembly with per-section clipping
- `composer.py`: Orchestrates the full pipeline

## Scope

- Data contracts and orchestration only.
- No storage engine, vector index, or background scheduler implementation in this package.
