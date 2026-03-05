# Agent Integration Guide

## Philosophy: Agents That Remember

Smart Memory v2 is designed for agents that **experience** continuity, not just store data.

## The Core Principle

**The agent reaches for its own memories.**

1. Verifies memory system is online
2. Queries what it needs when needed
3. Holds context internally
4. Responds from continuity

## Session Start Pattern

### 1. Health Check
```javascript
import memory from "smart-memory";
const status = await memory.start();
```

### 2. Context Priming
```javascript
const context = await memory.getPromptContext({
  agent_identity: "You are a cognitive assistant...",
  temporal_context: { current_time: new Date().toISOString() },
  conversation_history: "",
  current_message: "Session start - load active projects"
});
```

### 3. Internalize
```javascript
this.context = {
  identity: context.identity_context,
  hot: context.hot_memory,
  retrieved: context.selected_memories
};
```

## Why Self-Directed?

| Approach | Problem | Solution |
|----------|---------|----------|
| External priming | Single point of failure | Agent queries when needed |
| Scripted startup | Race conditions | Agent verifies health |
| Passive storage | No agency | Agent maintains working memory |

## The Goal

An agent that remembers who it is, knows what time it is, holds current priorities, recalls relevant history, and does this itself.

That's continuity. That's a mind, not a cache.
