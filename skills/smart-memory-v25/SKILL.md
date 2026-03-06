---
name: smart-memory
description: "Persistent cognitive memory via local FastAPI (127.0.0.1:8000). Semantic search, memory commit with retry queue, and background insight retrieval. Use when recalling past decisions, persisting important info, or checking pattern insights."
metadata:
  {"openclaw":{"emoji":"🧠","requires":{"bins":["curl"]}}}
---

# Smart Memory

Local neural memory system at http://127.0.0.1:8000. Provides long-term storage with embeddings, semantic search, episodic session capture, and background cognition.

## When to Use

✅ **USE when:**
- Recalling what was decided in past sessions
- Looking for relevant context on current topics
- Persisting important decisions or pivots
- Checking for pattern insights from background processing

❌ **DON'T use when:**
- Recent conversation context is sufficient (use context window)
- Server is unreachable (curl health check fails)

## Prerequisites

```bash
# Check server health
curl -s http://127.0.0.1:8000/health | jq .

# Start server if needed
cd ~/.openclaw/workspace/smart-memory
. .venv/bin/activate
uvicorn server:app --host 127.0.0.1 --port 8000 &
```

## OpenClaw Configuration

**Important:** OpenClaw has built-in `memory_search` and `memory_get` tools that search MEMORY.md files using FTS. To use this skill's semantic memory tools, you must disable the built-in ones:

```bash
# Disable built-in memory tools so skill tools take precedence
openclaw config set tools.deny '["memory_search", "memory_get"]'
openclaw gateway restart
```

After restart, the skill's `memory_search` will use Nomic embeddings for semantic retrieval instead of FTS file search.

## Search Memories

Find relevant memories via semantic + reranking search.

```bash
# Basic search
curl -s -X POST http://127.0.0.1:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"user_message":"What did we decide about PyTorch?","limit":5}' | jq .

# Filter by memory type
curl -s -X POST http://127.0.0.1:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"user_message":"database migration","type":"episodic","limit":3}' | jq .

# Higher relevance threshold
curl -s -X POST http://127.0.0.1:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"user_message":"Tappy.Menu activation flow","min_relevance":0.7}' | jq .
```

## Commit Memory

Persist a thought, fact, or decision.

```bash
# Semantic (factual knowledge)
curl -s -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "user_message":"We settled on CPU-only PyTorch for all installs.",
    "assistant_message":"Confirmed - avoids CUDA wheel bloat and keeps installs consistent.",
    "timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
  }' | jq .

# Episodic (session narrative)
curl -s -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "user_message":"Successfully deployed v2.5 skill architecture after 3 iterations.",
    "assistant_message":"Session captured with retry queue and hot memory integration.",
    "timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
  }' | jq .

# Goal (tracked objective)
curl -s -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "user_message":"GOAL: Complete Content Foundry MVP by end of March.",
    "assistant_message":"Tracking: lead capture → content gen → campaign workflows.",
    "timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
  }' | jq .
```

## View Insights

Check for background cognition patterns.

```bash
# Pending insights
curl -s http://127.0.0.1:8000/insights/pending | jq .

# All memories
curl -s "http://127.0.0.1:8000/memories?limit=20" | jq '.[] | {id, type, content: .content[:50]}'

# Memory by ID
curl -s http://127.0.0.1:8000/memory/<id> | jq .
```

## Work with Hot Memory

Check and update working context.

```bash
# View current hot memory
python3 ~/.openclaw/workspace/smart-memory/hot_memory_manager.py get

# Compose with hot memory context
python3 ~/.openclaw/workspace/smart-memory/memory_adapter.py compose -m "What should I prioritize?"

# Auto-update from conversation
~/.openclaw/workspace/smart-memory/smem-hook.sh "user message" "assistant response"

# Re-initialize hot memory
python3 ~/.openclaw/workspace/smart-memory/hot_memory_manager.py init
```

## Common Patterns

### Find recent decisions on a project
```bash
curl -s -X POST http://127.0.0.1:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"user_message":"Tappy.Menu activation flow decision recent"}' | jq '.memories[] | {score, content}'
```

### Session continuity check
```bash
curl -s -X POST http://127.0.0.1:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"user_message":"what we were building last session","type":"episodic"}' | jq '.memories[0].content'
```

### Capture mid-session pivot
```bash
CONTENT="Pivot: Moving from X approach to Y because of Z constraint"
curl -s -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  -d "{
    \"user_message\":\"$CONTENT\",
    \"assistant_message\":\"Important pivot captured.\",
    \"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
  }"
```

### Trigger background cognition
```bash
curl -s -X POST http://127.0.0.1:8000/run_background -d '{"scheduled":false}' | jq .
```

## Notes

- **Retry queue**: Failed commits queue to `.memory_retry_queue.json` and flush automatically
- **Background cognition**: Runs periodically to consolidate, decay, and generate insights
- **Hot memory**: Survives sessions; auto-detects projects and questions from conversation
- **Session arcs**: Captured automatically on checkpoints and session end
- **Prompt injection**: `[ACTIVE CONTEXT]` block auto-includes hot memory via `/compose`

## System Prompt Addition

Add this to agent identity:
> "If pending insights appear in your context that relate to the current conversation, surface them naturally to the user."
