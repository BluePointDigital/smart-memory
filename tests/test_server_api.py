from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from prompt_engine.schemas import AgentState, AgentStatus, HotMemory
from server import create_app


class StubEmbedder:
    model_name = "stub-embedder"

    def embed(self, text: str):
        return [0.0]


class StubMemoryStore:
    def list_memories(self, *, types=None, limit=None, created_after=None):
        return []

    def get_memory(self, memory_id: str):
        return None


class StubRetrievalComponent:
    def __init__(self):
        self.embedder = StubEmbedder()
        self.json_store = StubMemoryStore()


class StubIngestionComponent:
    def __init__(self):
        self.embedder = StubEmbedder()
        self.json_store = StubMemoryStore()


class StubHotMemoryManager:
    def get(self):
        now = datetime.now(timezone.utc)
        return HotMemory(
            agent_state=AgentState(
                status=AgentStatus.ENGAGED,
                last_interaction_timestamp=now,
                last_background_task="none",
            ),
            active_projects=[],
            working_questions=[],
            top_of_mind=[],
            insight_queue=[],
        )


class StubCognitiveSystem:
    def __init__(self):
        self.retrieval = StubRetrievalComponent()
        self.ingestion = StubIngestionComponent()
        self.hot_memory = StubHotMemoryManager()

    def ingest_interaction(self, payload):
        return {"ok": True, "kind": "ingest", "payload": payload}

    def retrieve_context(self, user_message: str, conversation_history: str = ""):
        return {
            "ok": True,
            "kind": "retrieve",
            "user_message": user_message,
            "conversation_history": conversation_history,
        }

    def compose_prompt(self, payload):
        return {
            "prompt": "<system>stub</system>",
            "interaction_state": "engaged",
            "temporal_state": {
                "current_timestamp": "2026-03-04T00:00:00+00:00",
                "time_since_last_interaction": "1m",
                "interaction_state": "engaged",
            },
            "entities": [],
            "selected_memories": [],
            "selected_insights": [],
            "token_allocation": {
                "total_tokens": 256,
                "system_identity": 26,
                "temporal_state": 13,
                "working_memory": 26,
                "retrieved_memory": 64,
                "insight_queue": 13,
                "conversation_history": 114,
            },
            "degraded_subsystems": [],
            "metadata": {},
        }

    def run_background_cycle(self, *, scheduled: bool = True):
        return {"ok": True, "kind": "background", "scheduled": scheduled}


def test_server_endpoints_with_stub_system():
    app = create_app(system_factory=StubCognitiveSystem)

    with TestClient(app) as client:
        health_resp = client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["embedder_loaded"] is True

        ingest_resp = client.post(
            "/ingest",
            json={
                "user_message": "hello world this is memory-worthy",
                "assistant_message": "ack",
                "source": "conversation",
                "participants": ["user", "assistant"],
                "active_projects": [],
                "metadata": {},
            },
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["kind"] == "ingest"

        retrieve_resp = client.post(
            "/retrieve",
            json={"user_message": "what did we decide", "conversation_history": ""},
        )
        assert retrieve_resp.status_code == 200
        assert retrieve_resp.json()["kind"] == "retrieve"

        compose_resp = client.post(
            "/compose",
            json={
                "agent_identity": "test-agent",
                "current_user_message": "hello",
                "conversation_history": "",
                "max_prompt_tokens": 256,
                "retrieval_timeout_ms": 500,
                "max_candidate_memories": 30,
                "max_selected_memories": 5,
            },
        )
        assert compose_resp.status_code == 200
        assert "prompt" in compose_resp.json()

        memories_resp = client.get("/memories")
        assert memories_resp.status_code == 200
        assert memories_resp.json() == []

        missing_memory_resp = client.get("/memory/not-found")
        assert missing_memory_resp.status_code == 404

        insights_resp = client.get("/insights/pending")
        assert insights_resp.status_code == 200
        assert insights_resp.json()["count"] == 0

        background_resp = client.post("/run_background", json={"scheduled": True})
        assert background_resp.status_code == 200
        assert background_resp.json()["kind"] == "background"
