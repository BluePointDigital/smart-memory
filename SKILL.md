---
name: smart-memory
description: Persistent local cognitive memory for OpenClaw via a Node adapter and FastAPI engine.
---

# Smart Memory v2 Skill

Smart Memory v2 is a persistent cognitive memory runtime, not a legacy vector-memory CLI.

Core runtime:
- Node adapter: `smart-memory/index.js`
- Local API: `server.py` (FastAPI)
- Orchestrator: `cognitive_memory_system.py`

## Core Capabilities

- Structured long-term memory (`episodic`, `semantic`, `belief`, `goal`)
- Entity-aware retrieval and reranking
- Hot working memory
- Background cognition (reflection, consolidation, decay, conflict resolution)
- Strict token-bounded prompt composition
- Observability endpoints (`/health`, `/memories`, `/memory/{id}`, `/insights/pending`)

## Native OpenClaw Integration (v2.5)

Use the native OpenClaw skill package:
- `skills/smart-memory-v25/index.js`
- Optional hook helper: `skills/smart-memory-v25/openclaw-hooks.js`
- Skill descriptor: `skills/smart-memory-v25/SKILL.md`

Primary exports:
- `createSmartMemorySkill(options)`
- `createOpenClawHooks({ skill, agentIdentity, summarizeWithLLM })`

### Tool Interface (for agent tool use)

1. `memory_search`
- Purpose: query long-term memory.
- Input:
  - `query` (string, required)
  - `type` (`all|semantic|episodic|belief|goal`, default `all`)
  - `limit` (number, default `5`)
  - `min_relevance` (number, default `0.6`)
- Behavior: checks `/health` first, then retrieves via `/retrieve` and returns formatted memory results.

2. `memory_commit`
- Purpose: explicitly persist important facts/decisions/beliefs/goals.
- Input:
  - `content` (string, required)
  - `type` (`semantic|episodic|belief|goal`, required)
  - `importance` (1-10, default `5`)
  - `tags` (string array, optional)
- Behavior:
  - checks `/health` first
  - auto-tags if missing (`working_question`, `decision` heuristics)
  - commits are serialized (sequential) to protect local CPU embedding throughput
  - if server is unreachable, payload is queued to `.memory_retry_queue.json`
  - unreachable response is explicit:
    - `Memory commit failed - server unreachable. Queued for retry.`

3. `memory_insights`
- Purpose: surface pending background insights.
- Input:
  - `limit` (number, default `10`)
- Behavior: checks `/health` first, calls `/insights/pending`, returns formatted insight list.

### Reliability Guarantees

- Mandatory health gate before each tool call (`GET /health`).
- Retry queue flushes automatically on healthy tool calls and heartbeat.
- Heartbeat supports automatic retry recovery and background maintenance.

### Session Arc Lifecycle Hooks

The v2.5 skill supports episodic session arc capture:
- checkpoint capture every 20 turns
- session-end capture during teardown/reset

Flow:
1. Extract recent conversation turns (up to 20).
2. Run summarization with prompt:
   - `Summarize this session arc: What was the goal? What approaches were tried? What decisions were made? What remains open?`
3. Persist summary through internal `memory_commit` as:
   - `type: "episodic"`
   - `tags: ["session_arc", "YYYY-MM-DD"]`

### Passive Context Injection

Use `inject_active_context` (or `createOpenClawHooks().beforeModelResponse`) before response generation.

This adds the standardized block:

```text
[ACTIVE CONTEXT]
Status: {status}
Active Projects: {active_projects}
Working Questions: {working_questions}
Top of Mind: {top_of_mind}

Pending Insights:
- {insight_1}
- {insight_2}
[/ACTIVE CONTEXT]
```

Add this guidance line to your agent base prompt:

`If pending insights appear in your context that relate to the current conversation, surface them naturally to the user. Do not force it - but if there is a genuine connection, seamlessly bring it up.`

### Minimal OpenClaw Wiring Example

```js
const {
  createSmartMemorySkill,
  createOpenClawHooks,
} = require("./skills/smart-memory-v25");

const memory = createSmartMemorySkill({
  baseUrl: "http://127.0.0.1:8000",
  summarizeSessionArc: async ({ prompt, conversationText }) => {
    return openclaw.llm.complete({ system: prompt, user: conversationText });
  },
});

const hooks = createOpenClawHooks({
  skill: memory.skill,
  agentIdentity: "OpenClaw Agent",
  summarizeWithLLM: async ({ prompt, conversationText }) => {
    return openclaw.llm.complete({ system: prompt, user: conversationText });
  },
});

// Register memory.tools as callable tools:
// - memory_search
// - memory_commit
// - memory_insights
// and call hooks.beforeModelResponse / hooks.onTurn / hooks.onSessionEnd at lifecycle points.
```

## Node Adapter Methods (Base Adapter)

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

## Install (CPU-Only Required)

For Docker, WSL, and laptops without NVIDIA GPUs, use CPU-only PyTorch.

```bash
# from repository root
cd smart-memory

# Create Python venv
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install CPU-only PyTorch FIRST
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Then install remaining dependencies
pip install -r requirements-cognitive.txt

# Finally, install Node dependencies
npm install
```

## PyTorch Policy

- Smart Memory v2 supports CPU-only PyTorch only.
- Do not install GPU/CUDA PyTorch builds for this project.
- Use the bundled installer flow (`npm install` -> `postinstall.js`) so CPU wheels are always used.

## Deprecated

Legacy vector-memory CLI artifacts (`smart_memory.js`, `vector_memory_local.js`, `focus_agent.js`) are removed in v2.
