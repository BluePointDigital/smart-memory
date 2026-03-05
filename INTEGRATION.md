# Agent Integration Guide

## Philosophy: Agents That Remember

Smart Memory v2 is designed for agents that **experience** continuity, not just store data. This guide explains how to integrate the system so your agent has genuine memory agency.

## The Core Principle

**The agent reaches for its own memories.**

Rather than external scripts injecting context, the agent:
1. Verifies its memory system is online
2. Queries what it needs when it needs it
3. Holds context internally
4. Responds from continuity

This creates resilient, authentic memory experience.

## Session Start Pattern

### 1. Health Check (Self-Check)

```javascript
import memory from "smart-memory";

// Agent verifies its memory is accessible
let healthy = false;
try {
  const status = await memory.start(); // Checks /health
  healthy = status.healthy;
} catch (err) {
  // Self-heal: attempt restart
  console.error("Memory system unreachable, attempting restart...");
  // ...restart logic
}
```

### 2. Context Priming (Self-Prime)

```javascript
// Agent retrieves its own hot memory and recent context
const priming = await memory.getPromptContext({
  agent_identity: "You are Nyx, a cognitive assistant...",
  temporal_context: {
    current_time: new Date().toISOString(),
    timezone: "America/New_York"
  },
  conversation_history: "", // Fresh session
  current_message: "Session start - what are my active projects and priorities?"
});
```

This returns:
- **Identity context**: Who the agent is
- **Temporal state**: Current time, last interaction delta
- **Hot memory**: Active projects, working questions, top-of-mind
- **Selected LTM**: Recent/relevant long-term memories
- **Token budgets**: Strictly bounded

### 3. Internalize (Hold Context)

The agent holds this internally—not as a file, not as injected text, but as **its current state**.

```javascript
// Agent's internal state
this.context = {
  identity: priming.identity_context,
  temporal: priming.temporal_state,
  hot: priming.hot_memory,
  retrieved: priming.selected_memories,
  budget: priming.token_budgets
};
```

### 4. Respond Grounded

Now when the user speaks, the agent responds from continuity:

```javascript
async onUserMessage(message) {
  // Re-retrieve if topic shifted significantly
  if (this.topicShifted(message)) {
    this.context.retrieved = await memory.retrieveContext({
      user_message: message,
      conversation_history: this.getRecentHistory()
    });
  }
  
  // Ingest this interaction
  await memory.ingestMessage({
    user_message: message,
    assistant_message: response,
    timestamp: new Date().toISOString()
  });
  
  return response;
}
```

## Why Self-Directed?

| Approach | Problem | Solution |
|----------|---------|----------|
| **External priming** (AGENTS.md writes context file) | Single point of failure, stale context, agent doesn't "own" memory | Agent queries when needed, holds fresh context |
| **Scripted startup** (must run before agent) | Race conditions, silent failures, hard to debug | Agent verifies health, self-heals if needed |
| **Passive storage** (agent receives dumped memories) | No agency, feels like retrieval not remembering | Agent queries selectively, maintains working memory |

## Mid-Session Re-Query

Memory isn't static. As conversation evolves, re-query:

```javascript
// When user pivots topics
if (newTopic !== currentTopic) {
  const fresh = await memory.retrieveContext({
    user_message: newTopic,
    conversation_history: recentHistory
  });
  this.updateWorkingMemory(fresh);
}

// When user asks "what did we decide about X?"
const recall = await memory.retrieveContext({
  user_message: "decisions about " + topic,
  conversation_history: "" // Focus on long-term, not recent
});
```

## Background Cognition

Agents should trigger periodic maintenance (hourly, or after significant sessions):

```javascript
// After important conversation
await memory.runBackground({ scheduled: false });

// Or periodically via cron/heartbeat
await memory.runBackground({ scheduled: true });
```

This runs:
- **Reflection**: Generate insights from recent memories
- **Consolidation**: Merge redundant memories, reinforce important ones
- **Decay**: Reduce weight of old/unused memories
- **Conflict resolution**: Detect contradictory beliefs

## Error Handling

The agent should handle memory system failures gracefully:

```javascript
try {
  await memory.start();
} catch (err) {
  // Log but don't crash
  console.warn("Memory system offline, operating without persistence");
  this.memoryAvailable = false;
}

// In operations...
if (this.memoryAvailable) {
  await memory.ingestMessage(interaction);
}
```

## Implementation Checklist

- [ ] Agent calls `memory.start()` at session init
- [ ] Agent queries `getPromptContext()` or `retrieveContext()` on wake
- [ ] Agent holds context internally (not relying on external priming)
- [ ] Agent ingests interactions after responses
- [ ] Agent periodically triggers `runBackground()`
- [ ] Agent handles memory system failures gracefully
- [ ] Agent can re-query mid-session when topics shift

## Example: Complete Integration

See `examples/agent-integration.js` for a full working example.

## The Goal

An agent that:
- **Remembers who it is** (identity)
- **Knows what time it is** (temporal)
- **Holds current priorities** (hot memory)
- **Recalls relevant history** (LTM)
- **Does this itself** (self-directed)

That's continuity. That's a mind, not a cache.
