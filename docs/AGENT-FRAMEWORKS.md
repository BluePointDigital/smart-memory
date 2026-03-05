# Agent Framework Integration Guide

How to wire Smart Memory v2 into different agent frameworks for automatic session priming.

## The Golden Rule

> **Query memory BEFORE the agent speaks.**

Without this, every session starts as a blank slate. With it, agents wake up with continuity.

---

## OpenClaw

OpenClaw uses `AGENTS.md` to define startup behavior.

### 1. Copy the priming script

```bash
cp examples/session-start/openclaw-prime.sh ~/.openclaw/session-prime-memory.sh
```

### 2. Update AGENTS.md

Add to the "Every Session" section:

```markdown
## Every Session

Before doing anything else:

1. Read `SOUL.md` — this is who you are
2. Read `USER.md` — this is who you're helping
3. **PRIME MEMORY** — Run the automatic memory priming script:
   ```bash
   bash ~/.openclaw/session-prime-memory.sh
   ```
4. Read `.session-memory-context.json` — this loads your hot memory context
   - Active projects and their status
   - What you were working on
   - Open threads or unresolved questions
5. Read `memory/YYYY-MM-DD.md` (today + yesterday) for recent context
```

### 3. Customize the script

Edit `AGENT_IDENTITY` in the script:

```bash
AGENT_IDENTITY="Nyx - AI assistant with persistent memory, soft fire, Solveil sanctuary keeper"
```

### 4. How it works

When a new session starts:
1. OpenClaw reads AGENTS.md
2. Runs the priming script (starts server if needed, queries /compose)
3. Saves context to `.session-memory-context.json`
4. Agent reads that file and holds the context
5. First response is grounded in actual history

---

## LangChain

For LangChain agents, use a startup callback or override the conversation chain.

### Option A: ConversationBufferMemory with Custom Startup

```python
from langchain.memory import ConversationBufferMemory
from smart_memory.prime import prime_memory  # Use our Python helper

class PrimedConversationChain:
    def __init__(self, agent_identity: str):
        # Prime memory at initialization
        context = prime_memory(agent_identity=agent_identity)
        
        self.memory = ConversationBufferMemory()
        
        # If we got good context, inject it as system context
        if "prompt" in context:
            self.memory.chat_memory.add_system_message(context["prompt"])
    
    def invoke(self, user_input: str):
        # Your normal chain invocation
        ...
```

### Option B: Custom Memory Class

```python
from langchain.schema import BaseMemory
from pydantic import BaseModel

class SmartMemory(BaseModel, BaseMemory):
    agent_identity: str
    server_url: str = "http://127.0.0.1:8000"
    
    def load_memory_variables(self, inputs):
        # Called at start of each chain run
        context = prime_memory(
            agent_identity=self.agent_identity,
            user_message=inputs.get("input", ""),
        )
        return {"memory_context": context.get("prompt", "")}
    
    def save_context(self, inputs, outputs):
        # Ingest interaction after response
        requests.post(f"{self.server_url}/ingest", json={
            "user_message": inputs["input"],
            "assistant_message": outputs["output"],
        })
```

---

## OpenAI Assistants API

For Assistants, use the `instructions` field to inject primed context.

```python
import openai
from session_prime import prime_memory

client = openai.OpenAI()

# At session start
context = prime_memory(agent_identity="MyAssistant")

# Create thread with primed instructions
thread = client.beta.threads.create(
    instructions=context["prompt"],  # Full composed prompt with memory
)

# Continue conversation normally
```

---

## Custom Python Agents

For your own agent implementation:

```python
import requests
from datetime import datetime, timezone

class CognitiveAgent:
    def __init__(self, identity: str, memory_server: str = "http://127.0.0.1:8000"):
        self.identity = identity
        self.memory_server = memory_server
        self.context = None
    
    def wake(self):
        """Call this at session start before first response."""
        self.context = self._prime_memory()
        return self
    
    def _prime_memory(self):
        payload = {
            "agent_identity": self.identity,
            "current_user_message": "Session start",
            "conversation_history": "",
            "hot_memory": {
                "agent_state": {
                    "status": "engaged",
                    "last_interaction_timestamp": datetime.now(timezone.utc).isoformat(),
                    "last_background_task": "session_start",
                },
                "active_projects": [],
                "working_questions": [],
                "top_of_mind": [],
            },
        }
        
        resp = requests.post(f"{self.memory_server}/compose", json=payload)
        return resp.json()
    
    def respond(self, user_message: str) -> str:
        # Use self.context["prompt"] as system context
        # + user_message to generate response
        ...
    
    def ingest(self, user_message: str, assistant_message: str):
        """Call after each exchange to persist continuity."""
        requests.post(f"{self.memory_server}/ingest", json={
            "user_message": user_message,
            "assistant_message": assistant_message,
        })

# Usage
agent = CognitiveAgent(identity="Nyx").wake()
response = agent.respond("What were we working on?")
```

---

## Node.js / JavaScript Agents

See `examples/session-start/nodejs-agent.js` for a reusable module.

```javascript
const { primeMemory } = require('./session-start/nodejs-agent');

class CognitiveAgent {
  constructor(identity) {
    this.identity = identity;
    this.context = null;
  }
  
  async wake() {
    this.context = await primeMemory({ agentIdentity: this.identity });
    return this;
  }
  
  async respond(userMessage) {
    // Use this.context.prompt as system prompt
    // + userMessage to generate response
    const response = await this.llm.complete({
      system: this.context.prompt,
      user: userMessage,
    });
    
    // Ingest for continuity
    await this.ingest(userMessage, response);
    
    return response;
  }
}

// Usage
const agent = await new CognitiveAgent("Nyx").wake();
const response = await agent.respond("What were we working on?");
```

---

## Docker / Containerized Agents

If your agent runs in a container:

### 1. Run memory server as sidecar

```yaml
version: '3'
services:
  agent:
    image: my-agent:latest
    environment:
      - MEMORY_SERVER_URL=http://memory:8000
    depends_on:
      - memory
  
  memory:
    image: smart-memory:latest
    volumes:
      - ./data:/data
    ports:
      - "8000:8000"
```

### 2. In agent code

```python
import os
from session_prime import prime_memory

MEMORY_URL = os.getenv("MEMORY_SERVER_URL", "http://127.0.0.1:8000")

context = prime_memory(
    agent_identity="MyAgent",
    server_url=MEMORY_URL,
)
```

---

## Testing Your Integration

After wiring up session priming:

1. **Start a fresh session** (or /new in OpenClaw)
2. **Check the context file** was created and has content
3. **Verify the greeting** references actual history, not generic help offers
4. **Test continuity** — mention something from last session, verify agent recalls

### Red Flags (Integration Broken)

- Agent says "How can I help you?" with no context
- Agent asks "What were we working on?" (should already know)
- Empty or error response from /compose

### Green Flags (Working)

- Agent greets with "Hey [Name]. We were just..."
- Agent references active projects without prompting
- Context file shows selected_memories with real content

---

## Troubleshooting

### "Memory server unavailable"

- Check if port 8000 is in use: `lsof -i :8000`
- Verify virtual environment exists: `ls smart-memory/.venv/bin/activate`
- Check server logs: `cat /tmp/smart-memory-server.log`

### "Empty context returned"

- Normal for first session (no memories yet)
- After interactions, run `/ingest` to populate
- Check `/memories` endpoint to verify data exists

### "Agent still wakes up blank"

- Verify priming script runs BEFORE first response
- Check that agent actually reads the context file
- Ensure agent holds context in state, not just reads and discards

---

## See Also

- [INTEGRATION.md](../INTEGRATION.md) — Core integration concepts
- [examples/session-start/](../examples/session-start/) — Framework-specific code
- [../tools/session-prime.py](../tools/session-prime.py) — Universal CLI tool
