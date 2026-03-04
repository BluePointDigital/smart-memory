"""FastAPI server for the cognitive memory system.

Runs as a persistent local process so embedding models and DB connections stay hot.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from cognitive_memory_system import CognitiveMemorySystem
from ingestion.ingestion_pipeline import IncomingInteraction
from prompt_engine.schemas import PromptComposerRequest


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

    @app.get("/")
    async def root():
        return {"status": "ok", "service": "cognitive-memory-api"}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

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
