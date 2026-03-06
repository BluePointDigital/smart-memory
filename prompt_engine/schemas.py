"""Canonical data schemas for Smart Memory v3.1."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Any, Literal
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
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        populate_by_name=True,
    )


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    BELIEF = "belief"
    GOAL = "goal"
    PREFERENCE = "preference"
    IDENTITY = "identity"
    TASK_STATE = "task_state"


class MemorySource(str, Enum):
    CONVERSATION = "conversation"
    REFLECTION = "reflection"
    SYSTEM = "system"
    IMPORTED = "imported"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    UNCERTAIN = "uncertain"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class DecayPolicy(str, Enum):
    NONE = "none"
    TIME_SENSITIVE = "time_sensitive"
    GOAL_COMPLETION = "goal_completion"
    SESSION_BOUND = "session_bound"
    MANUAL_REVIEW = "manual_review"


class LaneName(str, Enum):
    CORE = "core"
    WORKING = "working"
    RETRIEVED = "retrieved"


class RevisionAction(str, Enum):
    ADD = "ADD"
    UPDATE = "UPDATE"
    SUPERSEDE = "SUPERSEDE"
    EXPIRE = "EXPIRE"
    MERGE = "MERGE"
    NOOP = "NOOP"
    REJECT = "REJECT"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


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
    memory_type: MemoryType
    content: str = Field(min_length=1)
    importance_score: UnitInterval = 0.5
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime | None = None
    last_accessed_at: datetime | None = None
    access_count: NonNegativeInt = 0
    schema_version: str = "3.1"
    source: MemorySource = MemorySource.CONVERSATION
    source_session_id: str | None = None
    source_message_ids: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    confidence: UnitInterval = 0.5
    status: MemoryStatus = MemoryStatus.ACTIVE
    revision_of: UUID | None = None
    supersedes: list[UUID] = Field(default_factory=list)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    decay_policy: DecayPolicy = DecayPolicy.NONE
    lane_eligibility: list[LaneName] = Field(default_factory=lambda: [LaneName.RETRIEVED])
    pinned_priority: UnitInterval = 0.0
    retrieval_tags: list[str] = Field(default_factory=list)
    explanation: str = ""
    relations: list[RelationTriple] = Field(default_factory=list)
    emotional_valence: SignedUnitInterval = 0.0
    emotional_intensity: UnitInterval = 0.0
    subject_entity_id: str | None = None
    attribute_family: str | None = None
    normalized_value: str | None = None
    state_label: str | None = None
    derivation_method: str = "transcript_message"
    evidence_summary: str = ""
    evidence_count: NonNegativeInt = 0
    rebuilt_at: datetime | None = None
    synthetic: bool = False

    @field_validator(
        "created_at",
        "updated_at",
        "last_accessed_at",
        "valid_from",
        "valid_to",
        "rebuilt_at",
        mode="before",
    )
    @classmethod
    def _normalize_datetime(cls, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise TypeError("Expected datetime or ISO datetime string")
        return _ensure_timezone(value)

    @field_validator("memory_type", mode="before")
    @classmethod
    def _normalize_memory_type(cls, value: Any) -> MemoryType:
        if isinstance(value, MemoryType):
            return value
        return MemoryType(str(value).strip().lower())

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: Any) -> MemoryStatus:
        if isinstance(value, MemoryStatus):
            return value
        return MemoryStatus(str(value).strip().lower())

    @field_validator("decay_policy", mode="before")
    @classmethod
    def _normalize_decay_policy(cls, value: Any) -> DecayPolicy:
        if isinstance(value, DecayPolicy):
            return value
        return DecayPolicy(str(value).strip().lower())

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("schema_version must not be empty")
        return cleaned

    @field_validator("source_session_id", mode="before")
    @classmethod
    def _normalize_session_id(cls, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("source_message_ids", "entities", "keywords", "retrieval_tags", mode="before")
    @classmethod
    def _default_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value]

    @field_validator("source_message_ids")
    @classmethod
    def _normalize_message_ids(cls, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = str(value).strip()
            if cleaned and cleaned not in seen:
                deduped.append(cleaned)
                seen.add(cleaned)
        return deduped

    @field_validator("entities")
    @classmethod
    def _normalize_entities(cls, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            entity_id = value.strip().lower().replace(" ", "_").replace("-", "_")
            if entity_id and entity_id not in seen:
                deduped.append(entity_id)
                seen.add(entity_id)
        return deduped

    @field_validator("keywords", "retrieval_tags")
    @classmethod
    def _normalize_text_list(cls, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = value.strip().lower()
            if cleaned and cleaned not in seen:
                deduped.append(cleaned)
                seen.add(cleaned)
        return deduped

    @field_validator("lane_eligibility", mode="before")
    @classmethod
    def _normalize_lanes(cls, value: Any) -> list[LaneName]:
        if value is None:
            return [LaneName.RETRIEVED]
        raw_values = [value] if isinstance(value, str) else list(value)
        lanes: list[LaneName] = []
        seen: set[LaneName] = set()
        for raw in raw_values:
            lane = raw if isinstance(raw, LaneName) else LaneName(str(raw).strip().lower())
            if lane not in seen:
                lanes.append(lane)
                seen.add(lane)
        return lanes or [LaneName.RETRIEVED]

    @model_validator(mode="after")
    def _apply_defaults(self) -> "BaseMemory":
        if self.updated_at is None:
            self.updated_at = self.created_at
        if self.last_accessed_at is None:
            self.last_accessed_at = self.created_at
        if self.valid_from is None:
            self.valid_from = self.created_at
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to must be >= valid_from")
        if self.evidence_count == 0 and self.source_message_ids:
            self.evidence_count = len(self.source_message_ids)
        return self

    @property
    def type(self) -> MemoryType:
        return self.memory_type

    @property
    def importance(self) -> float:
        return self.importance_score

    @property
    def last_accessed(self) -> datetime:
        return self.last_accessed_at or self.created_at

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(*args, **kwargs)


class EpisodicMemory(BaseMemory):
    memory_type: Literal[MemoryType.EPISODIC] = MemoryType.EPISODIC
    participants: list[str] = Field(default_factory=list)


class SemanticMemory(BaseMemory):
    memory_type: Literal[MemoryType.SEMANTIC] = MemoryType.SEMANTIC


class BeliefMemory(BaseMemory):
    memory_type: Literal[MemoryType.BELIEF] = MemoryType.BELIEF
    reinforced_count: Annotated[int, Field(ge=1)] = 1


class GoalMemory(BaseMemory):
    memory_type: Literal[MemoryType.GOAL] = MemoryType.GOAL
    goal_status: GoalStatus = GoalStatus.ACTIVE
    priority: UnitInterval = 0.5


class PreferenceMemory(BaseMemory):
    memory_type: Literal[MemoryType.PREFERENCE] = MemoryType.PREFERENCE


class IdentityMemory(BaseMemory):
    memory_type: Literal[MemoryType.IDENTITY] = MemoryType.IDENTITY


class TaskStateMemory(BaseMemory):
    memory_type: Literal[MemoryType.TASK_STATE] = MemoryType.TASK_STATE


LongTermMemory = BaseMemory


def _memory_model_from_value(payload: BaseMemory | dict[str, Any]) -> type[BaseMemory]:
    if isinstance(payload, BaseMemory):
        return payload.__class__

    raw_type = payload.get("memory_type", MemoryType.EPISODIC.value)
    memory_type = raw_type if isinstance(raw_type, MemoryType) else MemoryType(str(raw_type).strip().lower())
    mapping: dict[MemoryType, type[BaseMemory]] = {
        MemoryType.EPISODIC: EpisodicMemory,
        MemoryType.SEMANTIC: SemanticMemory,
        MemoryType.BELIEF: BeliefMemory,
        MemoryType.GOAL: GoalMemory,
        MemoryType.PREFERENCE: PreferenceMemory,
        MemoryType.IDENTITY: IdentityMemory,
        MemoryType.TASK_STATE: TaskStateMemory,
    }
    return mapping[memory_type]


def validate_long_term_memory(payload: BaseMemory | dict[str, Any]) -> BaseMemory:
    if isinstance(payload, BaseMemory):
        return payload
    model = _memory_model_from_value(payload)
    return model.model_validate(payload)


def validate_long_term_memories(payloads: list[BaseMemory | dict[str, Any]]) -> list[BaseMemory]:
    return [validate_long_term_memory(payload) for payload in payloads]


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
    core_memory: NonNegativeInt = 0
    working_memory: NonNegativeInt
    retrieved_memory: NonNegativeInt
    insight_queue: NonNegativeInt
    conversation_history: NonNegativeInt

    @model_validator(mode="after")
    def _validate_sum(self) -> "TokenAllocation":
        total = (
            self.system_identity
            + self.temporal_state
            + self.core_memory
            + self.working_memory
            + self.retrieved_memory
            + self.insight_queue
            + self.conversation_history
        )
        if total != self.total_tokens:
            raise ValueError(f"Token allocation mismatch: expected {self.total_tokens}, got {total}")
        return self


class MemoryInclusionTrace(StrictModel):
    memory_id: UUID
    lane: LaneName
    memory_type: MemoryType
    status: MemoryStatus
    inclusion_reason: str = Field(min_length=1)
    token_estimate: NonNegativeInt = 0


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
    core_memories: list[BaseMemory] = Field(default_factory=list)
    working_memories: list[BaseMemory] = Field(default_factory=list)
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

    @field_validator("core_memories", "working_memories", mode="before")
    @classmethod
    def _normalize_memories(cls, value: Any) -> list[BaseMemory]:
        if value is None:
            return []
        return validate_long_term_memories(list(value))


class PromptComposerOutput(StrictModel):
    prompt: str = Field(min_length=1)
    interaction_state: InteractionState
    temporal_state: TemporalState
    entities: list[str] = Field(default_factory=list)
    selected_memories: list[BaseMemory] = Field(default_factory=list)
    selected_insights: list[InsightObject] = Field(default_factory=list)
    token_allocation: TokenAllocation
    degraded_subsystems: list[str] = Field(default_factory=list)
    memory_traces: list[MemoryInclusionTrace] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
