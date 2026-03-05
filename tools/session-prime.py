#!/usr/bin/env python3
"""
session-prime.py — Universal CLI for Session Memory Priming

Query the cognitive memory server before your agent speaks.

Usage:
    # Basic session start
    python -m tools.session_prime --agent-name "MyAgent"
    
    # With active projects
    python -m tools.session_prime \
        --agent-name "Nyx" \
        --identity "Nyx - AI assistant, soft fire" \
        --project "Smart Memory v2" \
        --project "Session continuity" \
        --question "How do we make priming automatic?"
    
    # Save to file for agent to read
    python -m tools.session_prime --agent-name "MyAgent" --output context.json
    
    # Custom server
    python -m tools.session_prime --agent-name "MyAgent" --server http://localhost:8000

Environment Variables:
    MEMORY_SERVER_URL — Default server URL (default: http://127.0.0.1:8000)
    AGENT_IDENTITY — Default agent identity
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
    
    # Try health check
    try:
        urllib.request.urlopen(f"{server_url}/health", timeout=2)
        return True
    except Exception:
        pass
    
    # Try to start server
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
        epilog="""
Examples:
  %(prog)s --agent-name "Nyx" --output context.json
  %(prog)s --agent-name "MyBot" --project "Task A" --project "Task B"
  %(prog)s --agent-name "Assistant" --identity "Helpful AI" --query "Morning check-in"
        """,
    )
    
    parser.add_argument(
        "--agent-name",
        required=True,
        help="Agent name/identifier",
    )
    parser.add_argument(
        "--identity",
        default=None,
        help="Full agent identity description (defaults to agent-name)",
    )
    parser.add_argument(
        "--query",
        default="Session start",
        help="Opening user message (default: 'Session start')",
    )
    parser.add_argument(
        "--project",
        action="append",
        default=[],
        help="Active project (can specify multiple)",
    )
    parser.add_argument(
        "--question",
        action="append",
        default=[],
        help="Working question/open thread (can specify multiple)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file (default: print to stdout)",
    )
    parser.add_argument(
        "--server",
        default=os.getenv("MEMORY_SERVER_URL", "http://127.0.0.1:8000"),
        help="Memory server URL (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Output raw JSON only (no stderr messages)",
    )
    
    args = parser.parse_args()
    
    identity = args.identity or args.agent_name
    
    if not args.raw:
        print(f"Priming memory for: {args.agent_name}", file=sys.stderr)
    
    # Ensure server is running
    if not ensure_server_running(args.server):
        result = {"status": "error", "message": "Memory server unavailable"}
    else:
        # Query compose
        if not args.raw:
            print("Querying memory server...", file=sys.stderr)
        
        result = query_compose(
            server_url=args.server,
            agent_identity=identity,
            user_message=args.query,
            active_projects=args.project,
            working_questions=args.question,
        )
    
    # Output
    output = json.dumps(result, indent=2)
    
    if args.output:
        Path(args.output).write_text(output)
        if not args.raw:
            print(f"Context saved to: {args.output}", file=sys.stderr)
    else:
        print(output)
    
    return 0 if result.get("status") != "error" and "error" not in result else 1


if __name__ == "__main__":
    sys.exit(main())
