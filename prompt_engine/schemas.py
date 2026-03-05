"""Canonical data schemas for the cognitive memory architecture.

Phase 1 scope:
- Strict Pydantic models for long-term memory, working memory, insights, and composer contracts.
- No storage, retrieval backend, or vector/index implementation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Any, Literal, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


UnitInterval = Annotated[float, Field(ge=0.0, le=1.0)]
SignedUnitInterval = Annotated[float, Field(ge=-1.0, le=1.0)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    BELIEF = "belief"
    GOAL = "goal"


class MemorySource(str, Enum):
    CONVERSATION = "conversation"
    REFLECTION = "reflection"
    SYSTEM = "system"
    IMPORTED = "imported"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class InteractionState(str, Enum):
    ENGAGED = "engaged"
    RETURNING = "returning"
    IDLE = "idle"


class AgentStatus(str, Enum):
    ENGAGED = "engaged"
    IDLE = "idle"
    RETURNING = "returning"
    SLEEPING = "sleeping"


class RelationTriple(StrictModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object: str = Field(min_length=1)


class BaseMemory(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    type: MemoryType
    content: str = Field(min_length=1)
    importance: UnitInterval
    created_at: datetime = Field(default_factory=_utc_now)
    last_accessed: datetime = Field(default_factory=_utc_now)
    access_count: NonNegativeInt = 0
    schema_version: str = Field(default="2.0")
    entities: list[str] = Field(default_factory=list)
    relations: list[RelationTriple] = Field(default_factory=list)
    emotional_valence: SignedUnitInterval = 0.0
    emotional_intensity: UnitInterval = 0.0
    source: MemorySource

    @field_validator("created_at", "last_accessed", mode="before")
    @classmethod
    def _normalize_datetime(cls, value: Any) -> datetime:
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise TypeError("Expected datetime or ISO datetime string")
        return _ensure_timezone(value)

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("schema_version must not be empty")
        return value

    @field_validator("entities")
    @classmethod
    def _validate_entities(cls, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()

        for value in values:
            if not value:
                continue
            entity_id = value.strip().lower().replace(" ", "_")
            if entity_id and entity_id not in seen:
                deduped.append(entity_id)
                seen.add(entity_id)

        return deduped


class EpisodicMemory(BaseMemory):
    type: Literal[MemoryType.EPISODIC] = MemoryType.EPISODIC
    participants: list[str] = Field(default_factory=list)


class SemanticMemory(BaseMemory):
    type: Literal[MemoryType.SEMANTIC] = MemoryType.SEMANTIC
    confidence: UnitInterval


class BeliefMemory(BaseMemory):
    type: Literal[MemoryType.BELIEF] = MemoryType.BELIEF
    confidence: UnitInterval
    reinforced_count: Annotated[int, Field(ge=1)] = 1


class GoalMemory(BaseMemory):
    type: Literal[MemoryType.GOAL] = MemoryType.GOAL
    status: GoalStatus
    priority: UnitInterval


LongTermMemory = Annotated[
    Union[EpisodicMemory, SemanticMemory, BeliefMemory, GoalMemory],
    Field(discriminator="type"),
]


class InsightObject(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    content: str = Field(min_length=1)
    confidence: UnitInterval
    source_memory_ids: list[UUID] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=_utc_now)
    expires_at: datetime | None = None

    @field_validator("generated_at", "expires_at", mode="before")
    @classmethod
    def _normalize_datetime(cls, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise TypeError("Expected datetime or ISO datetime string")
        return _ensure_timezone(value)

    @model_validator(mode="after")
    def _default_expiry(self) -> "InsightObject":
        if self.expires_at is None:
            self.expires_at = self.generated_at + timedelta(hours=24)
        return self


class AgentState(StrictModel):
    status: AgentStatus
    last_interaction_timestamp: datetime
    last_background_task: str = Field(min_length=1)

    @field_validator("last_interaction_timestamp", mode="before")
    @classmethod
    def _normalize_datetime(cls, value: Any) -> datetime:
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise TypeError("Expected datetime or ISO datetime string")
        return _ensure_timezone(value)


class HotMemory(StrictModel):
    agent_state: AgentState
    active_projects: list[str] = Field(default_factory=list)
    working_questions: list[str] = Field(default_factory=list)
    top_of_mind: list[str] = Field(default_factory=list)
    insight_queue: list[InsightObject] = Field(default_factory=list)


class TemporalState(StrictModel):
    current_timestamp: datetime
    time_since_last_interaction: str = Field(min_length=1)
    interaction_state: InteractionState

    @field_validator("current_timestamp", mode="before")
    @classmethod
    def _normalize_datetime(cls, value: Any) -> datetime:
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise TypeError("Expected datetime or ISO datetime string")
        return _ensure_timezone(value)


class TokenAllocation(StrictModel):
    total_tokens: Annotated[int, Field(ge=1)]
    system_identity: NonNegativeInt
    temporal_state: NonNegativeInt
    working_memory: NonNegativeInt
    retrieved_memory: NonNegativeInt
    insight_queue: NonNegativeInt
    conversation_history: NonNegativeInt

    @model_validator(mode="after")
    def _validate_sum(self) -> "TokenAllocation":
        total = (
            self.system_identity
            + self.temporal_state
            + self.working_memory
            + self.retrieved_memory
            + self.insight_queue
            + self.conversation_history
        )
        if total != self.total_tokens:
            raise ValueError(
                f"Token allocation mismatch: expected {self.total_tokens}, got {total}"
            )
        return self



def _default_hot_memory() -> HotMemory:
    now = _utc_now()
    return HotMemory(
        agent_state=AgentState(
            status=AgentStatus.IDLE,
            last_interaction_timestamp=now,
            last_background_task="none",
        ),
        active_projects=[],
        working_questions=[],
        top_of_mind=[],
        insight_queue=[],
    )

class PromptComposerRequest(StrictModel):
    agent_identity: str = Field(min_length=1)
    current_user_message: str = Field(min_length=1)
    conversation_history: str = ""
    last_interaction_timestamp: datetime | None = None
    hot_memory: HotMemory = Field(default_factory=_default_hot_memory)
    max_prompt_tokens: Annotated[int, Field(ge=256)] = 8192
    retrieval_timeout_ms: Annotated[int, Field(ge=50, le=10000)] = 500
    max_candidate_memories: Annotated[int, Field(ge=1, le=100)] = 30
    max_selected_memories: Annotated[int, Field(ge=1, le=20)] = 5

    @field_validator("last_interaction_timestamp", mode="before")
    @classmethod
    def _normalize_datetime(cls, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise TypeError("Expected datetime or ISO datetime string")
        return _ensure_timezone(value)


class PromptComposerOutput(StrictModel):
    prompt: str = Field(min_length=1)
    interaction_state: InteractionState
    temporal_state: TemporalState
    entities: list[str] = Field(default_factory=list)
    selected_memories: list[LongTermMemory] = Field(default_factory=list)
    selected_insights: list[InsightObject] = Field(default_factory=list)
    token_allocation: TokenAllocation
    degraded_subsystems: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


