# Agent Integration Guide

Smart Memory v3.1 is transcript-first. Your agent should treat transcript append as the durable write, and treat memory retrieval as a derived convenience layer.

## Core pattern

1. Check `GET /health`.
2. Prime with `POST /compose`.
3. Use `POST /retrieve` when the topic shifts or the user asks for prior context.
4. Persist turns with `POST /ingest` or `POST /transcripts/message`.
5. Use transcript and evidence endpoints when debugging or rebuilding.

## Startup flow

```text
Agent starts
-> GET /health
-> POST /compose
-> respond with primed context
```

Why `/compose` first:

- it includes core lane without search
- it includes working lane as bounded active context
- it adds retrieved memory only after core and working context
- it returns inclusion traces for inspection

## Ingesting turns

### Preferred high-level route

Use `POST /ingest` for a user/assistant turn pair.

The server will:

1. append transcript rows first
2. derive candidate memories from the appended messages
3. run revision logic
4. update lanes, entities, vectors, and audit events

Example:

```json
{
  "user_message": "I prefer coffee now instead of tea.",
  "assistant_message": "Preference updated.",
  "source_session_id": "session-42"
}
```

### Low-level transcript route

Use `POST /transcripts/message` when the host wants explicit per-message control.

Example:

```json
{
  "session_id": "session-42",
  "role": "user",
  "source_type": "conversation",
  "content": "Deployment is blocked on config review."
}
```

## Retrieval

Call `/retrieve` when:

- the user asks about prior decisions, preferences, or history
- the agent pivots to a different project or entity cluster
- the host wants history mode with `include_history=true`
- the host wants entity-scoped recall with `entity_scope`

Example:

```json
{
  "user_message": "What did we decide about the database migration?",
  "conversation_history": "",
  "include_history": false,
  "entity_scope": ["database migration"]
}
```

## Evidence and transcript inspection

Use these when debugging trust or lifecycle behavior:

- `GET /transcripts/{session_id}`
- `GET /transcript/message/{message_id}`
- `GET /memory/{memory_id}/evidence`
- `GET /memory/{memory_id}/history`
- `GET /memory/{memory_id}/chain`

These endpoints show the transcript-backed lineage behind active, superseded, or expired memories.

## Rebuild operations

Use rebuild when you change extraction or revision logic and want to recover derived state from transcript truth.

- `POST /rebuild`
- `POST /rebuild/{session_id}`

Current implementation note:

- rebuild requests replay transcript history deterministically and regenerate memory, lanes, entities, relationship hints, vectors, and the hot-memory projection

## Lane-aware integration

- `core` is always-visible durable context
- `working` is bounded active task context
- `retrieved` is runtime-selected and not canonical persisted truth

Do not build a second pinning or working-context system on top of this unless you have a specific reason.

## OpenClaw guidance

The OpenClaw wrapper remains in [skills/smart-memory-openclaw](/D:/Users/JamesMSI/Desktop/LLM%20Projects/Smart%20Memory/smart-memory/.release-repo/skills/smart-memory-openclaw).

Recommended host behavior:

- use the skill for commit/search/insight workflows
- keep transcript append and memory inspection local
- let Smart Memory own revision logic and lane derivation
- treat `hot_memory.json` as a compatibility projection, not a source of truth

## Failure handling

If the local service is unavailable, continue without fabricated continuity and say so explicitly.

Example:

`I could not reach the local memory service, so I am continuing without reliable prior context.`
