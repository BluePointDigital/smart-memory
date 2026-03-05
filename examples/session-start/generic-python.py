#!/usr/bin/env python3
"""
Generic Python Session Memory Primer
For agents built with Python (LangChain, custom frameworks, etc.)

Usage:
    from session_prime import prime_memory
    context = prime_memory(agent_identity="MyAgent")
    
Or CLI:
    python session_prime.py --agent-name "MyAgent" --output context.json
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def ensure_server_running(server_url: str = "http://127.0.0.1:8000") -> bool:
    """Check if memory server is healthy, attempt to start if not."""
    import urllib.request
    
    try:
        urllib.request.urlopen(f"{server_url}/health", timeout=2)
        return True
    except Exception:
        pass
    
    # Try to start server
    for path in ["./smart-memory", "../smart-memory", "./skills/smart-memory"]:
        venv_activate = Path(path) / ".venv/bin/activate"
        if venv_activate.exists():
            subprocess.Popen(
                f"cd {path} && . .venv/bin/activate && python -m uvicorn server:app --host 127.0.0.1 --port 8000 > /tmp/smart-memory-server.log 2>&1 &",
                shell=True,
            )
            time.sleep(3)
            try:
                urllib.request.urlopen(f"{server_url}/health", timeout=2)
                return True
            except Exception:
                pass
    
    return False


def prime_memory(
    agent_identity: str,
    user_message: str = "Session start",
    server_url: str = "http://127.0.0.1:8000",
    active_projects: list[str] | None = None,
    working_questions: list[str] | None = None,
) -> dict[str, Any]:
    """
    Prime agent memory at session start.
    
    Returns the composed prompt context from the memory server.
    """
    import urllib.request
    
    if not ensure_server_running(server_url):
        return {"status": "error", "message": "Memory server unavailable"}
    
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
            "active_projects": active_projects or [],
            "working_questions": working_questions or [],
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
    parser = argparse.ArgumentParser(description="Prime agent memory at session start")
    parser.add_argument("--agent-name", required=True, help="Agent identity string")
    parser.add_argument("--query", default="Session start", help="Opening query")
    parser.add_argument("--output", help="Output file (default: stdout)")
    parser.add_argument("--server", default="http://127.0.0.1:8000", help="Memory server URL")
    
    args = parser.parse_args()
    
    context = prime_memory(
        agent_identity=args.agent_name,
        user_message=args.query,
        server_url=args.server,
    )
    
    output = json.dumps(context, indent=2)
    
    if args.output:
        Path(args.output).write_text(output)
        print(f"Context saved to {args.output}", file=sys.stderr)
    else:
        print(output)
    
    return 0 if context.get("status") != "error" else 1


if __name__ == "__main__":
    sys.exit(main())
