---
name: smart-memory
description: A persistent, local cognitive memory system for OpenClaw agents. Features Nomic embeddings, hot working memory, background cognition (REM-style consolidation), and a continuously running FastAPI brain.
---

# Smart Memory v2 - Cognitive Memory for OpenClaw

> **Not a basic RAG cache.** A full cognitive pipeline: ingestion → retrieval → working memory → background cognition → prompt composition.

## What It Is

Smart Memory v2 is a **persistent, local cognitive engine** for OpenClaw agents. It runs as a continuously-active FastAPI server that keeps embedding models and database connections hot, providing fast, high-quality memory retrieval with actual cognition—not just vector search.

## Key Features

| Feature | What You Get |
|---------|-------------|
| **Typed Memory** | Episodic, semantic, belief, and goal memories with schema versioning |
| **Nomic Embeddings** | Local `nomic-embed-text-v1.5` (768-dim, high quality) |
| **Hot Working Memory** | Small, high-signal "mind state" for current cognitive focus |
| **Background Cognition** | REM-style consolidation, decay, reflection, and belief conflict resolution |
| **Entity-Aware Retrieval** | Vector search + entity biasing + reranking |
| **Token-Bounded Prompts** | Strict context budgeting with deterministic eviction |
| **CPU-First** | PyTorch CPU-only by default (~200MB vs ~900MB), no CUDA required |

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  OpenClaw Agent │────▶│  FastAPI Server  │────▶│ CognitiveMemory │
│   (Node.js)     │     │   (Port 8000)    │     │    System       │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
        ┌──────────┬──────────┬───────────┬───────────────┼───────────┐
        ▼          ▼          ▼           ▼               ▼           ▼
   ┌────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐ ┌────────────┐ ┌────────┐
   │Ingest  │ │Retrieve│ │Hot Mem  │ │Cognition │ │Prompt Eng. │ │Storage │
   │Pipeline│ │Pipeline│ │Manager  │ │ Engine   │ │  Composer  │ │(Qdrant)│
   └────────┘ └────────┘ └─────────┘ └──────────┘ └────────────┘ └────────┘
```

## Installation

### Prerequisites
- Python 3.11+
- Node.js 18+ (for OpenClaw integration)

### Step 1: Clone and Setup
```bash
git clone https://github.com/BluePointDigital/smart-memory.git
cd smart-memory

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements-cognitive-cpu.txt
```

### Step 2: Start the Server
```bash
# Development (foreground)
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload

# Production (background)
nohup python -m uvicorn server:app --host 127.0.0.1 --port 8000 > server.log 2>&1 &
```

### Step 3: Verify
```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

## OpenClaw Integration

Add to your `AGENTS.md` to auto-start on session init:

```bash
# Start cognitive memory server if not running
curl -s http://127.0.0.1:8000/health > /dev/null 2>&1 || (
  cd ~/workspace/smart-memory &&
  nohup bash -c '. .venv/bin/activate && python -m uvicorn server:app --host 127.0.0.1 --port 8000' > /tmp/smart-memory-server.log 2>&1 &
)
```

## Quick Start

### 1. Ingest a Conversation
```bash
curl -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "I started the database migration today.",
    "assistant_message": "Good. We should track rollback strategy.",
    "timestamp": "2026-03-05T11:00:00Z"
  }'
```

### 2. Retrieve Context
```bash
curl -X POST http://127.0.0.1:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "How is the migration going?",
    "conversation_history": ""
  }'
```

Returns ranked memories with vector scores and composite relevance scores.

### 3. Compose Prompt Context
```bash
curl -X POST http://127.0.0.1:8000/compose \
  -H "Content-Type: application/json" \
  -d '{
    "identity_context": "You are Nyx, a persistent cognitive assistant.",
    "temporal_context": {"current_time": "2026-03-05T11:30:00Z", "timezone": "America/New_York"},
    "conversation_history": "User: Hey Nyx. Assistant: Hey James.",
    "current_message": "What were we working on?"
  }'
```

### 4. Trigger Background Cognition
```bash
curl -X POST http://127.0.0.1:8000/run_background \
  -H "Content-Type: application/json" \
  -d '{"scheduled": true}'
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service status |
| `/health` | GET | Health check |
| `/ingest` | POST | Ingest an interaction |
| `/retrieve` | POST | Retrieve relevant memories |
| `/compose` | POST | Compose bounded prompt context |
| `/run_background` | POST | Run background cognition cycle |

## Memory Types

| Type | Purpose | Example |
|------|---------|---------|
| **episodic** | Events with participants | "User started database migration" |
| **semantic** | Facts and concepts | "Database migrations should have rollback plans" |
| **belief** | Learned preferences/patterns | "User prefers local tools over cloud APIs" |
| **goal** | Active objectives | "Complete migration by Friday" |

## Background Cognition

The `/run_background` endpoint performs REM-style processing:

1. **Reflection** - Generate insights from recent memories
2. **Consolidation** - Merge redundant memories, reinforce important ones
3. **Decay** - Reduce importance of old/unaccessed memories
4. **Conflict Resolution** - Detect and flag contradictory beliefs

Run this periodically (e.g., hourly) to keep memory quality high:

```bash
# Cron example (every hour)
0 * * * * curl -X POST http://127.0.0.1:8000/run_background -d '{"scheduled":true}'
```

## Prompt Composition

The `/compose` endpoint assembles context in priority order:

1. **Identity** (configurable budget)
2. **Temporal State** (time, last interaction)
3. **Hot Memory** (active projects, working questions)
4. **Retrieved LTM** (ranked memories by relevance)
5. **Conversation History** (recent turns)

Eviction is deterministic: lower importance + older + less accessed = evicted first.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORY_DATA_DIR` | `./data` | Storage directory for Qdrant |
| `MEMORY_LOG_LEVEL` | `INFO` | Logging level |

### Token Budgets (in compose request)

```json
{
  "max_context_tokens": 4000,
  "identity_budget_tokens": 500,
  "temporal_budget_tokens": 200,
  "hot_memory_budget_tokens": 800,
  "ltm_budget_tokens": 1500,
  "conversation_budget_tokens": 1000
}
```

## Performance

| Metric | CPU | GPU (if available) |
|--------|-----|-------------------|
| Cold start | ~3s | ~3s |
| Embedding latency | ~35ms | ~25ms |
| Retrieval latency | ~50ms | ~40ms |
| Memory usage | ~400MB | ~1.2GB |

## Requirements Files

- `requirements-cognitive.txt` - GPU-enabled PyTorch (full)
- `requirements-cognitive-cpu.txt` - CPU-only PyTorch (recommended)

## Development

### Run Tests
```bash
cd tests
pytest -v
```

### Project Structure
```
.
├── server.py                    # FastAPI entry point
├── cognitive_memory_system.py   # Main orchestrator
├── ingestion/                   # Ingestion pipeline
├── retrieval/                   # Retrieval pipeline
├── hot_memory/                  # Working memory manager
├── cognition/                   # Background processing
├── prompt_engine/               # Prompt composition
├── storage/                     # Qdrant vector store
├── embeddings/                  # Nomic embedder
└── entities/                    # Entity extraction
```

## Troubleshooting

**Server won't start:**
```bash
# Check port 8000 is free
lsof -i :8000

# Check logs
tail -f /tmp/smart-memory-server.log
```

**Out of memory:**
- Use CPU-only requirements: `pip install -r requirements-cognitive-cpu.txt`
- Reduce batch sizes in `embeddings/embedder.py`

**Poor retrieval quality:**
- Run background cognition: `/run_background`
- Check entity extraction is working (see logs)
- Verify memories are being ingested (check storage)

## License

MIT
