# Agent Framework Integration Guide

How to wire Smart Memory v3.1 into different agent frameworks for deterministic session priming, transcript-first persistence, and rebuildable continuity.

## Golden rule

Query memory before the agent speaks, and treat transcript append as the durable write.

The recommended startup pattern is the same across frameworks:

1. `GET /health`
2. `POST /compose`
3. hold the returned prompt and traces in agent state
4. answer the user
5. `POST /ingest` or `POST /transcripts/message` after meaningful turns

## OpenClaw

For OpenClaw, combine:

- the root `AGENTS.md` retrieval guidance
- the `skills/smart-memory-openclaw/` package
- the session-start helpers in `examples/session-start/`

Practical setup:

1. start the Smart Memory API
2. call `/compose` during session initialization
3. keep the returned prompt in state before the first greeting
4. use the skill tools for search, commit, and pending insights
5. use transcript and evidence endpoints when debugging continuity

## Custom Python agents

```python
import requests

BASE_URL = "http://127.0.0.1:8000"

class CognitiveAgent:
    def __init__(self, identity: str):
        self.identity = identity
        self.context = None

    def wake(self):
        requests.get(f"{BASE_URL}/health", timeout=5).raise_for_status()
        response = requests.post(
            f"{BASE_URL}/compose",
            json={
                "agent_identity": self.identity,
                "current_user_message": "Session start - what matters right now?",
                "conversation_history": "",
                "max_prompt_tokens": 512,
            },
            timeout=10,
        )
        response.raise_for_status()
        self.context = response.json()
        return self

    def ingest(self, user_message: str, assistant_message: str):
        requests.post(
            f"{BASE_URL}/ingest",
            json={
                "user_message": user_message,
                "assistant_message": assistant_message,
            },
            timeout=10,
        ).raise_for_status()
```

## Node.js agents

```javascript
import memory from 'smart-memory';

await memory.start();

const context = await memory.getPromptContext({
  agent_identity: 'MyAgent',
  current_user_message: 'Session start - summarize active context.',
  conversation_history: '',
  max_prompt_tokens: 512,
});

const retrieval = await memory.retrieveContext({
  user_message: 'What did we decide about deployment?',
  conversation_history: '',
});
```

## Retrieval guidance

Use `/retrieve` before:

- summarizing prior discussions
- referencing earlier decisions
- recalling user preferences
- continuing prior project threads

Prefer natural-language queries over keyword fragments.

## Explicit inspection

For transcript and lifecycle debugging, use:

- `GET /memories`
- `GET /memory/{memory_id}`
- `GET /memory/{memory_id}/evidence`
- `GET /memory/{memory_id}/history`
- `GET /memory/{memory_id}/active`
- `GET /memory/{memory_id}/chain`
- `GET /transcripts/{session_id}`
- `GET /transcript/message/{message_id}`
- `GET /lanes/core`
- `GET /lanes/working`
- `POST /rebuild`

## Failure handling

If Smart Memory is unavailable:

- keep the agent running
- say continuity is degraded
- do not pretend to remember prior context you could not retrieve
