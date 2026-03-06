## Memory Recall - Smart Memory v3

Before answering questions about prior work, preferences, decisions, or project history:

1. Retrieve context from the cognitive engine first.
   - Use `POST /retrieve` with the current user message.
2. If needed, inspect long-term memory directly.
   - Use `GET /memories`, `GET /memory/{memory_id}`, or the revision-history endpoints.
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

### Current Architecture (v3)

- Node adapter: `smart-memory/index.js`
- Persistent local API: `server.py`
- System facade: `cognitive_memory_system.py`
- Canonical long-term memory store: `data/memory_store/v3_memory.sqlite`
- Hot-memory compatibility store: `data/hot_memory/hot_memory.json`

### Inspection Endpoints

- `GET /memory/{memory_id}/history`
- `GET /memory/{memory_id}/active`
- `GET /memory/{memory_id}/chain`
- `GET /eval/case/{case_id}`
- `GET /eval/suite/{suite_name}`

### Deprecated

Legacy vector-memory CLI commands remain deprecated. JSON stores remain for migration and export, but SQLite is the canonical backend in v3.
