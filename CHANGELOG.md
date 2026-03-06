# Changelog

## [3.1.0-experimental] - 2026-03-06

### Added
- Transcript-first runtime architecture with canonical `sessions`, `transcript_messages`, and `memory_evidence` tables.
- Transcript append APIs and inspection endpoints.
- Evidence-backed revision history and memory evidence lookup.
- Deterministic rebuild and replay from transcript history.
- Transcript-first regression tests covering evidence linkage, replay, rebuild, and transcript-backed lane behavior.

### Changed
- SQLite is now the only canonical runtime backend.
- Runtime ingest now commits transcript records before deriving or revising memory.
- Durable memories now carry derivation metadata and evidence summaries.
- Core and working lane promotion require transcript-backed active memories.
- Hot memory is now a derived compatibility projection instead of a source of truth.
- Evaluation modes now focus on live ingest, replay equivalence, partial replay, and evidence-backed inspection.
- Product docs now describe transcript-first rebuildability rather than migration-centric v3 messaging.

### Removed from the normal runtime path
- legacy alias compatibility in live schema validation
- migration-first runtime assumptions
- v2 baseline comparison as a product concern
- JSON store dependence in the active runtime path

---
## [3.0.0-experimental] - 2026-03-06

### Added
- Canonical SQLite-backed v3 memory store with JSON migration/export compatibility.
- Revision-aware ingestion with deterministic `ADD`, `UPDATE`, `SUPERSEDE`, `EXPIRE`, `NOOP`, and conservative `MERGE` decisions.
- First-class core and working memory lanes plus lane inspection and promotion APIs.
- Stable entity normalization, registry, and lightweight relationship hints for entity-aware retrieval.
- Context assembly v2 with core lane inclusion traces and status-aware retrieval filtering.
- Evaluation harness, migration scaffolding, and v3 regression tests.

### Changed
- Memory schema is now v3-first with status, revision links, validity windows, lane eligibility, retrieval tags, and optional structured facets.
- Retrieval excludes superseded and expired memories by default and applies configurable scoring weights.
- HTTP API remains additive-compatible while exposing new revision, lane, history, and eval endpoints.
- Repository documentation now reflects the v3 architecture, storage model, lane semantics, and integration flow.

---
## [2.5.0] - 2026-03-05

### Added
- New native OpenClaw skill package at `skills/smart-memory-openclaw/` for the local FastAPI cognitive engine.
- Three active memory tools:
  - `memory_search`
  - `memory_commit`
  - `memory_insights`
- Tool-level mandatory health gate (`GET /health`) before execution.
- Persistent retry queue (`.memory_retry_queue.json`) for failed memory commits when server/embedder is unavailable.
- Automatic retry queue flush on healthy tool calls and heartbeat.
- Session arc lifecycle capture:
  - mid-session checkpoint every 20 turns
  - session-end episodic capture hook
- Passive prompt injection middleware for `[ACTIVE CONTEXT]` formatting and pending insight guidance.
- OpenClaw hook helper (`openclaw-hooks.js`) for turn and teardown integration.
