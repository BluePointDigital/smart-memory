## Memory Recall - Smart Memory v3.1

Before answering questions about prior work, preferences, decisions, or project history:

1. Retrieve context from the cognitive engine first.
   - Use `POST /retrieve` with the current user message.
2. If needed, inspect transcript-backed memory directly.
   - Use `GET /memories`, `GET /memory/{memory_id}`, `GET /memory/{memory_id}/evidence`, or the revision-history endpoints.
3. If confidence is low after retrieval, say so explicitly.
   - Example: `I checked memory context but I do not see a reliable prior note for that topic.`

### Retrieval Guidance

Always retrieve before:
- summarizing prior discussions
- referencing earlier decisions
- recalling user preferences
- continuing prior project threads

Use conceptual, natural-language queries rather than isolated keywords.

### Runtime Checks

- API health: `GET /health`
- Pending insights: `GET /insights/pending`
- Core lane: `GET /lanes/core`
- Working lane: `GET /lanes/working`
- Transcript session: `GET /transcripts/{session_id}`

### Current Architecture (v3.1)

- Node adapter: `smart-memory/index.js`
- Persistent local API: `server.py`
- System facade: `cognitive_memory_system.py`
- Canonical transcript + memory store: `data/memory_store/v3_memory.sqlite`
- Hot-memory compatibility projection: `data/hot_memory/hot_memory.json`

### Truth Hierarchy

1. `transcript_messages` are canonical truth
2. `memories` are derived revision-aware state
3. core/working/retrieved lanes are prompt-time context views

### Inspection Endpoints

- `GET /memory/{memory_id}/evidence`
- `GET /memory/{memory_id}/history`
- `GET /memory/{memory_id}/active`
- `GET /memory/{memory_id}/chain`
- `GET /transcript/message/{message_id}`
- `POST /rebuild`
- `POST /rebuild/{session_id}`
- `GET /eval/case/{case_id}`
- `GET /eval/suite/{suite_name}`

### Deprecated in the normal runtime path

Legacy vector-memory CLI commands remain deprecated. JSON stores and migration helpers remain offline utilities only; the active runtime path is transcript-first and SQLite-only.
