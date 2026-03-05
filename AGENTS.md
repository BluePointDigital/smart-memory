## Memory Recall - Smart Memory v2

Before answering questions about prior work, preferences, decisions, or project history:

1. Retrieve context from the cognitive engine first.
   - Use `POST /retrieve` with the current user message.
2. If needed, inspect long-term memory directly.
   - Use `GET /memories` or `GET /memory/{memory_id}`.
3. If confidence is low after retrieval, say so explicitly.
   - Example: "I checked memory context but I do not see a reliable prior note for that topic."

### Retrieval Guidance

Always retrieve before:
- Summarizing prior discussions
- Referencing earlier decisions
- Recalling user preferences
- Continuing prior project threads

Use conceptual, natural-language queries rather than isolated keywords.

### Runtime Checks

- API health: `GET /health`
- Pending insights: `GET /insights/pending`

### Current Architecture (v2)

- Node adapter: `smart-memory/index.js`
- Persistent local API: `server.py`
- Long-term memory store: `data/memory_store/`
- Hot memory store: `data/hot_memory/hot_memory.json`

### Deprecated

Legacy Vector Memory CLI commands (`vector-memory/smart_memory.js`, `vector_memory_local.js`) are removed in v2.
