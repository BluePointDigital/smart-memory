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
        self.memory_store = StubMemoryStore()


class StubIngestionComponent:
    def __init__(self):
        self.embedder = StubEmbedder()
        self.memory_store = StubMemoryStore()


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
        return {"ok": True, "kind": "ingest", "payload": payload, "session_id": "sess_stub", "transcript_message_ids": ["msg_user", "msg_assistant"]}

    def append_transcript_message(self, payload):
        return {"ok": True, "kind": "transcript", "payload": payload, "session_id": payload.get("session_id") or "sess_stub", "transcript_message_ids": ["msg_single"]}

    def retrieve(self, query, *, include_history=False, entity_scope=None):
        return {
            "ok": True,
            "kind": "retrieve",
            "user_message": query,
            "include_history": include_history,
            "entity_scope": entity_scope or [],
        }

    def retrieve_context(self, user_message: str, conversation_history: str = ""):
        return {
            "ok": True,
            "kind": "retrieve_context",
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

    def get_transcript(self, session_id: str, start=None, end=None):
        return [{"session_id": session_id, "seq_num": 1, "message_id": "msg_single", "content": "hello", "role": "user", "source_type": "conversation", "created_at": "2026-03-04T00:00:00+00:00", "metadata": {}}]

    def get_message(self, message_id: str):
        if message_id == "missing":
            return None
        return {"message_id": message_id, "session_id": "sess_stub", "seq_num": 1, "content": "hello", "role": "user", "source_type": "conversation", "created_at": "2026-03-04T00:00:00+00:00", "metadata": {}}

    def get_memory_evidence(self, memory_id: str):
        return [{"memory_id": memory_id, "message_id": "msg_single", "evidence_kind": "direct"}]

    def get_memory_history(self, memory_id: str):
        return []

    def get_active_version(self, memory_id: str):
        return None

    def get_revision_chain(self, memory_id: str):
        return []

    def get_lane_contents(self, lane_name: str):
        return []

    def promote_memory(self, memory_id: str, lane_name: str):
        return None

    def demote_memory(self, memory_id: str, lane_name: str):
        return None

    def rebuild_all_memory_state(self):
        return {"scope": "full", "rebuilt_messages": 1, "rebuilt_memories": 1}

    def rebuild_from_transcripts(self, session_id: str | None = None):
        return {"scope": "session" if session_id else "full", "session_id": session_id, "rebuilt_messages": 1, "rebuilt_memories": 1}

    def run_eval_suite(self, suite_name: str):
        return []

    def run_eval_case(self, case_id: str):
        return []


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
        assert ingest_resp.json()["session_id"] == "sess_stub"

        transcript_resp = client.post(
            "/transcripts/message",
            json={"role": "user", "source_type": "conversation", "content": "hello"},
        )
        assert transcript_resp.status_code == 200
        assert transcript_resp.json()["kind"] == "transcript"

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

        transcript_get = client.get("/transcripts/sess_stub")
        assert transcript_get.status_code == 200
        assert transcript_get.json()[0]["session_id"] == "sess_stub"

        message_get = client.get("/transcript/message/msg_single")
        assert message_get.status_code == 200
        assert message_get.json()["message_id"] == "msg_single"

        evidence_get = client.get("/memory/mem_1/evidence")
        assert evidence_get.status_code == 200
        assert evidence_get.json()[0]["memory_id"] == "mem_1"

        rebuild_resp = client.post("/rebuild")
        assert rebuild_resp.status_code == 200
        assert rebuild_resp.json()["scope"] == "full"

        rebuild_session_resp = client.post("/rebuild/sess_stub")
        assert rebuild_session_resp.status_code == 200
        assert rebuild_session_resp.json()["session_id"] == "sess_stub"

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
