# Hot Memory and Working Context in v3.1

Smart Memory v3.1 keeps the existing hot-memory file, but its role is now explicitly downstream of transcript-backed derived memory.

It is not a source of truth. The canonical runtime path is:

`transcripts -> derived memory -> lane assignment -> prompt assembly`

`data/hot_memory/hot_memory.json` remains as a compatibility projection used by the current runtime and prompt renderer.

## What hot memory does now

The compatibility layer still stores:

- `active_projects`
- `working_questions`
- `top_of_mind`
- `insight_queue`
- `agent_state`
- reinforcement timestamps and retrieval counters
- recent memory references

This keeps the current prompt surface and older helper paths working while the working lane owns the actual durable continuity model.

## Relationship to working lane

- The working lane stores active context membership in SQLite.
- `WorkingMemoryManager` decides which transcript-backed memories belong in working context.
- `CognitiveMemorySystem.compose_prompt()` projects working-lane state into the hot-memory structure if the caller does not provide one.
- Rebuild regenerates `hot_memory.json` from derived lane state.

In practice, the working lane is the source of truth and hot memory is the compatibility transport.

## Relationship to core lane

Core memories are not mixed into the generic hot-memory block. They are rendered separately as `[CORE MEMORY]` so pinned durable context remains visible and inspectable.

## Cooling and decay

`hot_memory/store.py` still supports cooling logic for active projects, working questions, and top-of-mind items. In v3.1, those controls complement lane demotion policy rather than replacing it.

## Current file location

```text
data/hot_memory/hot_memory.json
```

## Debugging tips

Use these endpoints to understand what is happening:

- `GET /lanes/working` to inspect the canonical working lane
- `GET /lanes/core` to inspect pinned durable context
- `GET /memory/{memory_id}/evidence` to inspect transcript backing
- `GET /insights/pending` to inspect the live insight queue
- `POST /compose` to verify what the renderer actually includes
- `POST /rebuild` to regenerate the projection from transcript truth

## Important boundary

Do not build new durable-memory features directly on top of `hot_memory.json`.

For v3.1 development:

- durable truth begins in transcripts
- revision logic belongs in ingestion and revision layers
- durable memory belongs in SQLite
- working continuity belongs in working-lane policy
- hot memory exists only to keep the current runtime surface stable
