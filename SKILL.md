---
name: smart-memory
description: Persistent local revision-aware memory for OpenClaw via a Node adapter and FastAPI engine.
---

# Smart Memory v3 Skill

Smart Memory v3 is a local cognitive memory runtime with revision-aware ingestion, pinned context lanes, entity-aware retrieval, and bounded prompt composition.

Core runtime:
- Node adapter: `smart-memory/index.js`
- Local API: `server.py`
- System facade: `cognitive_memory_system.py`
- Canonical store: `storage/sqlite_memory_store.py`

## Core Capabilities

- typed long-term memory including `preference`, `identity`, and `task_state`
- revision-aware lifecycle decisions and supersession chains
- explicit core and working memory lanes
- entity-aware retrieval with lightweight relationship hints
- hot-memory compatibility projection for working context
- strict token-bounded prompt composition with trace metadata
- inspection endpoints for history, active version, lanes, and eval runs

## OpenClaw Integration

Use the native wrapper package in `skills/smart-memory-openclaw/`.

Primary exports:
- `createSmartMemorySkill(options)`
- `createOpenClawHooks({ skill, agentIdentity, summarizeWithLLM })`

The wrapper remains stable while the backend is now v3 under the hood.

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

Stable endpoints:
- `GET /health`
- `POST /ingest`
- `POST /retrieve`
- `POST /compose`
- `POST /run_background`
- `GET /memories`
- `GET /memory/{memory_id}`
- `GET /insights/pending`

New v3 endpoints:
- `POST /revise`
- `GET /memory/{memory_id}/history`
- `GET /memory/{memory_id}/active`
- `GET /memory/{memory_id}/chain`
- `GET /lanes/{lane_name}`
- `POST /lanes/{lane_name}/{memory_id}`
- `DELETE /lanes/{lane_name}/{memory_id}`
- `GET /eval/suite/{suite_name}`
- `GET /eval/case/{case_id}`

## Operating guidance

- query memory before speaking when continuity matters
- do not claim prior context unless retrieval actually supports it
- treat SQLite as canonical storage in v3
- use JSON only for migration, export, and fixtures
- keep CPU-only PyTorch policy intact

## Deprecated

Legacy vector-memory CLI artifacts remain deprecated and should not be revived in v3 work.

