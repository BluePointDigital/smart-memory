# Memory Structure (Smart Memory v3)

Smart Memory v3 keeps long-term memory in SQLite and preserves JSON compatibility for migration, export, and fixtures.

## Runtime layout

```text
workspace/
+- data/
   +- memory_store/
   |  +- v3_memory.sqlite
   |  +- memories/                  # legacy JSON import/export compatibility
   |  +- archive/                   # legacy JSON archive compatibility
   +- hot_memory/
      +- hot_memory.json            # working-context and insight compatibility store
+- MEMORY.md                        # optional human-maintained notes
+- memory/                          # optional human note hierarchy
   +- logs/
   +- projects/
   +- decisions/
   +- lessons/
```

## Canonical SQLite tables

`storage/sqlite_memory_store.py` initializes these tables:

- `memories`
- `memory_entities`
- `lane_memberships`
- `entity_registry`
- `entity_aliases`
- `relationship_hints`
- `audit_events`
- `schema_migrations`

The vector index uses the same local SQLite strategy through `VectorIndexStore`.

## Memory record fields

Every v3 record includes the required product fields from the schema layer, including:

- identifiers and text: `id`, `content`, `memory_type`
- scoring: `importance_score`, `confidence`
- timestamps: `created_at`, `updated_at`, `last_accessed_at`
- traceability: `access_count`, `source_session_id`, `source_message_ids`
- retrieval hints: `entities`, `keywords`, `retrieval_tags`
- lifecycle: `status`, `revision_of`, `supersedes`, `valid_from`, `valid_to`, `decay_policy`
- lane metadata: `lane_eligibility`, `pinned_priority`
- explanation: `explanation`
- optional structured facets: `subject_entity_id`, `attribute_family`, `normalized_value`, `state_label`

The optional facets are nullable and only used when they can be derived safely. They are not universal requirements for every memory type.

## Status model

Default retrieval behavior is status-aware:

- `active`: eligible
- `superseded`: excluded unless history mode is requested
- `expired`: excluded unless history mode is requested
- `uncertain`: eligible with penalty
- `archived`: off by default
- `rejected`: never retrieved

## Lane model

Lane membership is stored explicitly in `lane_memberships`.

- `core`: always-visible, durable, high-trust context
- `working`: active task and project context with bounded decay
- `retrieved`: runtime-selected lane, not persisted as a static prompt dump

The current prompt engine renders core memory as dedicated lines and projects working-lane state through the hot-memory compatibility block.

## Hot memory compatibility store

`data/hot_memory/hot_memory.json` still exists because the current runtime uses it for:

- active projects
- working questions
- top-of-mind items
- insight queue
- reinforcement metadata and retrieval counts

In v3, this file is a compatibility projection for working context, not the canonical durable memory database.

## Legacy JSON compatibility

`storage/json_memory_store.py` is still supported for:

- migration input
- fixture creation
- debugging and export
- legacy memory directories under `data/memory_store/memories/`

New canonical writes should go to SQLite.

## Migration

Use `migration/v3_migration.py` to upgrade legacy JSON memories into SQLite.

Migration behavior:

- preserves IDs where possible
- defaults status to `active`
- backfills lane eligibility by memory type
- inserts placeholder source session IDs when legacy data is missing
- normalizes entity references where possible

## Operational guidance

- keep `data/` out of version control
- use the API for inspection instead of hand-editing the SQLite database
- prefer migration scripts or API writes over direct manual schema edits
- if you export back to JSON for debugging, treat those files as derived artifacts
