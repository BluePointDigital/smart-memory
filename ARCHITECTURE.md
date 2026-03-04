# Cognitive Memory Architecture

This document is the design anchor for `smart-memory` as it evolves from retrieval-only memory into a cognitive memory backend that supports persistent agent behavior.

It defines:
- Phase 0: Prompt Composer architecture and runtime behavior
- Phase 1: Canonical data schemas and contracts

This architecture is additive to the existing JS runtime and is intentionally modular so implementation can be phased in without breaking current tool interfaces.

## Phase 0: Prompt Composer

### Objective

The Prompt Composer assembles the final context sent to the language model by combining memory layers and system state into one coherent cognitive snapshot.

It must:
- maintain continuity across interactions
- enforce strict context budgeting
- degrade gracefully when subsystems fail
- adapt context dynamically by interaction state

### Core Context Layers

The composer can inject these layers:
1. Agent Identity
2. Temporal State
3. Working Memory (Hot Memory)
4. Relevant Long-Term Memory
5. Insight Queue (Background Cognition)
6. Conversation Context
7. Current User Input

### Interaction State Detection

The composer detects one state per request:
- `engaged`
- `returning`
- `idle`

Behavior by state:
- `engaged`
  - prioritize conversation history
  - minimize long-term memory injection
  - skip insight queue
  - optimize for low latency and conversational flow
- `returning`
  - re-orient with temporal and working context
  - include active projects/top-of-mind
  - optionally include insight queue
  - summarize time gap
- `idle`
  - minimize all optional memory injection
  - include only essential context
  - skip insight queue

Initial defaults for state thresholds:
- engaged window: <= 15 minutes since last interaction
- returning: > 15 minutes since last interaction
- idle override: short/functional commands (for example `status`, `sync`, `search`, flag-like inputs)

### Context Budgeting

Budgets are percentage-based and dynamically adapted:

| Section | Base Allocation |
|---|---|
| System Identity | ~10% |
| Temporal State | ~5% |
| Working Memory | ~10% |
| Retrieved Memory | ~25% |
| Insight Queue | ~5% |
| Conversation History | Remaining budget |

Adjustments:
- engaged: reduce retrieved memory and insight queue, increase conversation
- returning: preserve or increase retrieved memory, allow insight queue
- idle: reduce memory injection, maximize conversation/user command budget

### Master Prompt Template

```text
<system>

[AGENT IDENTITY]
{{ agent_identity }}

[TEMPORAL STATE]
Current Time: {{ current_timestamp }}
Time Since Last Interaction: {{ time_since_last_interaction }}
Interaction State: {{ interaction_state }}

[WORKING CONTEXT]
Active Projects:
- {{ hot_memory.active_projects }}

Current Focus / Goals:
- {{ hot_memory.top_of_mind }}

</system>

{% if insight_queue and interaction_state == "returning" %}
[BACKGROUND INSIGHTS]
The following insights were generated during background reflection cycles.

{% for insight in insight_queue %}
- {{ insight.content }} (confidence: {{ insight.confidence }})
{% endfor %}
{% endif %}

{% if retrieved_memories %}
[RELEVANT LONG-TERM MEMORY]

{% for memory in retrieved_memories %}
[{{ memory.type }}] {{ memory.content }}
{% endfor %}
{% endif %}

<user>

[RECENT CONVERSATION]
{{ conversation_history }}

{{ current_user_message }}

</user>

<assistant>
```

### Context Assembly Pipeline

Pipeline:

```text
User Message
  -> Interaction State Detection
  -> Entity Extraction
  -> Memory Retrieval
  -> Memory Re-ranking
  -> Token Budget Allocation
  -> Prompt Rendering
```

Each stage outputs structured data consumed by the next stage.

### Working Memory (Hot Memory)

Hot memory is fast-read/fast-write working context and should be stored as a JSON document or memory cache.

Fields:
- `agent_state`
- `active_projects`
- `top_of_mind`
- `working_questions`
- `insight_queue`

### Insight Queue

Insights are reflective background outputs.

Insertion rules:
- `confidence >= 0.65`
- expire if unused (recommended: 24 hours)
- inject only when:
  - interaction state is `returning`
  - insight relevance to current interaction is high

### Long-Term Memory Retrieval

Long-term memory types:
- episodic
- semantic
- belief
- goal

Retrieval flow:

```text
Entity Detection
  -> Vector Similarity Search
  -> Top 30 Candidate Memories
  -> LLM/semantic Re-ranking
  -> Top 5 Selected Memories
```

Optional retrieval filters:
- entity match
- time-range constraints
- importance threshold

### Temporal State Provider

Must produce:
- `current_timestamp`
- `time_since_last_interaction`
- `interaction_state`

Computed from current time and latest conversation timestamp.

### Graceful Degradation

#### Vector retrieval failure
- skip long-term memory injection
- continue with hot memory + conversation context
- log failure
- recommended retrieval timeout: `500ms`

#### Working memory failure
- reconstruct minimal context from recent conversation only

Failures must never block prompt assembly.

### Data Contracts

#### Temporal State Provider
- `current_timestamp`
- `time_since_last_interaction`
- `interaction_state`

#### Working Memory Provider
- `agent_state`
- `active_projects`
- `top_of_mind`
- `working_questions`
- `insight_queue`

#### Memory Retrieval System
- `type`
- `content`
- `importance`
- `entities`
- `relations`

#### Insight Generator
- `content`
- `confidence`
- `source_memory_ids`
- `generated_at`

### Design Principles

- continuity over verbosity
- context prioritization
- failure tolerance
- extensibility

### Target Module Layout

```text
prompt_engine/
  state_detector.py
  entity_extractor.py
  memory_retriever.py
  memory_reranker.py
  token_allocator.py
  prompt_renderer.py
  composer.py
  schemas.py
```

## Phase 1: Canonical Schemas

Phase 1 defines strict, versioned Pydantic models for all core memory objects and working-state contracts.

Implemented in:
- `prompt_engine/schemas.py`

Coverage includes:
- base long-term memory schema (with versioning, entities, relations, emotional metadata, access tracking)
- specialized memory types (`episodic`, `semantic`, `belief`, `goal`)
- insight objects
- agent state and hot memory
- temporal state
- prompt composer I/O contracts

## Implementation Notes

- This phase introduces no storage engine changes and no vector index requirements.
- Existing JS search tooling remains valid while the composer architecture is introduced incrementally.
- Future phases should adapt retrieval and reflection systems to emit objects conforming to `prompt_engine/schemas.py`.
