"""FastAPI server for the cognitive memory system.

Runs as a persistent local process so embedding models and DB connections stay hot.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Callable

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from cognitive_memory_system import CognitiveMemorySystem
from ingestion.ingestion_pipeline import IncomingInteraction
from prompt_engine.schemas import MemoryType, PromptComposerRequest


class RetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_message: str = Field(min_length=1)
    conversation_history: str = ""


class RunBackgroundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheduled: bool = True


def create_app(
    system_factory: Callable[[], CognitiveMemorySystem] = CognitiveMemorySystem,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Keep the full cognitive stack (including embedder) hot across requests.
        app.state.cognitive_system = system_factory()
        yield

    app = FastAPI(
        title="Cognitive Memory API",
        version="0.1.0",
        lifespan=lifespan,
    )

    def get_system(request: Request) -> CognitiveMemorySystem:
        system = getattr(request.app.state, "cognitive_system", None)
        if system is None:
            raise HTTPException(status_code=503, detail="Cognitive system not initialized")
        return system

    def resolve_embedder(system: CognitiveMemorySystem):
        for component_name in ("retrieval", "ingestion", "background"):
            component = getattr(system, component_name, None)
            if component is None:
                continue
            embedder = getattr(component, "embedder", None)
            if embedder is not None:
                return embedder
        return None

    def resolve_json_store(system: CognitiveMemorySystem):
        for component_name in ("retrieval", "ingestion", "background"):
            component = getattr(system, component_name, None)
            if component is None:
                continue
            store = getattr(component, "json_store", None)
            if store is not None:
                return store
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
    async def list_memories(
        request: Request,
        memory_type: str | None = Query(default=None, alias="type"),
    ):
        system = get_system(request)
        store = resolve_json_store(system)
        if store is None:
            raise HTTPException(status_code=503, detail="Memory store unavailable")

        selected_types = None
        if memory_type:
            try:
                selected_types = [MemoryType(memory_type.strip().lower())]
            except ValueError as error:
                allowed = ", ".join(memory.value for memory in MemoryType)
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid memory type '{memory_type}'. Allowed values: {allowed}",
                ) from error

        memories = store.list_memories(types=selected_types)
        return jsonable_encoder(memories)

    @app.get("/memory/{memory_id}")
    async def get_memory(memory_id: str, request: Request):
        system = get_system(request)
        store = resolve_json_store(system)
        if store is None:
            raise HTTPException(status_code=503, detail="Memory store unavailable")

        memory = store.get_memory(memory_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="Memory not found")

        return jsonable_encoder(memory)

    @app.get("/insights/pending")
    async def insights_pending(request: Request):
        system = get_system(request)
        hot_memory_manager = getattr(system, "hot_memory", None)
        if hot_memory_manager is None:
            raise HTTPException(status_code=503, detail="Hot memory unavailable")

        hot_memory = hot_memory_manager.get()
        now = datetime.now(timezone.utc)
        pending = [
            insight
            for insight in hot_memory.insight_queue
            if insight.expires_at is None or insight.expires_at >= now
        ]

        return jsonable_encoder({"count": len(pending), "insights": pending})

    @app.post("/ingest")
    async def ingest(interaction: IncomingInteraction, request: Request):
        system = get_system(request)
        result = system.ingest_interaction(interaction.model_dump(mode="json"))
        return jsonable_encoder(result)

    @app.post("/retrieve")
    async def retrieve(payload: RetrieveRequest, request: Request):
        system = get_system(request)
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

    return app


app = create_app()
