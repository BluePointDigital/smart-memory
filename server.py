"""FastAPI server for the transcript-first cognitive memory system."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Callable

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from cognitive_memory_system import CognitiveMemorySystem
from ingestion.ingestion_pipeline import IncomingInteraction, TranscriptMessageRequest
from prompt_engine.schemas import LaneName, MemoryType, PromptComposerRequest


class RetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_message: str = Field(min_length=1)
    conversation_history: str = ""
    include_history: bool = False
    entity_scope: list[str] = Field(default_factory=list)


class RunBackgroundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheduled: bool = True


class ReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory: dict


def create_app(system_factory: Callable[[], CognitiveMemorySystem] = CognitiveMemorySystem) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.cognitive_system = system_factory()
        yield

    app = FastAPI(title="Cognitive Memory API", version="0.3.1", lifespan=lifespan)

    def get_system(request: Request):
        system = getattr(request.app.state, "cognitive_system", None)
        if system is None:
            raise HTTPException(status_code=503, detail="Cognitive system not initialized")
        return system

    def resolve_embedder(system):
        for component_name in ("retrieval", "ingestion", "background"):
            component = getattr(system, component_name, None)
            if component is None:
                continue
            embedder = getattr(component, "embedder", None)
            if embedder is not None:
                return embedder
        return None

    def resolve_memory_store(system):
        store = getattr(system, "memory_store", None)
        if store is not None:
            return store
        for component_name in ("retrieval", "ingestion", "background"):
            component = getattr(system, component_name, None)
            if component is None:
                continue
            candidate = getattr(component, "memory_store", None) or getattr(component, "json_store", None)
            if candidate is not None:
                return candidate
        return None

    @app.get("/")
    async def root():
        return {"status": "ok", "service": "cognitive-memory-api"}

    @app.get("/health")
    async def health(request: Request):
        system = get_system(request)
        embedder = resolve_embedder(system)
        embedder_loaded = bool(embedder is not None and callable(getattr(embedder, "embed", None)))
        model_name = getattr(embedder, "model_name", None) if embedder is not None else None
        backend = embedder.__class__.__name__ if embedder is not None else None
        return {
            "status": "ok" if embedder_loaded else "degraded",
            "embedder_loaded": embedder_loaded,
            "embedder_model": model_name,
            "embedder_backend": backend,
        }

    @app.get("/memories")
    async def list_memories(request: Request, memory_type: str | None = Query(default=None, alias="type")):
        system = get_system(request)
        store = resolve_memory_store(system)
        if store is None:
            raise HTTPException(status_code=503, detail="Memory store unavailable")

        selected_types = None
        if memory_type:
            try:
                selected_types = [MemoryType(memory_type.strip().lower())]
            except ValueError as error:
                allowed = ", ".join(memory.value for memory in MemoryType)
                raise HTTPException(status_code=400, detail=f"Invalid memory type '{memory_type}'. Allowed values: {allowed}") from error
        memories = store.list_memories(types=selected_types)
        return jsonable_encoder(memories)

    @app.get("/memory/{memory_id}")
    async def get_memory(memory_id: str, request: Request):
        system = get_system(request)
        store = resolve_memory_store(system)
        if store is None:
            raise HTTPException(status_code=503, detail="Memory store unavailable")
        memory = store.get_memory(memory_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        return jsonable_encoder(memory)

    @app.get("/memory/{memory_id}/evidence")
    async def get_memory_evidence(memory_id: str, request: Request):
        system = get_system(request)
        return jsonable_encoder(system.get_memory_evidence(memory_id))

    @app.get("/memory/{memory_id}/history")
    async def get_memory_history(memory_id: str, request: Request):
        system = get_system(request)
        return jsonable_encoder(system.get_memory_history(memory_id))

    @app.get("/memory/{memory_id}/active")
    async def get_active_version(memory_id: str, request: Request):
        system = get_system(request)
        memory = system.get_active_version(memory_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="No active version found")
        return jsonable_encoder(memory)

    @app.get("/memory/{memory_id}/chain")
    async def get_revision_chain(memory_id: str, request: Request):
        system = get_system(request)
        return jsonable_encoder(system.get_revision_chain(memory_id))

    @app.get("/transcripts/{session_id}")
    async def get_transcript(session_id: str, request: Request, start: int | None = None, end: int | None = None):
        system = get_system(request)
        return jsonable_encoder(system.get_transcript(session_id, start=start, end=end))

    @app.get("/transcript/message/{message_id}")
    async def get_transcript_message(message_id: str, request: Request):
        system = get_system(request)
        message = system.get_message(message_id)
        if message is None:
            raise HTTPException(status_code=404, detail="Transcript message not found")
        return jsonable_encoder(message)

    @app.get("/insights/pending")
    async def insights_pending(request: Request):
        system = get_system(request)
        hot_memory = system.hot_memory.get()
        now = datetime.now(timezone.utc)
        pending = [insight for insight in hot_memory.insight_queue if insight.expires_at is None or insight.expires_at >= now]
        return jsonable_encoder({"count": len(pending), "insights": pending})

    @app.get("/lanes/{lane_name}")
    async def get_lane_contents(lane_name: str, request: Request):
        system = get_system(request)
        try:
            LaneName(lane_name)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Invalid lane") from error
        return jsonable_encoder(system.get_lane_contents(lane_name))

    @app.post("/lanes/{lane_name}/{memory_id}")
    async def promote_to_lane(lane_name: str, memory_id: str, request: Request):
        system = get_system(request)
        system.promote_memory(memory_id, lane_name)
        return {"ok": True, "lane": lane_name, "memory_id": memory_id}

    @app.delete("/lanes/{lane_name}/{memory_id}")
    async def demote_from_lane(lane_name: str, memory_id: str, request: Request):
        system = get_system(request)
        system.demote_memory(memory_id, lane_name)
        return {"ok": True, "lane": lane_name, "memory_id": memory_id}

    @app.post("/ingest")
    async def ingest(interaction: IncomingInteraction, request: Request):
        system = get_system(request)
        result = system.ingest_interaction(interaction.model_dump(mode="json"))
        return jsonable_encoder(result)

    @app.post("/transcripts/message")
    async def append_transcript(payload: TranscriptMessageRequest, request: Request):
        system = get_system(request)
        result = system.append_transcript_message(payload.model_dump(mode="json"))
        return jsonable_encoder(result)

    @app.post("/revise")
    async def revise(payload: ReviseRequest, request: Request):
        system = get_system(request)
        result = system.revise_memory(payload.memory)
        return jsonable_encoder(result)

    @app.post("/retrieve")
    async def retrieve(payload: RetrieveRequest, request: Request):
        system = get_system(request)
        if hasattr(system, "retrieve"):
            result = system.retrieve(
                payload.user_message,
                include_history=payload.include_history,
                entity_scope=payload.entity_scope,
            )
        else:
            result = system.retrieve_context(
                user_message=payload.user_message,
                conversation_history=payload.conversation_history,
            )
        return jsonable_encoder(result)

    @app.post("/compose")
    async def compose(payload: PromptComposerRequest, request: Request):
        system = get_system(request)
        result = system.compose_prompt(payload.model_dump(mode="json"))
        return jsonable_encoder(result)

    @app.post("/run_background")
    async def run_background(payload: RunBackgroundRequest, request: Request):
        system = get_system(request)
        result = system.run_background_cycle(scheduled=payload.scheduled)
        return jsonable_encoder(result)

    @app.post("/rebuild")
    async def rebuild(request: Request):
        system = get_system(request)
        return jsonable_encoder(system.rebuild_all_memory_state())

    @app.post("/rebuild/{session_id}")
    async def rebuild_session(session_id: str, request: Request):
        system = get_system(request)
        return jsonable_encoder(system.rebuild_from_transcripts(session_id=session_id))

    @app.get("/eval/suite/{suite_name}")
    async def run_eval_suite(suite_name: str, request: Request):
        system = get_system(request)
        return jsonable_encoder(system.run_eval_suite(suite_name))

    @app.get("/eval/case/{case_id}")
    async def run_eval_case(case_id: str, request: Request):
        system = get_system(request)
        return jsonable_encoder(system.run_eval_case(case_id))

    return app


app = create_app()

