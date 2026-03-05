# Suggested Memory Structure (Smart Memory v2)

Smart Memory v2 persists structured cognitive state locally.

## Runtime Data Layout

```text
workspace/
+-- data/
¦   +-- memory_store/
¦   ¦   +-- memories/                # Canonical long-term memory JSON objects
¦   ¦   +-- archive/                 # Archived / consolidated / decayed memory JSON
¦   ¦   +-- vector_index.sqlite      # Vector index (IDs + embeddings + compact payload)
¦   +-- hot_memory/
¦       +-- hot_memory.json          # Working memory + insight queue
+-- MEMORY.md                        # Optional curated human memory notes
+-- memory/                          # Optional human-authored notes
    +-- logs/
    +-- projects/
    +-- decisions/
    +-- lessons/
```

## Recommended Human Notes Structure

- `memory/logs/`: chronological notes and events
- `memory/projects/`: project context and status snapshots
- `memory/decisions/`: decision records and rationale
- `memory/lessons/`: failures, retrospectives, reusable lessons

## Operational Notes

- Personal runtime memory data under `data/` should never be committed.
- Use the API for inspection:
  - `GET /memories`
  - `GET /memory/{memory_id}`
  - `GET /insights/pending`

## Deprecated

Legacy Vector Memory sync commands are removed in v2.
