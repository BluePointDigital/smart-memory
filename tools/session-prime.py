#!/usr/bin/env python3
"""
session-prime.py - Universal CLI for transcript-first session memory priming.

Query the local cognitive memory server before your agent speaks.

Usage:
    python -m tools.session_prime --agent-name "MyAgent"

    python -m tools.session_prime \
        --agent-name "Nyx" \
        --identity "Nyx - AI assistant, soft fire" \
        --project "Smart Memory v3.1" \
        --project "Session continuity" \
        --question "How do we make priming automatic?"

    python -m tools.session_prime --agent-name "MyAgent" --output context.json
    python -m tools.session_prime --agent-name "MyAgent" --server http://localhost:8000

Environment Variables:
    MEMORY_SERVER_URL - Default server URL (default: http://127.0.0.1:8000)
    AGENT_IDENTITY - Default agent identity
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def ensure_server_running(server_url: str) -> bool:
    """Check health and attempt to start if needed."""
    import urllib.request
    
    try:
        urllib.request.urlopen(f"{server_url}/health", timeout=2)
        return True
    except Exception:
        pass
    
    print("Memory server not running. Attempting to start...", file=sys.stderr)
    
    for rel_path in [".", "..", "./skills", "~/.openclaw/workspace"]:
        base = Path(rel_path).expanduser().resolve()
        venv_activate = base / "smart-memory" / ".venv" / "bin" / "activate"
        server_py = base / "smart-memory" / "server.py"
        
        if venv_activate.exists() and server_py.exists():
            cmd = f"cd {base}/smart-memory && . .venv/bin/activate && python -m uvicorn server:app --host 127.0.0.1 --port 8000 > /tmp/smart-memory-server.log 2>&1 &"
            subprocess.Popen(cmd, shell=True)
            time.sleep(3)
            
            try:
                urllib.request.urlopen(f"{server_url}/health", timeout=2)
                print("Server started successfully.", file=sys.stderr)
                return True
            except Exception:
                pass
    
    print("ERROR: Could not start memory server.", file=sys.stderr)
    return False


def query_compose(
    server_url: str,
    agent_identity: str,
    user_message: str,
    active_projects: list[str],
    working_questions: list[str],
) -> dict[str, Any]:
    """Query the /compose endpoint."""
    import urllib.request
    
    now = datetime.now(timezone.utc).isoformat()
    
    payload = {
        "agent_identity": agent_identity,
        "current_user_message": user_message,
        "conversation_history": "",
        "hot_memory": {
            "agent_state": {
                "status": "engaged",
                "last_interaction_timestamp": now,
                "last_background_task": "session_start",
            },
            "active_projects": active_projects,
            "working_questions": working_questions,
            "top_of_mind": [],
        },
    }
    
    req = urllib.request.Request(
        f"{server_url}/compose",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        return {"status": "error", "message": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Prime agent memory at session start",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--agent-name", required=True, help="Agent name")
    parser.add_argument("--identity", help="Full agent identity string")
    parser.add_argument("--project", action="append", default=[], help="Active project")
    parser.add_argument("--question", action="append", default=[], help="Working question")
    parser.add_argument("--message", default="Session start - what matters right now?", help="Current user message")
    parser.add_argument("--server", default=os.environ.get("MEMORY_SERVER_URL", "http://127.0.0.1:8000"), help="Server URL")
    parser.add_argument("--output", help="Optional output file")
    args = parser.parse_args()

    identity = args.identity or os.environ.get("AGENT_IDENTITY") or args.agent_name

    if not ensure_server_running(args.server):
        sys.exit(1)

    result = query_compose(
        server_url=args.server,
        agent_identity=identity,
        user_message=args.message,
        active_projects=args.project,
        working_questions=args.question,
    )

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
