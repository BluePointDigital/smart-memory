# Prompt Engine

This package contains the prompt composition layer used by Smart Memory v3.1.

## Responsibilities

- build temporal state for the current interaction
- extract lightweight prompt-time entities from the active query and history
- retrieve and rerank relevant memories through a retrieval backend
- render deterministic prompt sections with strict token enforcement
- expose memory inclusion traces for inspection

## Current assembly order

The renderer assembles prompt context in this order:

1. agent identity
2. temporal state
3. core memory
4. working context
5. background insights
6. retrieved memory
7. recent conversation and current user message

Core memory is preserved ahead of retrieved memory unless explicit trimming is enabled.

## Key modules

- `schemas.py`: canonical Pydantic contracts for prompt requests, transcript-derived memory records, lanes, and traces
- `state_detector.py`: temporal and interaction-state generation
- `entity_extractor.py`: lightweight prompt-time entity extraction
- `memory_retriever.py`: retrieval wrapper with timeout and graceful fallback
- `memory_reranker.py`: query-time reranking for retrieved candidates
- `token_allocator.py`: budget allocation across identity, temporal, core, working, insights, retrieval, and conversation
- `prompt_renderer.py`: bounded rendering with deterministic eviction
- `composer.py`: end-to-end orchestration and trace creation

## Trace metadata

`PromptComposerOutput` includes `memory_traces`, where each trace carries:

- `memory_id`
- `lane`
- `memory_type`
- `status`
- `inclusion_reason`
- `token_estimate`

This is the inspectable link between retrieval or lane state and the rendered prompt.

## Working-context note

The current renderer still consumes `HotMemory` for the `[WORKING CONTEXT]` section. In v3.1, `CognitiveMemorySystem` fills that structure from the working-lane manager when the caller omits it, so prompt composition remains compatible while transcript-backed lane state stays canonical.

## Scope boundary

This package does not own:

- transcript persistence
- durable storage
- vector indexing implementation
- background scheduling
- revision-policy decisions

It consumes those subsystems and produces bounded prompt context.
