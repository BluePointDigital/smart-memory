# Hot Memory Extension for Smart Memory v2.1

## Summary
This extension adds persistent "hot memory" (working context) to Smart Memory v2.1. Hot memory survives between sessions and appears in every prompt's `[WORKING CONTEXT]` section.

## Files Added/Modified

### New Files
1. `hot_memory_manager.py` - Core hot memory persistence and auto-update logic
2. `memory_adapter.py` - API wrapper that auto-includes hot memory in compose calls
3. `smem-hook.sh` - Shell hook for post-conversation updates
4. `hot_memory_state.json` - Persistent storage (auto-created)

### Modified
None (this is an extension, not a core modification)

## Key Features

### 1. Persistent Working Context
Hot memory stores:
- `active_projects` - Top 5 current projects with descriptions
- `working_questions` - Open questions being explored
- `top_of_mind` - Immediate priorities/notes
- `insight_queue` - Live pending insights from background cognition
- `agent_state` - Status, timestamps, last background task

### 2. Auto-Update from Conversations
- Detects project mentions (customizable keyword list)
- Adds questions (anything with `?`) to working_questions
- Prevents duplicate projects via key-based matching
- Updates timestamp and status on every interaction

### 3. API Integration
The `memory_adapter.py` provides:
```python
compose_with_hot_memory(agent_identity, user_message)
# Automatically includes hot memory in /compose calls

ingest_and_update(user_message, assistant_message)
# Ingests to LTM + updates hot memory in one call
```

## Bug Fix: Duplicate Prevention
Original code checked `project_desc not in projects` which failed when descriptions differed (e.g., "Mobile App - iOS development" vs "Mobile App - iOS and Android development").

**Fixed by:** `_project_exists()` function that extracts project keys (text before " - ") and compares normalized keys.

```python
def _project_exists(projects: list[str], project_key: str) -> bool:
    """Check if a project already exists by its key identifier."""
    project_key_lower = project_key.lower()
    for project in projects:
        existing_key = project.split(" - ")[0].lower() if " - " in project else project.lower()
        if existing_key == project_key_lower:
            return True
    return False
```

## Usage

### Initialize hot memory
```bash
python3 hot_memory_manager.py init
```

### After conversations
```bash
# Quick update (hot memory only)
./smem-hook.sh "user message" "assistant response"

# Full update (hot memory + LTM ingestion)
python3 memory_adapter.py ingest -m "user message" -a "assistant response"
```

### Compose with hot memory
```bash
python3 memory_adapter.py compose -m "What are my priorities?"
```

## Customizing Project Detection

Edit `auto_update_from_context()` in `hot_memory_manager.py` to match your domain:

```python
project_definitions = [
    # Example: Product/Platform projects
    (["mobile app", "ios app", "android app"], "Mobile App", "Mobile App - cross-platform development"),
    (["web platform", "web app"], "Web Platform", "Web Platform - frontend and backend development"),
    
    # Example: Infrastructure
    (["infrastructure", "infra", "deployment"], "Infrastructure", "Infrastructure - hosting, CI/CD, DevOps"),
    
    # Add your own project keywords here
]
```

## Integration Path

### Option A: Fork + PR to Upstream (Recommended)
1. Fork https://github.com/BluePointDigital/smart-memory/
2. Add these files to a `contrib/hot-memory/` directory
3. Submit PR with:
   - Hot memory extension module
   - Updated README with usage docs
   - Tests for duplicate prevention

### Option B: Separate Package
Create `smart-memory-hot` as a companion package that depends on smart-memory and provides the hot memory layer.

### Option C: Documentation Patch
If upstream isn't accepting changes, document as a "recommended extension" in the wiki.

## Testing

### Test duplicate prevention
```bash
# Initialize
python3 hot_memory_manager.py init

# Try to add duplicate project
./smem-hook.sh "Working on the mobile app today" "OK"
./smem-hook.sh "Continuing mobile app development" "Great"

# Verify only one "Mobile App" entry
python3 hot_memory_manager.py get | grep "Mobile App"
```

### Test new project addition
```bash
./smem-hook.sh "Starting the infrastructure migration" "Let's do it"
# Should add Infrastructure to active_projects
```

## Token Impact

Hot memory adds ~400 tokens to composed prompts (configurable):
- 5 active projects: ~150 tokens
- 4 working questions: ~100 tokens  
- 3 top-of-mind items: ~75 tokens
- Agent state + overhead: ~75 tokens

This fits within the default token allocation's `working_memory` budget.

---

**Created:** 2026-03-05
**Smart Memory Version:** v2.1
**License:** Same as Smart Memory (MIT)
