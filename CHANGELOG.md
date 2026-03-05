# Changelog

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
