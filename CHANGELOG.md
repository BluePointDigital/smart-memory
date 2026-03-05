# Changelog

## [2.5.0] - 2026-03-05

### Added
- New native OpenClaw skill package at `skills/smart-memory-v25/` for the local FastAPI cognitive engine.
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

### Changed
- Memory commit flow now serializes commits to protect local CPU embedding throughput under bursty commit calls.
- Retrieval wrapper now uses compatibility fallback for `/retrieve` payload filters, then applies type/relevance/limit filtering safely client-side.
- Auto-tag fallback is now extensible via rule definitions (`tagging.js`) and includes default `working_question` + `decision` heuristics.
- Documentation sweep completed: README now includes `skills/smart-memory-v25` architecture details, and skill docs now enforce CPU-only PyTorch policy with no GPU fallback guidance.
- README architecture content was consolidated into a whole-system overview, Mermaid flowcharts were simplified for consistent rendering, and obsolete `ARCHITECTURE.md` was removed.

### Fixed
- Commit failure behavior now returns explicit operational state feedback to the agent:
  - `Memory commit failed - server unreachable. Queued for retry.`

---
## [2.3.0] - 2026-03-05

### Added (Hot Memory Extension)
- **Persistent Working Context**: New optional extension for maintaining active projects, working questions, and top-of-mind items across sessions
  - `hot_memory_manager.py`: Core persistence with JSON storage
  - `memory_adapter.py`: API wrapper for seamless `/compose` integration
  - `smem-hook.sh`: Shell hook for post-conversation updates
- **Auto-Detection**: Automatically identifies project mentions and questions from conversation content
  - Keyword-based project detection (Tappy.Menu, Content Foundry, etc.)
  - Question extraction (any message containing `?`)
  - Working context updates on every interaction
- **Intelligent Duplicate Prevention**: Prevents duplicate project entries by matching on project keys rather than full descriptions
  - Extracts keys from "Project Name - Description" format
  - Normalized comparison prevents false duplicates
- **Live Insight Integration**: Fetches pending insights from `/insights/pending` and includes them in composed prompts
- **Full Documentation**: `HOT_MEMORY_EXTENSION.md` with usage guide and API reference

### Changed
- Extended memory architecture to support session-surviving working context
- Hot memory appears in `[WORKING CONTEXT]` section of composed prompts
- Token budget allocates ~400 tokens for working memory by default

---

## [2.2.0] - 2026-03-05

### Added
- FastAPI observability endpoints for runtime inspection:
  - `GET /health` (embedder-loaded status and backend metadata)
  - `GET /memories` (with optional `?type=` filter)
  - `GET /memory/{memory_id}`
  - `GET /insights/pending`
- Regression coverage for strict token budgeting and observability behavior.

### Changed
- Standardized cognitive runtime installs to CPU-only PyTorch wheels in `postinstall.js`:
  - `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu`
- Added `einops>=0.8.0` to cognitive requirements for Nomic embedding compatibility.
- `PromptComposerRequest.hot_memory` is now optional with a safe default payload.

### Fixed
- Enforced strict `max_prompt_tokens` handling in prompt rendering with deterministic eviction order:
  1. Oldest conversation history
  2. Lower-ranked retrieved memories
  3. Insight queue items
  4. Working memory
  5. Temporal state
  6. Agent identity (preserved)
- Retrieval access tracking now persists correctly:
  - increments `access_count`
  - updates `last_accessed`
- Ingestion now performs semantic deduplication before writing new long-term memory:
  - top-1 similarity check (`> 0.85`)
  - reinforces existing memory instead of duplicating
  - increments belief `reinforced_count` where applicable
- Belief conflict resolution thresholds were relaxed to detect shared-entity conflicts with opposing stance/sentiment.

## [2.1.2] - 2026-02-06

### Security
- **CRITICAL**: Fixed path traversal vulnerabilities in multiple files:
  - `memory.js`: `memoryGet()` function
  - `vector_memory_local.js`: `getFullContent()` function
- Added path resolution validation to ensure all file access stays within workspace
- Added allowlist check to restrict access to `MEMORY.md`, `memory/*.md`, and `.hot_memory.md` only
- Blocks attempts like `../../../etc/passwd` or nested traversal patterns

## [2.1.1] - 2026-02-05

### Added
- AGENTS.md template for memory recall instructions
- MEMORY_STRUCTURE.md with directory organization guide
- Test script (`--test` command) for verification
- Troubleshooting table in README
- Better onboarding documentation

## [2.1.0] - 2026-02-04

### Added
- Smart wrapper with automatic fallback (vector -> built-in)
- Zero-configuration philosophy
- Graceful degradation when vector not ready

## [2.0.0] - 2026-02-04

### Added
- 100% local embeddings using `all-MiniLM-L6-v2` via Transformers.js
- No API calls required
- Semantic chunking (by headers, not just lines)
- Cosine similarity scoring
- JSON storage for personal-scale use
- OpenClaw skill manifest
- Programmatic API wrapper (`memory.js`)

### Changed
- Replaced word-frequency embeddings with neural embeddings
- Improved retrieval quality significantly
- Better chunking strategy (semantic boundaries)

## [1.0.0] - 2026-02-04

### Added
- Initial version with word-frequency embeddings
- Simple JSON storage
- Basic CLI interface
- pgvector support (Docker-based)

### Notes
- Word-frequency method works but has limited semantic understanding
- Neural embeddings (v2) recommended for production use
