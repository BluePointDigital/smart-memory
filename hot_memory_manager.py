#!/usr/bin/env python3
"""
Hot Memory Manager compatibility helper for Smart Memory v3.1.

This helper maintains a file-backed hot-memory projection for older local workflows.
It is not canonical truth in the transcript-first runtime.
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
    
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/insights/pending", method='GET')
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode('utf-8'))
            insights = data.get("insights", [])
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
        existing_key = project.split(" - ")[0].lower() if " - " in project else project.lower()
        if existing_key == project_key_lower:
            return True
    return False

def auto_update_from_context(user_message: str, assistant_message: str):
    """Automatically update hot memory based on conversation content.
    
    Configure project_definitions below to match your domain.
    """
    state = get_default_hot_memory()
    
    projects = state.get("active_projects", [])
    message_lower = (user_message + " " + assistant_message).lower()
    
    project_definitions = [
        (["mobile app", "ios app", "android app"], "Mobile App", "Mobile App - cross-platform development"),
        (["web platform", "web app"], "Web Platform", "Web Platform - frontend and backend development"),
        (["api", "backend"], "API Development", "API Development - service architecture and endpoints"),
        (["blog", "content"], "Content Strategy", "Content Strategy - editorial calendar and publishing"),
        (["marketing", "campaign"], "Marketing", "Marketing - campaigns and growth initiatives"),
        (["documentation", "docs"], "Documentation", "Documentation - technical writing and guides"),
        (["infrastructure", "infra", "deployment"], "Infrastructure", "Infrastructure - hosting, CI/CD, DevOps"),
        (["database", "db migration"], "Database", "Database - schema design and migrations"),
        (["security", "auth"], "Security", "Security - authentication, authorization, compliance"),
        (["smart memory", "memory system"], "Smart Memory", "Smart Memory - transcript-first cognitive memory architecture"),
    ]
    
    for keywords, project_key, default_desc in project_definitions:
        if any(kw in message_lower for kw in keywords):
            if not _project_exists(projects, project_key):
                desc = default_desc or f"{project_key} - active project"
                projects.insert(0, desc)
    
    state["active_projects"] = projects[:5]
    
    questions = state.get("working_questions", [])
    if "?" in user_message and len(user_message) > 20:
        question = user_message.strip()
        if question not in questions:
            questions.insert(0, question)
    
    state["working_questions"] = questions[:5]
    state["agent_state"]["status"] = "engaged"
    state["agent_state"]["last_interaction_timestamp"] = datetime.now(timezone.utc).isoformat()
    save_hot_memory(state)
    return state
