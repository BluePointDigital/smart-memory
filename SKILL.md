---
name: smart-memory
description: Persistent, local cognitive memory for OpenClaw via a Node adapter and FastAPI engine.
---

# Smart Memory v2 Skill

Smart Memory v2 is not a legacy Vector Memory CLI. It is a persistent cognitive memory runtime:

- Node adapter: `smart-memory/index.js`
- Local API: `server.py` (FastAPI)
- Orchestrator: `cognitive_memory_system.py`

## Core Capabilities

- Structured long-term memory (`episodic`, `semantic`, `belief`, `goal`)
- Entity-aware retrieval + reranking
- Hot working memory
- Background cognition (reflection, consolidation, decay, conflict resolution)
- Strict token-bounded prompt composition
- Observability endpoints (`/health`, `/memories`, `/memory/{id}`, `/insights/pending`)

## Node Adapter Methods

- `start()` / `init()`
- `ingestMessage(interaction)`
- `retrieveContext({ user_message, conversation_history })`
- `getPromptContext(promptComposerRequest)`
- `runBackground(scheduled)`
- `stop()`

## API Endpoints

- `GET /health`
- `POST /ingest`
- `POST /retrieve`
- `POST /compose`
- `POST /run_background`
- `GET /memories`
- `GET /memory/{memory_id}`
- `GET /insights/pending`

## Install (CPU-Only Recommended)

For Docker, WSL, and laptops without NVIDIA GPUs, use the CPU-only version (~200MB vs ~2GB):

```bash
# from repository root
cd smart-memory

# Create Python venv
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install CPU-only PyTorch FIRST (before sentence-transformers)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Then install remaining dependencies
pip install -r requirements-cognitive.txt

# Finally, install Node dependencies
npm install
```

**Why CPU-only?**
- Smaller: ~200MB vs ~2GB
- No CUDA drivers needed
- Performance: ~50ms ingestion vs ~40ms on GPU (acceptable trade-off)
- Perfect for local development, Docker, and edge deployment

**GPU Option:** If you have an NVIDIA GPU and want maximum speed, install the full `requirements-cognitive.txt` without the CPU torch line.

## PyTorch Policy

- Smart Memory v2 supports **CPU-only PyTorch only**.
- Do not install GPU/CUDA PyTorch builds for this project.
- Use the bundled installer flow (`npm install` -> `postinstall.js`) so the CPU index URL is always applied.

## Usage Example

```js
import memory from "smart-memory";

await memory.start();

await memory.ingestMessage({
  user_message: "User started a migration project.",
  assistant_message: "Captured as active project context.",
  timestamp: new Date().toISOString()
});

const retrieval = await memory.retrieveContext({
  user_message: "How is the migration going?",
  conversation_history: "..."
});

await memory.stop();
```

## Deprecated

Legacy Vector Memory CLI artifacts (`smart_memory.js`, `vector_memory_local.js`, `focus_agent.js`) are removed in v2.
