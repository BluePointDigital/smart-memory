#!/usr/bin/env python3
"""
Hot Memory Manager for Smart Memory v2.1
Provides persistent hot memory storage and automatic updates.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

HOT_MEMORY_FILE = Path.home() / ".openclaw" / "workspace" / "smart-memory" / "hot_memory_state.json"

def get_default_hot_memory():
    """Get current hot memory state from disk or create default."""
    if HOT_MEMORY_FILE.exists():
        with open(HOT_MEMORY_FILE) as f:
            return json.load(f)
    
    return {
        "agent_state": {
            "status": "idle",
            "last_interaction_timestamp": datetime.now(timezone.utc).isoformat(),
            "last_background_task": "none"
        },
        "active_projects": [],
        "working_questions": [],
        "top_of_mind": [],
        "insight_queue": []
    }

def save_hot_memory(state: dict):
    """Persist hot memory to disk."""
    HOT_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HOT_MEMORY_FILE, 'w') as f:
        json.dump(state, f, indent=2, default=str)

def update_hot_memory(
    active_projects: list[str] = None,
    working_questions: list[str] = None,
    top_of_mind: list[str] = None,
    agent_status: str = None,
    last_background_task: str = None
):
    """Update specific fields in hot memory."""
    state = get_default_hot_memory()
    
    if active_projects is not None:
        state["active_projects"] = active_projects
    if working_questions is not None:
        state["working_questions"] = working_questions
    if top_of_mind is not None:
        state["top_of_mind"] = top_of_mind
    if agent_status:
        state["agent_state"]["status"] = agent_status
    if last_background_task:
        state["agent_state"]["last_background_task"] = last_background_task
    
    state["agent_state"]["last_interaction_timestamp"] = datetime.now(timezone.utc).isoformat()
    
    save_hot_memory(state)
    return state

def get_hot_memory_for_compose():
    """Get hot memory formatted for /compose API."""
    import urllib.request
    import urllib.error
    
    state = get_default_hot_memory()
    
    # Fetch pending insights from server
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/insights/pending", method='GET')
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode('utf-8'))
            insights = data.get("insights", [])
            # Convert to proper format
            state["insight_queue"] = [
                {
                    "id": i.get("id"),
                    "content": i.get("content"),
                    "confidence": i.get("confidence"),
                    "source_memory_ids": i.get("source_memory_ids", []),
                    "generated_at": i.get("generated_at"),
                    "expires_at": i.get("expires_at")
                }
                for i in insights
            ]
    except Exception as e:
        print(f"Warning: Could not fetch insights: {e}")
    
    return state

def _project_exists(projects: list[str], project_key: str) -> bool:
    """Check if a project already exists by its key identifier."""
    project_key_lower = project_key.lower()
    for project in projects:
        # Extract the key from existing project (text before first " - ")
        existing_key = project.split(" - ")[0].lower() if " - " in project else project.lower()
        if existing_key == project_key_lower:
            return True
    return False

def auto_update_from_context(user_message: str, assistant_message: str):
    """Automatically update hot memory based on conversation content.
    
    Configure project_definitions below to match your domain.
    """
    state = get_default_hot_memory()
    
    # Detect project mentions
    projects = state.get("active_projects", [])
    message_lower = (user_message + " " + assistant_message).lower()
    
    # Project definitions: (trigger_keywords, project_key, default_description)
    # Customize this list for your domain - examples shown
    project_definitions = [
        # Example: Product/Platform projects
        (["mobile app", "ios app", "android app"], "Mobile App", "Mobile App - cross-platform development"),
        (["web platform", "web app"], "Web Platform", "Web Platform - frontend and backend development"),
        (["api", "backend"], "API Development", "API Development - service architecture and endpoints"),
        
        # Example: Content/Business projects
        (["blog", "content"], "Content Strategy", "Content Strategy - editorial calendar and publishing"),
        (["marketing", "campaign"], "Marketing", "Marketing - campaigns and growth initiatives"),
        (["documentation", "docs"], "Documentation", "Documentation - technical writing and guides"),
        
        # Example: Infrastructure/DevOps
        (["infrastructure", "infra", "deployment"], "Infrastructure", "Infrastructure - hosting, CI/CD, DevOps"),
        (["database", "db migration"], "Database", "Database - schema design and migrations"),
        (["security", "auth"], "Security", "Security - authentication, authorization, compliance"),
        
        # Example: AI/Memory (meta - for this project itself)
        (["smart memory", "memory system"], "Smart Memory", "Smart Memory - cognitive memory architecture"),
    ]
    
    for keywords, project_key, default_desc in project_definitions:
        # Check if any keyword matches
        if any(kw in message_lower for kw in keywords):
            # Check if project already exists
            if not _project_exists(projects, project_key):
                # Add with default description (or just key if no default)
                desc = default_desc or f"{project_key} - active project"
                projects.insert(0, desc)
    
    # Keep only top 5 active projects
    state["active_projects"] = projects[:5]
    
    # Detect working questions (questions that weren't immediately resolved)
    questions = state.get("working_questions", [])
    if "?" in user_message and len(user_message) > 20:
        # Extract the question
        question = user_message.strip()
        if question not in questions:
            questions.insert(0, question)
    
    # Keep only top 5 working questions
    state["working_questions"] = questions[:5]
    
    # Update agent state
    state["agent_state"]["status"] = "engaged"
    state["agent_state"]["last_interaction_timestamp"] = datetime.now(timezone.utc).isoformat()
    
    save_hot_memory(state)
    return state

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: hot_memory_manager.py <command> [args]")
        print("")
        print("Commands:")
        print("  get           - Show current hot memory state")
        print("  init          - Initialize with example context")
        print("  update        - Update specific fields (interactive)")
        print("  compose       - Get hot memory formatted for /compose API")
        print("  auto <user_msg> <asst_msg>  - Auto-update from conversation")
        print("")
        print("To customize project detection, edit project_definitions in auto_update_from_context()")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "get":
        state = get_default_hot_memory()
        print(json.dumps(state, indent=2, default=str))
    
    elif cmd == "init":
        # Initialize with generic example context
        state = update_hot_memory(
            active_projects=[
                "Example Project - description of current work",
                "Another Initiative - another project description",
                "Infrastructure - hosting and deployment tasks",
                "Documentation - technical writing and guides",
                "Research - exploratory work and learning"
            ],
            working_questions=[
                "What is the scope of the current milestone?",
                "How should we prioritize the backlog?",
                "What are the blockers for deployment?",
                "Which architecture pattern should we use?"
            ],
            top_of_mind=[
                "Review recent system changes",
                "Update project documentation",
                "Plan next development sprint"
            ],
            agent_status="engaged",
            last_background_task="initialization"
        )
        print("✓ Hot memory initialized with example context")
        print(json.dumps(state, indent=2, default=str))
    
    elif cmd == "compose":
        state = get_hot_memory_for_compose()
        print(json.dumps(state, indent=2, default=str))
    
    elif cmd == "auto" and len(sys.argv) >= 4:
        state = auto_update_from_context(sys.argv[2], sys.argv[3])
        print("✓ Auto-updated from conversation")
        print(json.dumps(state, indent=2, default=str))
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
