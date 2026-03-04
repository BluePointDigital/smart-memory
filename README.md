# Smart Memory v2 - Cognitive Architecture for OpenClaw

Smart Memory v2 is not a standard RAG memory plugin. It is a persistent, sovereign cognitive engine designed for OpenClaw agents.

It combines:
- schema-versioned JSON memory objects (episodic, semantic, belief, goal)
- local Nomic vector embeddings (`nomic-embed-text-v1.5`)
- a continuously running FastAPI "brain"
- a Node.js adapter that makes the Python engine feel native inside OpenClaw

## Overview

Traditional memory plugins do one-shot retrieval. Smart Memory v2 operates as a cognitive system:
- Ingests interactions with heuristic gating and importance scoring
- Persists structured long-term memory objects
- Retrieves with entity bias + reranking + time-aware filtering
- Maintains hot working memory
- Runs background cognition (reflection, consolidation, decay, belief conflict resolution)
- Composes bounded prompts for the model with continuity and graceful degradation

## Key Features

### Hybrid Architecture
Node.js OpenClaw adapter talks to a persistent local Python FastAPI server.

`OpenClaw (Node)` -> `smart-memory/index.js` -> `FastAPI server.py` -> `CognitiveMemorySystem`

### REM Sleep and Background Cognition
The system runs periodic background cognition cycles:
- reflection and associative insight generation
- memory consolidation
- decay and vector pruning
- belief conflict resolution

This keeps memory coherent over time instead of accumulating raw noise.

### Curiosity Triggers
Associative cognition includes a curiosity score driven by emotional intensity.

When a memory has high emotional signal, the system can generate proactive working questions such as:
- "User was very frustrated by X, did they resolve it?"

### Cold-Start Prevention
The FastAPI server stays alive, so the Nomic embedder remains warm in memory/VRAM.

Result: no model reload on every call and warm retrieval latency in the ~50ms class on local setups (hardware-dependent).

## Architecture Snapshot

```text
OpenClaw Runtime (Node.js)
  -> smart-memory/index.js (adapter + lifecycle + background timer)
  -> FastAPI server.py (persistent local API)
      -> ingestion/
      -> retrieval/
      -> hot_memory/
      -> cognition/
      -> prompt_engine/
      -> storage/
      -> embeddings/
```

## Installation

### From ClawHub
```bash
npx clawhub install smart-memory
```

### Local / GitHub
```bash
git clone https://github.com/BluePointDigital/smart-memory.git
cd smart-memory/smart-memory
npm install
```

`npm install` runs `postinstall.js`, which automatically:
1. creates Python virtual environment at `../.venv`
2. upgrades pip
3. installs `../requirements-cognitive.txt`
4. prepares FastAPI/uvicorn + cognitive dependencies

This works on Windows and Unix path conventions.

## Usage

### Adapter lifecycle (automatic)
`smart-memory/index.js` manages the Python server lifecycle for you:
- starts uvicorn when needed
- polls `/health` before serving requests
- sends periodic `POST /run_background` (hourly by default)
- kills the child Python process on `SIGINT`/`SIGTERM`/process exit

### OpenClaw-facing methods
The adapter exposes async wrappers:
- `init()` / `start()`
- `ingestMessage(interaction)` -> `POST /ingest`
- `retrieveContext({ user_message, conversation_history })` -> `POST /retrieve`
- `getPromptContext(promptComposerRequest)` -> `POST /compose`
- `runBackground(scheduled)` -> `POST /run_background`
- `stop()`

### FastAPI endpoints
- `GET /health`
- `POST /ingest`
- `POST /retrieve`
- `POST /compose`
- `POST /run_background`

## Development Notes

- Python cognitive engine lives at repository root (`server.py`, `cognitive_memory_system.py`, and phase modules).
- Node package adapter lives in `smart-memory/`.
- Embedding backend is pluggable; default prefers local Nomic and falls back safely when unavailable.

## Requirements

- Node.js 18+
- Python 3.11+
- Local disk space for model cache and memory store

## License

MIT
