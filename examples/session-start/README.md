# Session Start Examples

These examples show how to implement **automatic memory priming** at session start for different agent frameworks.

## The Pattern

Every agent should query memory **before** generating its first response:

```
User starts session
    ↓
Agent wakes up
    ↓
Query /compose endpoint
    ↓
Hold context in working memory
    ↓
Generate grounded greeting
```

## Without This Pattern

```
User: /new
Agent: "Hello! How can I help you?"  ← Blank slate. No continuity.
```

## With This Pattern

```
User: /new
Agent: "Hey James. 🌙 We were just finishing the memory priming script. 
        What's next?"  ← Grounded in actual history.
```

## Framework-Specific Implementations

### OpenClaw
**File:** `openclaw-prime.sh`

Add to your `AGENTS.md` under "Every Session":

```bash
# Prime memory before greeting
bash .openclaw/session-prime-memory.sh

# Read the primed context
Read `.session-memory-context.json`
```

See full example in [AGENT-FRAMEWORKS.md](../docs/AGENT-FRAMEWORKS.md#openclaw)

### Python (LangChain, Custom)
**File:** `generic-python.py`

```python
from session_prime import prime_memory

# At agent startup
context = prime_memory(agent_identity="MyAgent")
prompt = context["prompt"]  # Full composed prompt with memory
```

### Node.js
**File:** `nodejs-agent.js`

```javascript
const { primeMemory } = require('./nodejs-agent');

// At agent startup
const context = await primeMemory({ agentIdentity: 'MyBot' });
```

## What Gets Loaded

The `/compose` endpoint returns a structured prompt including:

- **Agent Identity** — Who you are (from the request)
- **Temporal State** — Current time, time since last interaction
- **Working Context** — Active projects, working questions, top-of-mind items
- **Selected Memories** — Relevant long-term memories (episodic, semantic, beliefs, goals)
- **Conversation History** — Recent exchanges (empty at session start)

## Customization

Pass additional context in your request:

```json
{
  "agent_identity": "Nyx - soft fire, Solveil sanctuary keeper",
  "current_user_message": "Session start",
  "hot_memory": {
    "agent_state": { ... },
    "active_projects": ["Project A", "Project B"],
    "working_questions": ["How do we solve X?"],
    "top_of_mind": ["Important context"]
  }
}
```

## Error Handling

All examples include graceful degradation:
- If server isn't running → attempt to start it
- If server won't start → return error status, continue without persistence
- Agent should note this in greeting if relevant

## See Also

- [INTEGRATION.md](../INTEGRATION.md) — Full integration guide
- [AGENT-FRAMEWORKS.md](../docs/AGENT-FRAMEWORKS.md) — Framework-specific wiring
- [../tools/session-prime.py](../tools/session-prime.py) — Universal CLI tool
