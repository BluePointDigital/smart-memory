#!/bin/bash
# OpenClaw Session Memory Priming Script
# Place in .openclaw/ and reference from AGENTS.md
#
# This script queries the cognitive memory server before the agent speaks,
# ensuring continuity across sessions.

set -e

MEMORY_SERVER="http://127.0.0.1:8000"
CONTEXT_FILE="${CONTEXT_FILE:-.session-memory-context.json}"
LOG_FILE="/tmp/memory-prime.log"
AGENT_IDENTITY="${AGENT_IDENTITY:-AI Assistant}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log "=== Session Memory Prime Started ==="

# 1. Check server health
if ! curl -s "$MEMORY_SERVER/health" > /dev/null 2>&1; then
    log "Server not running, attempting startup..."
    
    # Try common locations for smart-memory
    for DIR in "./smart-memory" "../smart-memory" "./skills/smart-memory" "~/.openclaw/workspace/smart-memory"; do
        if [ -f "$DIR/.venv/bin/activate" ]; then
            cd "$DIR"
            nohup bash -c '. .venv/bin/activate && python -m uvicorn server:app --host 127.0.0.1 --port 8000' > /tmp/smart-memory-server.log 2>&1 &
            sleep 3
            break
        fi
    done
fi

# Verify server is up
if ! curl -s "$MEMORY_SERVER/health" > /dev/null 2>&1; then
    log "ERROR: Memory server unavailable"
    echo '{"status": "error", "message": "Memory server unavailable"}' > "$CONTEXT_FILE"
    exit 1
fi

log "Server healthy"

# 2. Query /compose for session context
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%S)

# Build JSON payload
curl -s -X POST "$MEMORY_SERVER/compose" \
    -H "Content-Type: application/json" \
    -d "{
        \"agent_identity\": \"$AGENT_IDENTITY\",
        \"current_user_message\": \"Session start\",
        \"conversation_history\": \"\",
        \"hot_memory\": {
            \"agent_state\": {
                \"status\": \"engaged\",
                \"last_interaction_timestamp\": \"$TIMESTAMP\",
                \"last_background_task\": \"session_start\"
            },
            \"active_projects\": [],
            \"working_questions\": [],
            \"top_of_mind\": []
        }
    }" > "$CONTEXT_FILE" 2>/dev/null || {
    log "ERROR: Failed to query /compose"
    echo '{"status": "error", "message": "Compose query failed"}' > "$CONTEXT_FILE"
    exit 1
}

log "Context saved to $CONTEXT_FILE"
log "=== Session Memory Prime Complete ==="
