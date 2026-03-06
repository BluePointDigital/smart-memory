---
name: smart-memory
description: Persistent local transcript-first memory for OpenClaw via a Node adapter and FastAPI engine.
---

# Smart Memory v3.1 Skill

Smart Memory v3.1 is a local transcript-first cognitive memory runtime with revision-aware derivation, pinned context lanes, entity-aware retrieval, and bounded prompt composition.

Core runtime:
- Node adapter: `smart-memory/index.js`
- Local API: `server.py`
- System facade: `cognitive_memory_system.py`
- Canonical store: `storage/sqlite_memory_store.py` plus `transcripts/`

## Core Capabilities

- transcript-first ingest and per-message transcript logging
- typed long-term memory including `preference`, `identity`, and `task_state`
- evidence-backed revision lifecycle decisions and supersession chains
- explicit core and working memory lanes
- entity-aware retrieval with lightweight relationship hints
- deterministic rebuild from transcript history
- hot-memory compatibility projection for working context
- strict token-bounded prompt composition with trace metadata
- inspection endpoints for transcripts, evidence, history, lanes, and eval runs

## OpenClaw Integration

Use the native wrapper package in `skills/smart-memory-openclaw/`.

Primary exports:
- `createSmartMemorySkill(options)`
- `createOpenClawHooks({ skill, agentIdentity, summarizeWithLLM })`

The wrapper remains stable while the backend is now transcript-first under the hood.

### Tool Interface

1. `memory_search`
- purpose: query relevant memory through `/retrieve`
- supports `query`, `type`, `limit`, `min_relevance`, and optional `conversation_history`
- health-checks the backend before execution

2. `memory_commit`
- purpose: persist important facts, decisions, beliefs, goals, or session summaries
- health-checks the backend before execution
- serializes commits to protect local embedding throughput
- queues failed commits in `.memory_retry_queue.json`

3. `memory_insights`
- purpose: surface pending background insights
- health-checks the backend before execution
- calls `/insights/pending`

## API Endpoints

Core endpoints:
- `GET /health`
- `POST /ingest`
- `POST /retrieve`
- `POST /compose`
- `POST /run_background`
- `GET /memories`
- `GET /memory/{memory_id}`
- `GET /insights/pending`

Transcript and inspection endpoints:
- `POST /transcripts/message`
- `GET /transcripts/{session_id}`
- `GET /transcript/message/{message_id}`
- `GET /memory/{memory_id}/evidence`
- `POST /revise`
- `GET /memory/{memory_id}/history`
- `GET /memory/{memory_id}/active`
- `GET /memory/{memory_id}/chain`
- `GET /lanes/{lane_name}`
- `POST /lanes/{lane_name}/{memory_id}`
- `DELETE /lanes/{lane_name}/{memory_id}`
- `POST /rebuild`
- `POST /rebuild/{session_id}`
- `GET /eval/suite/{suite_name}`
- `GET /eval/case/{case_id}`

## Operating guidance

- query memory before speaking when continuity matters
- do not claim prior context unless retrieval actually supports it
- transcripts are canonical, memories are derived
- treat SQLite as canonical runtime storage
- treat JSON as offline export or backup only
- keep CPU-only PyTorch policy intact

## Deprecated

Legacy vector-memory CLI artifacts remain deprecated and should not be revived.
