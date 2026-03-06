# Hot Memory and Working Context in v3

Smart Memory v3 keeps the existing hot-memory file, but its role has changed.

It is no longer the primary long-term working-memory mechanism. The canonical durable backend is SQLite, and the v3 working lane owns task continuity. `data/hot_memory/hot_memory.json` remains as a compatibility projection used by the current runtime and prompt renderer.

## What hot memory does now

The compatibility layer still stores:

- `active_projects`
- `working_questions`
- `top_of_mind`
- `insight_queue`
- `agent_state`
- reinforcement timestamps and retrieval counters
- recent memory references

This keeps older prompt composition and background-cognition paths working while v3 lane managers own the real promotion and demotion decisions.

## Relationship to working lane

- The working lane stores active memory membership in SQLite.
- `WorkingMemoryManager` decides which durable memories belong in working context.
- `CognitiveMemorySystem.compose_prompt()` projects working-lane state into the hot-memory structure if the caller does not provide one.
- The prompt renderer then renders `[WORKING CONTEXT]` from that projected structure.

In practice, this means the working lane is the source of truth and hot memory is the compatibility transport.

## Relationship to core lane

Core memories are not mixed into the generic hot-memory block. They are rendered separately as `[CORE MEMORY]` so pinned, durable context remains visible and inspectable.

## Cooling and decay

`hot_memory/store.py` still supports cooling logic for active projects, working questions, and top-of-mind items. In v3, those controls complement lane demotion policy rather than replacing it.

## Current file location

```text
data/hot_memory/hot_memory.json
```

## Debugging tips

Use these endpoints to understand what is happening:

- `GET /lanes/working` to inspect the canonical working lane
- `GET /lanes/core` to inspect pinned durable context
- `GET /insights/pending` to inspect the live insight queue
- `POST /compose` to verify what the renderer actually includes

## Important boundary

Do not build new durable-memory features directly on top of `hot_memory.json`. For v3 development:

- durable memory belongs in SQLite
- revision logic belongs in the ingestion and revision layers
- working continuity belongs in working-lane policy
- hot memory exists to keep the current runtime and prompt surface stable while the v3 internals evolve
