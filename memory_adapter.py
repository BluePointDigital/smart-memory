#!/usr/bin/env python3
"""
Smart Memory Adapter with Hot Memory Integration
Wraps the existing smart-memory API to include persistent hot memory.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hot_memory_manager import get_hot_memory_for_compose, auto_update_from_context

import urllib.request
import urllib.error

def _api_call(endpoint: str, payload: dict) -> dict:
    """Make API call using urllib (no external deps)."""
    url = f"http://127.0.0.1:8000{endpoint}"
    data = json.dumps(payload).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode('utf-8'), "status": e.code}

def compose_with_hot_memory(agent_identity: str, user_message: str, **kwargs):
    """Call /compose with hot memory included."""
    hot_memory = get_hot_memory_for_compose()
    
    payload = {
        "agent_identity": agent_identity,
        "current_user_message": user_message,
        "hot_memory": hot_memory,
        **kwargs
    }
    
    return _api_call("/compose", payload)

def ingest_and_update(user_message: str, assistant_message: str, timestamp: str = None):
    """Ingest interaction AND auto-update hot memory."""
    from datetime import datetime, timezone
    
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    
    # First, update hot memory based on this conversation
    auto_update_from_context(user_message, assistant_message)
    
    # Then, ingest to long-term memory
    payload = {
        "user_message": user_message,
        "assistant_message": assistant_message,
        "timestamp": timestamp
    }
    
    return _api_call("/ingest", payload)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Smart Memory with Hot Memory integration")
    parser.add_argument("command", choices=["compose", "ingest", "get-hot-memory"])
    parser.add_argument("--identity", default="Nyx - AI assistant with soft fire energy")
    parser.add_argument("--message", "-m", required=True, help="User message")
    parser.add_argument("--assistant", "-a", help="Assistant message (for ingest)")
    parser.add_argument("--max-tokens", type=int, default=8192)
    
    args = parser.parse_args()
    
    if args.command == "compose":
        result = compose_with_hot_memory(
            agent_identity=args.identity,
            user_message=args.message,
            max_prompt_tokens=args.max_tokens
        )
        print(json.dumps(result, indent=2, default=str))
    
    elif args.command == "ingest" and args.assistant:
        result = ingest_and_update(args.message, args.assistant)
        print(json.dumps(result, indent=2, default=str))
    
    elif args.command == "get-hot-memory":
        state = get_hot_memory_for_compose()
        print(json.dumps(state, indent=2, default=str))
