# Agent Integration Guide

Smart Memory v3 is meant to be queried by the agent itself, not treated as a passive dump of retrieved text. The integration goal is simple: the agent should wake up, check memory health, pull current context, and then respond from continuity.

## Core pattern

1. Check `GET /health` before relying on memory.
2. Prime with `POST /compose` before the first response.
3. Use `POST /retrieve` when the topic shifts or the user asks for prior decisions, preferences, or history.
4. Persist continuity with `POST /ingest` after meaningful turns.
5. Use revision and lane inspection endpoints when the host needs explicit lifecycle or pinning control.

## Session startup

The minimum reliable startup flow is:

```text
Agent process starts
-> GET /health
-> POST /compose
-> hold returned prompt and memory traces in agent state
-> answer the user
```

Why `/compose` first:

- it includes core memory without requiring retrieval
- it includes working context through the hot-memory compatibility layer
- it can include retrieved memory when relevant
- it exposes trace metadata so the host can inspect why context was included

## Recommended compose request

```json
{
  "agent_identity": "You are a persistent cognitive assistant.",
  "current_user_message": "Session start - what are my active projects and priorities?",
  "conversation_history": "",
  "max_prompt_tokens": 512,
  "max_candidate_memories": 30,
  "max_selected_memories": 5,
  "retrieval_timeout_ms": 500
}
```

If `hot_memory`, `core_memories`, or `working_memories` are omitted, the system fills them from the canonical v3 services.

## Mid-session retrieval

Call `/retrieve` when:

- the user asks about earlier work, preferences, decisions, or project history
- the agent pivots to a different project or entity cluster
- the host wants explicit history mode via `include_history=true`
- the host wants entity-scoped recall using `entity_scope`

Example payload:

```json
{
  "user_message": "What did we decide about the database migration?",
  "conversation_history": "",
  "include_history": false,
  "entity_scope": ["database migration"]
}
```

## Ingestion and revision

Use `/ingest` after important turns. The v3 pipeline may return revision-aware actions such as `ADD`, `UPDATE`, `SUPERSEDE`, `EXPIRE`, or `NOOP`.

Use `/revise` when the host already has a fully formed candidate memory payload and wants direct revision processing.

Important contract:

- semantic changes are handled with `SUPERSEDE`
- `UPDATE` is metadata-only
- `MERGE` is intentionally conservative

## Lane-aware integration

Core and working memory are now explicit.

- `GET /lanes/core` inspects always-visible context.
- `GET /lanes/working` inspects active task context.
- `POST /lanes/core/{memory_id}` pins a memory to core.
- `DELETE /lanes/core/{memory_id}` removes a pin.

A good host does not rebuild its own pinning system on top of this. Let the memory backend own durable core context and bounded working context.

## Revision inspection

When debugging lifecycle behavior, use:

- `GET /memory/{memory_id}/history`
- `GET /memory/{memory_id}/active`
- `GET /memory/{memory_id}/chain`

These endpoints are useful when a newer preference, goal state, or task state has replaced older memory and you need to verify that the stale version stopped dominating retrieval.

## OpenClaw guidance

The `skills/smart-memory-openclaw/` package remains the main OpenClaw wrapper, but it now talks to a v3 backend underneath.

Recommended pattern:

- start the Smart Memory server with the Node adapter or your own process manager
- use the skill for `memory_search`, `memory_commit`, and `memory_insights`
- use the prompt injection helper before response generation so the model sees current active context

Still disable OpenClaw's built-in file-search memory tools to avoid shadowing semantic retrieval:

```bash
openclaw config set tools.deny '["memory_search", "memory_get"]'
openclaw gateway restart
```

## Python example

```python
import requests

BASE_URL = "http://127.0.0.1:8000"

health = requests.get(f"{BASE_URL}/health", timeout=5)
health.raise_for_status()

prompt = requests.post(
    f"{BASE_URL}/compose",
    json={
        "agent_identity": "You are a persistent assistant.",
        "current_user_message": "Session start - what matters right now?",
        "conversation_history": "",
        "max_prompt_tokens": 512,
    },
    timeout=10,
)
prompt.raise_for_status()
context = prompt.json()

retrieval = requests.post(
    f"{BASE_URL}/retrieve",
    json={"user_message": "What are the current blockers?"},
    timeout=10,
)
retrieval.raise_for_status()

requests.post(
    f"{BASE_URL}/ingest",
    json={
        "user_message": "We finished the schema review.",
        "assistant_message": "Noted.",
        "source_session_id": "session-123",
        "source_message_ids": ["msg-99"],
    },
    timeout=10,
).raise_for_status()
```

## Node example

```js
import memory from "smart-memory";

await memory.start();

const primed = await memory.getPromptContext({
  agent_identity: "You are a persistent assistant.",
  current_user_message: "Session start - summarize active context.",
  conversation_history: "",
  max_prompt_tokens: 512,
});

const retrieval = await memory.retrieveContext({
  user_message: "What did we decide about deployment?",
  conversation_history: "",
});

await memory.ingestMessage({
  user_message: "Deployment is blocked on a config diff review.",
  assistant_message: "Captured.",
  source_session_id: "session-abc",
  source_message_ids: ["turn-12"],
});
```

## Operational checks

Use these during integration and debugging:

- `GET /health`
- `GET /memories`
- `GET /memory/{memory_id}`
- `GET /insights/pending`
- `GET /lanes/core`
- `GET /lanes/working`
- `GET /eval/case/{case_id}`

## Failure handling

If the memory service is unavailable, keep the agent running but be explicit that continuity is degraded. Do not silently fabricate prior context.

Example:

`I could not reach the local memory service, so I am continuing without reliable prior context.`

