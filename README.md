# Smart Memory v2 - Cognitive Architecture for OpenClaw

<p>
  <img alt="Node.js" src="https://img.shields.io/badge/Node.js-18%2B-339933?logo=node.js&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-Persistent%20Local%20API-009688?logo=fastapi&logoColor=white">
  <img alt="Embeddings" src="https://img.shields.io/badge/Embeddings-nomic--embed--text--v1.5-blue">
  <img alt="PyTorch" src="https://img.shields.io/badge/PyTorch-CPU--Only-critical?logo=pytorch">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-black">
</p>

> **Not a basic RAG cache.**  
> Smart Memory v2 is a persistent, local cognitive engine for OpenClaw with schema-versioned long-term memory, hot working memory, background cognition, strict token-bounded prompt composition, and a continuously running FastAPI process.

---

## Quick Value (60 seconds)

| You Need | Smart Memory v2 Gives You |
|---|---|
| Continuity across sessions | Typed long-term memory (`episodic`, `semantic`, `belief`, `goal`) |
| Fast local recall | Nomic embeddings + vector search + reranking |
| Stable context quality | Strict prompt token enforcement with deterministic eviction priority |
| Better long-run memory quality | Semantic dedup, reinforcement, consolidation, decay, and conflict resolution |
| Lightweight installs | CPU-only PyTorch standard (no CUDA wheel bloat) |
| Operational visibility | `/health`, `/memories`, `/memory/{id}`, `/insights/pending` |

---

## Why This Exists

Most memory plugins are retrieval wrappers. They do not behave like cognition.  
Smart Memory v2 is designed as a **cognitive pipeline**:

- `Ingestion`: Decide what is memory-worthy.
- `Retrieval`: Find relevant memories with entity and time bias.
- `Working Memory`: Keep a small, high-signal mind state.
- `Background Cognition`: Reflect, consolidate, decay, and resolve conflicts.
- `Prompt Composition`: Assemble bounded, coherent context for the model.

---

## Architecture At A Glance

```mermaid
flowchart LR
  A["OpenClaw Runtime (Node.js)"] --> B["smart-memory/index.js\nAdapter + lifecycle manager"]
  B --> C["FastAPI server.py\nPersistent local API"]
  C --> D["CognitiveMemorySystem"]
  D --> E["ingestion/"]
  D --> F["retrieval/"]
  D --> G["hot_memory/"]
  D --> H["cognition/"]
  D --> I["prompt_engine/"]
  D --> J["storage/ + embeddings/ + entities/"]
```

### Request Flow

```mermaid
flowchart TD
  U["User Message"] --> ING["/ingest\nHeuristic filter -> scoring -> classification -> semantic dedup"]
  U --> RET["/retrieve\nEntity bias -> vector search -> rerank -> access tracking"]
  RET --> COM["/compose\nIdentity + temporal + hot memory + selected LTM + history"]
  BG["/run_background"] --> COG["Reflection + consolidation + decay + belief conflict resolution"]
```

---

## Phase 8 Production Polish

### CPU-Only Standard (mandatory)
- CPU-only PyTorch is required in v2.
- GPU/CUDA PyTorch builds are intentionally unsupported.
- Install explicitly forces CPU wheels:
- `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu`
- `requirements-cognitive.txt` includes `einops>=0.8.0` for Nomic compatibility.

### Strict Token Enforcement
`max_prompt_tokens` is now hard-enforced at render time. If over budget, eviction happens in this exact order:
1. Oldest conversation history
2. Lower-ranked retrieved memories
3. Insight queue items
4. Working memory
5. Temporal state
6. Agent identity (never evicted)

### Access Tracking Fixed
Selected retrieval memories now persist:
- `last_accessed = now()`
- `access_count += 1`

### Semantic Dedup in Ingestion
Before creating a new memory:
- Embed candidate content
- Search top-1 nearest vector
- If cosine similarity `> 0.85`, skip new memory creation and reinforce existing memory:
- update `last_accessed`
- increment `access_count`
- increment `reinforced_count` for belief memories

### Conflict Resolver Thresholds Relaxed
Belief conflicts are now flagged when:
- beliefs share at least one entity
- and stances or sentiment are opposing

### Observability Endpoints
- `GET /health` includes embedder-loaded status and model/backend metadata
- `GET /memories?type=` lists memory objects (optional type filter)
- `GET /memory/{memory_id}` fetches one memory object
- `GET /insights/pending` inspects pending hot-memory insights

### Prompt Compose Input Improvement
`hot_memory` is optional in `PromptComposerRequest`; a safe default object is used when omitted.

---

## Feature Highlights

### Hybrid Node + Python Design
- OpenClaw stays in Node.
- Heavy cognitive operations run in Python.
- `index.js` is a thin adapter that talks HTTP to `localhost:8000`.

### Cold-Start Prevention
- The adapter launches `uvicorn` once and keeps it alive.
- Nomic embeddings and storage connections remain warm between calls.

### REM-Style Background Cognition
Periodic background cycle handles:
- reflection + associative insights
- memory consolidation
- decay + vector pruning
- belief conflict resolution

### Curiosity Triggers
Associative insight generation computes curiosity from emotional intensity and familiarity.
High-curiosity memories can become proactive working questions.

### Schema-First Memory Objects
- JSON documents validated with Pydantic.
- Schema versioning + entity IDs + relations + emotional metadata.


### OpenClaw Native Skill (v2.5)
- New modular skill package: `skills/smart-memory-v25/`
- Active tools:
  - `memory_search`
  - `memory_commit`
  - `memory_insights`
- Built-in reliability:
  - mandatory `/health` gate
  - `.memory_retry_queue.json` for offline commit retries
  - automatic queue flush on successful heartbeat/tool calls
- Lifecycle hooks:
  - session arc checkpoint every 20 turns
  - session-end episodic arc capture
- Passive prompt injection helper emits standardized `[ACTIVE CONTEXT]` blocks for OpenClaw prompts.
---

## Memory Layers

| Layer | Purpose | Example Content |
|---|---|---|
| Agent Identity | Stable behavior anchor | role, mission, style |
| Temporal State | Time continuity | current time, last interaction delta, state |
| Hot Memory | Current cognitive focus | active projects, top-of-mind, working questions |
| Long-Term Memory | Durable history | episodic/semantic/belief/goal objects |
| Insight Queue | Background reflections | confidence-scored insight objects |
| Conversation Context | Immediate grounding | recent turns + current user input |

---

## Repository Layout

```text
.
+- server.py
+- cognitive_memory_system.py
+- prompt_engine/
+- ingestion/
+- retrieval/
+- hot_memory/
+- cognition/
+- storage/
+- embeddings/
+- entities/
+- skills/
   +- smart-memory-v25/
      +- index.js
      +- openclaw-hooks.js
      +- prompt-injection.js
      +- retry-queue.js
+- smart-memory/
   +- index.js
   +- postinstall.js
```

---

## Installation

### Option A: ClawHub

```bash
npx clawhub install smart-memory
```

### Option B: From GitHub

```bash
git clone https://github.com/BluePointDigital/smart-memory.git
cd smart-memory/smart-memory
npm install
```

### What `npm install` Does

`postinstall.js` automatically:
1. Creates `.venv` at repository root.
2. Upgrades `pip`.
3. Installs CPU-only PyTorch wheels (mandatory policy).
4. Installs `requirements-cognitive.txt` (including FastAPI, sentence-transformers, qdrant-client, einops).

Works on both Windows and Unix path conventions.

Do not install generic GPU/CUDA PyTorch wheels for this project; keep CPU-only for consistency and package size.

---

## How To Use

```js
import memory from "smart-memory";

await memory.start();

await memory.ingestMessage({
  user_message: "I started migrating our database today.",
  assistant_message: "Track risks and rollback strategy.",
  timestamp: new Date().toISOString()
});

const retrieval = await memory.retrieveContext({
  user_message: "How is the migration going?",
  conversation_history: "..."
});

const composed = await memory.getPromptContext({
  agent_identity: "You are a persistent cognitive assistant.",
  conversation_history: "...",
  current_user_message: "Continue from where we left off."
  // hot_memory optional
});

await memory.runBackground(true);
await memory.stop();
```

---

## Hot Memory Extension (Optional)

The **Hot Memory Extension** provides persistent working context that survives between sessions and automatically appears in every prompt's `[WORKING CONTEXT]` section.

### What It Adds

| Feature | Description |
|---------|-------------|
| **Active Projects** | Top 5 current projects with auto-detection from conversation |
| **Working Questions** | Open questions being explored (auto-captured from queries) |
| **Top of Mind** | Immediate priorities and notes |
| **Live Insights** | Pending insights from background cognition |
| **Auto-Update** | Detects project mentions and questions automatically |

### Quick Start

```bash
# Initialize with current context
python3 hot_memory_manager.py init

# After conversations, update hot memory
./smem-hook.sh "user message" "assistant response"

# Compose with hot memory auto-included
python3 memory_adapter.py compose -m "What should I work on?"
```

### Files

- `hot_memory_manager.py` - Core persistence and auto-update logic
- `memory_adapter.py` - API wrapper with hot memory integration
- `smem-hook.sh` - Post-conversation shell hook
- `hot_memory_state.json` - Persistent storage (auto-created)

### Duplicate Prevention

The extension includes intelligent duplicate prevention that matches projects by key (e.g., "Tappy.Menu") rather than full description, preventing duplicates when project descriptions evolve.

See `HOT_MEMORY_EXTENSION.md` for full documentation.

---

## API Surface

### JavaScript Adapter Methods

| Method | Purpose |
|---|---|
| `init()` / `start()` | Ensure API process is running and healthy |
| `ingestMessage(interaction)` | Send interaction to ingestion pipeline |
| `retrieveContext({ user_message, conversation_history })` | Retrieve ranked memory context |
| `getPromptContext(request)` | Compose final bounded prompt context |
| `runBackground(scheduled)` | Trigger cognition cycle |
| `stop()` | Stop managed Python server process |

### FastAPI Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | `GET` | Basic service status |
| `/health` | `GET` | Health + embedder loaded metadata |
| `/ingest` | `POST` | Ingest incoming interaction |
| `/retrieve` | `POST` | Retrieve relevant long-term memories |
| `/compose` | `POST` | Compose prompt context payload |
| `/run_background` | `POST` | Execute background cognition cycle |
| `/memories` | `GET` | List memories (`?type=` optional) |
| `/memory/{memory_id}` | `GET` | Fetch one memory by ID |
| `/insights/pending` | `GET` | View pending hot-memory insights |

---

## Security and Privacy

- Memory data is designed for local operation.
- `.gitignore` excludes runtime memory stores, virtualenvs, caches, and `node_modules`.
- Review ignored paths before publishing any fork.

---

## Requirements

- Node.js `>=18`
- Python `>=3.11`
- Local disk for model cache + memory storage

---

## License

MIT
