---
name: smart-memory
description: "Persistent local transcript-first memory via FastAPI (127.0.0.1:8000). Use for semantic recall, durable memory commits, transcript inspection, and pending insight retrieval through the Smart Memory v3.1 backend."
metadata:
  {"openclaw":{"emoji":"??","requires":{"bins":["curl"]}}}
---

# Smart Memory OpenClaw Skill

This skill wraps the Smart Memory backend running at `http://127.0.0.1:8000`.

The wrapper package lives in `skills/smart-memory-openclaw/`, and the backend it targets is Smart Memory v3.1 with transcript-first ingestion, SQLite-backed durable memory, evidence-backed revision chains, status-aware retrieval, and explicit core and working memory lanes.

## When to Use

Use this skill when you need to:

- recall prior decisions, preferences, goals, or project state
- persist important new facts, pivots, completions, or blockers
- inspect transcript-backed evidence behind a memory
- inspect pending insights from background cognition
- ground an OpenClaw session in local memory continuity

Do not use it when the recent context window already fully answers the question or when the local memory server is unavailable.

## Prerequisites

```bash
curl -s http://127.0.0.1:8000/health
```

If the server is not running, start it from the repo root:

```bash
.\.venv\Scripts\python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

## OpenClaw Configuration

Disable OpenClaw's built-in file-search memory tools so this skill's semantic path takes precedence:

```bash
openclaw config set tools.deny '["memory_search", "memory_get"]'
openclaw gateway restart
```

## Core Operations

### Search memory

```bash
curl -s -X POST http://127.0.0.1:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"user_message":"What did we decide about the database migration?"}'
```

Notes:

- retrieval excludes superseded and expired memories by default
- use natural-language queries instead of keyword fragments
- use transcript and evidence endpoints when you need deeper inspection

### Commit memory

```bash
curl -s -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "user_message":"Deployment is blocked on config diff review.",
    "assistant_message":"Captured as active task state.",
    "source_session_id":"session-123"
  }'
```

Notes:

- semantic changes become revision actions such as `SUPERSEDE`
- metadata-only changes can `UPDATE`
- failed commits are queued in `.memory_retry_queue.json` by the wrapper

### Check insights

```bash
curl -s http://127.0.0.1:8000/insights/pending
```

## Useful inspection endpoints

```bash
curl -s http://127.0.0.1:8000/memories
curl -s http://127.0.0.1:8000/memory/<memory_id>
curl -s http://127.0.0.1:8000/memory/<memory_id>/evidence
curl -s http://127.0.0.1:8000/memory/<memory_id>/history
curl -s http://127.0.0.1:8000/memory/<memory_id>/active
curl -s http://127.0.0.1:8000/memory/<memory_id>/chain
curl -s http://127.0.0.1:8000/transcripts/<session_id>
curl -s http://127.0.0.1:8000/lanes/core
curl -s http://127.0.0.1:8000/lanes/working
curl -s -X POST http://127.0.0.1:8000/rebuild
```

## Prompt guidance

If pending insights appear in context and they genuinely relate to the current conversation, surface them naturally. Do not force them in.

## Operational notes

- the wrapper health-checks the backend before tool calls
- failed commits queue locally and flush on later healthy calls
- session-arc capture and prompt injection still live in this package
- transcript rows are canonical truth and memories are derived
