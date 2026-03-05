---
name: smart-memory
description: Persistent cognitive memory with search, commit, and insights. Local FastAPI brain at :8000.
metadata: {"clawdbot":{"emoji":":brain:","requires":{"bins":["curl"]},"install":[]}}
---

# Smart Memory

Local persistent memory for AI agents. Neural embeddings, background cognition, and durable long-term storage.

**Prerequisites**
- Smart Memory server running on `http://127.0.0.1:8000`
- Health check: `curl -s http://127.0.0.1:8000/health`

---

## memory_search

Find relevant memories from long-term storage.

```yaml
memory_search:
  query: "What did we decide about PyTorch?"
  type: all        # all | semantic | episodic | belief | goal
  limit: 5
  min_relevance: 0.6
```

**Output**: Ranked memories with relevance scores.

**Raw API example**:
```bash
curl -s -X POST http://127.0.0.1:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"user_message":"What did we decide about PyTorch?","conversation_history":""}'
```

---

## memory_commit

Persist a thought, fact, or decision to memory.

```yaml
memory_commit:
  content: "We settled on CPU-only PyTorch for all installs to avoid CUDA bloat."
  type: semantic    # semantic | episodic | belief | goal
  importance: 8     # 1-10
  tags: ["pytorch", "infrastructure", "decision"]
```

**Auto-tagging**: If `tags` is omitted, fallback heuristics add tags like `working_question` and `decision`.

**Retry behavior**: Failed commits are queued in `.memory_retry_queue.json` and flushed automatically on the next healthy call.

---

## memory_insights

View pending insights from background cognition.

```yaml
memory_insights:
  limit: 10
  status: pending   # optional hint; backend endpoint currently returns pending insights
```

**Output**: Pattern matches, associative connections, and reflection prompts.

**Raw API example**:
```bash
curl -s http://127.0.0.1:8000/insights/pending
```

---

## Passive Context Injection

Smart Memory can auto-inject `[ACTIVE CONTEXT]` before responses via the v2.5 hook middleware (`inject_active_context` / `beforeModelResponse`).

Include this in your system prompt:
> "If pending insights appear in your context that relate to the current conversation, surface them naturally."

---

## Common Queries

**Recent decisions on Tappy.Menu:**
`memory_search: {query: "Tappy.Menu activation flow decision", type: semantic}`

**Session continuity:**
`memory_search: {query: "last session what we were building", type: episodic}`

**Capture a pivot:**
`memory_commit: {content: "Pivoted from X to Y because Z", type: episodic, importance: 9}`

---

## Notes

- Server start (example): `cd ~/.openclaw/workspace/smart-memory && . .venv/bin/activate && uvicorn server:app --host 127.0.0.1 --port 8000`
- Background cognition runs automatically via cron/heartbeat
- Hot memory may be persisted in either:
  - `~/.openclaw/workspace/smart-memory/hot_memory_state.json` (extension manager)
  - `data/hot_memory/hot_memory.json` (core hot-memory store)
