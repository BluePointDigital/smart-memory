# Memory Structure (Smart Memory v3.1)

Smart Memory v3.1 is transcript-first and SQLite-only at runtime.

## Runtime layout

```text
workspace/
+- data/
   +- memory_store/
   |  +- v3_memory.sqlite
   +- hot_memory/
      +- hot_memory.json   # derived compatibility projection only
+- MEMORY.md               # optional human-maintained notes
+- memory/                 # optional human note hierarchy
```

`hot_memory.json` is not canonical truth. It is a local projection/cache regenerated from derived working-lane state.

## Canonical SQLite tables

`storage/sqlite_memory_store.py` and `transcripts/transcript_store.py` initialize the runtime schema.

Transcript truth tables:

- `sessions`
- `transcript_messages`
- `memory_evidence`

Derived memory tables:

- `memories`
- `memory_entities`
- `lane_memberships`
- `entity_registry`
- `entity_aliases`
- `relationship_hints`
- `vectors`
- `audit_events`
- `schema_migrations`

## Truth hierarchy

1. `transcript_messages`
2. `memories`
3. prompt/lane assembly

Operationally:

- transcript rows are append-only source records
- memories are revision-aware interpretations of transcript evidence
- lanes are downstream prompt context views
- rebuild wipes derived state and replays transcripts

## Memory record fields

Every durable v3.1 memory record includes:

- identifiers and text: `id`, `content`, `memory_type`
- scoring: `importance_score`, `confidence`
- timestamps: `created_at`, `updated_at`, `last_accessed_at`
- lifecycle: `status`, `revision_of`, `supersedes`, `valid_from`, `valid_to`, `decay_policy`
- retrieval hints: `entities`, `keywords`, `retrieval_tags`, `lane_eligibility`, `pinned_priority`
- transcript linkage: `source_session_id`, `source_message_ids`, `evidence_count`, `evidence_summary`
- derivation metadata: `derivation_method`, `rebuilt_at`, `synthetic`
- optional structured facets: `subject_entity_id`, `attribute_family`, `normalized_value`, `state_label`

Non-synthetic durable memories are expected to have transcript evidence.

## Evidence model

`memory_evidence` links a memory record back to one or more transcript messages.

Stored fields:

- `memory_id`
- `message_id`
- `span_start`
- `span_end`
- `evidence_kind`
- `confidence`

Current default behavior is message-level evidence with null spans.

## Lane model

Lane membership is persisted in `lane_memberships`.

- `core`: transcript-backed, durable, high-trust context
- `working`: transcript-backed active task/goal context with bounded decay
- `retrieved`: runtime-selected context, not canonical persisted state

Core and working lanes require transcript-backed memories for auto-promotion.

## Rebuild model

Rebuild preserves transcript truth and clears derived state:

- clear `memories`, `memory_evidence`, `memory_entities`, `lane_memberships`
- clear entity registry and relationship hints
- clear vectors
- replay transcript messages deterministically
- regenerate working-lane hot-memory projection

## Export and backup

JSON export is still useful for backup or inspection, but it is no longer a runtime compatibility layer.

Use exports as derived artifacts, not as an alternative source of truth.
