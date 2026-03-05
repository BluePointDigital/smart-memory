#!/bin/bash
# Post-conversation hook for Smart Memory
# Call this after significant conversations to update hot memory
# Usage: smem-hook.sh "user message" "assistant response"

WORKSPACE="$HOME/.openclaw/workspace"
SM_DIR="$WORKSPACE/smart-memory"

if [ $# -lt 2 ]; then
    echo "Usage: smem-hook.sh \"user message\" \"assistant response\""
    exit 1
fi

USER_MSG="$1"
ASST_MSG="$2"

# Update hot memory based on conversation
python3 "$SM_DIR/hot_memory_manager.py" auto "$USER_MSG" "$ASST_MSG" > /dev/null 2>&1

# Ingest to long-term memory (optional - can be done separately)
# curl -s -X POST http://127.0.0.1:8000/ingest \
#   -H "Content-Type: application/json" \
#   -d "{\"user_message\":\"$USER_MSG\",\"assistant_message\":\"$ASST_MSG\",\"timestamp\":\"$(date -Iseconds)\"}" > /dev/null 2>&1

echo "✓ Hot memory updated"
