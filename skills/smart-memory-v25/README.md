# Smart Memory v2.5 OpenClaw Skill

This folder contains a native OpenClaw skill wrapper for the local FastAPI cognitive engine (`http://127.0.0.1:8000`).

## Files

- `index.js` - Main skill class + OpenClaw-friendly factory (`createSmartMemorySkill`)
- `openclaw-hooks.js` - Hook wiring for turns, teardown, and pre-response context injection
- `http-client.js` - API client + health checks
- `retry-queue.js` - `.memory_retry_queue.json` persistence and flush logic
- `tagging.js` - Extensible auto-tag heuristics
- `session-arc.js` - 20-turn checkpoint + session-end episodic capture hooks
- `prompt-injection.js` - Passive context middleware (`[ACTIVE CONTEXT]` block)
- `formatters.js` - LLM-readable formatter output for tools
- `constants.js` - Shared constants
- `types.js` - JSDoc type definitions

## Quick Start

```js
const { createSmartMemorySkill } = require("./skills/smart-memory-v25");

const smartMemory = createSmartMemorySkill({
  baseUrl: "http://127.0.0.1:8000",
  summarizeSessionArc: async ({ prompt, conversationText }) => {
    // Replace this with OpenClaw's internal completion/summarization call.
    return await openclaw.llm.complete({
      system: prompt,
      user: conversationText,
    });
  },
});

await smartMemory.start();

const searchText = await smartMemory.memory_search({ query: "database migration" });
const commitText = await smartMemory.memory_commit({
  content: "We settled on CPU-only PyTorch for all installs.",
  type: "semantic",
});
```

## Required Prompt Guidance

Add this exact line to your base system prompt:

> If pending insights appear in your context that relate to the current conversation, surface them naturally to the user. Do not force it - but if there is a genuine connection, seamlessly bring it up.

## Notes

- Every tool call starts with `GET /health`.
- Failed commits are queued in `.memory_retry_queue.json`.
- Queue flushes automatically on successful tool calls and heartbeat.
