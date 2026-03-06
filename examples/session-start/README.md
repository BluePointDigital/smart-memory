# Session Start Examples

These examples show how to prime Smart Memory v3.1 before the first response of a new session.

## Why this matters

If the agent speaks before querying memory, the session starts blank. The correct pattern is:

```text
session starts
-> check /health
-> call /compose
-> hold returned prompt and traces in agent state
-> answer the user
```

## What `/compose` gives you in v3.1

A compose response can include:

- transcript-backed core memory that should always stay visible
- working context projected from the working lane
- retrieved memories selected for the current message
- temporal state and interaction state
- memory traces explaining what was included and why

## OpenClaw

Use the session-start helpers in this directory together with the Smart Memory skill.

Recommended sequence:

1. ensure the local API is running
2. call `/compose` with a session-start user message
3. keep the returned prompt in agent state
4. only then generate the first greeting

## Python example

```python
from session_prime import prime_memory

context = prime_memory(agent_identity="MyAgent")
prompt = context["prompt"]
traces = context.get("memory_traces", [])
```

## Node example

```javascript
const { primeMemory } = require('./nodejs-agent');

const context = await primeMemory({ agentIdentity: 'MyAgent' });
console.log(context.prompt);
```

## What to look for during validation

Good signs:

- the first reply references current active work
- the compose payload includes core or retrieved memory when expected
- `memory_traces` explain inclusion clearly

Bad signs:

- the agent greets generically with no continuity
- the startup path never calls `/compose`
- the host drops the compose response instead of holding it in session state

## Related docs

- [INTEGRATION.md](/D:/Users/JamesMSI/Desktop/LLM%20Projects/Smart%20Memory/smart-memory/.release-repo/INTEGRATION.md)
- [docs/AGENT-FRAMEWORKS.md](/D:/Users/JamesMSI/Desktop/LLM%20Projects/Smart%20Memory/smart-memory/.release-repo/docs/AGENT-FRAMEWORKS.md)
