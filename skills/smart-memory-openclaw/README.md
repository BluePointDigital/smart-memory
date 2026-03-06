# Smart Memory OpenClaw Skill

This folder contains the OpenClaw-facing skill package at `skills/smart-memory-openclaw/`. It targets the Smart Memory v3.1 backend running at `http://127.0.0.1:8000`.

## Files

- `index.js` - skill class and OpenClaw-friendly factory
- `openclaw-hooks.js` - turn, teardown, and prompt-injection hooks
- `http-client.js` - API client and health checks
- `retry-queue.js` - `.memory_retry_queue.json` persistence and flush logic
- `tagging.js` - commit auto-tag heuristics
- `session-arc.js` - checkpoint and session-end episodic capture
- `prompt-injection.js` - passive active-context injection
- `formatters.js` - tool output formatting
- `constants.js` - shared constants
- `types.js` - JSDoc type definitions

## What changed under v3.1

- the backend is now transcript-first and writes transcript rows before deriving memory
- durable memory is stored in SQLite and linked back to transcript evidence
- retrieval is status-aware and excludes superseded or expired memories by default
- core and working memory are first-class on the backend side
- rebuild can regenerate derived state from transcript history

The skill interface stays stable so existing OpenClaw wiring does not break.

## Tools

### `memory_search`

- health-checks the backend before use
- calls `/retrieve`
- formats selected memory hits for OpenClaw
- still supports `type`, `limit`, `min_relevance`, and optional conversation history

### `memory_commit`

- health-checks the backend before use
- calls `/ingest`
- serializes commits to protect local embedding throughput
- queues failed commits in `.memory_retry_queue.json` when the backend is unreachable

### `memory_insights`

- health-checks the backend before use
- calls `/insights/pending`
- formats background insight output

## Prompt injection

Use the provided hook helpers to inject current active context before model response generation. The backend compose path now includes transcript-backed core memory and working-context projections, so the injected prompt surface can stay stable while the underlying memory model improves.

## Required prompt guidance

Add this line to your base prompt:

`If pending insights appear in your context that relate to the current conversation, surface them naturally to the user. Do not force it, but do not ignore a real connection.`

## Operational notes

- every tool call starts with `GET /health`
- retry queue flushes on healthy tool calls and heartbeat
- disable OpenClaw's built-in `memory_search` and `memory_get` tools so they do not shadow Smart Memory's semantic path
