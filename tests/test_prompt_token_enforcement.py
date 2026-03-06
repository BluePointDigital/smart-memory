from __future__ import annotations

from datetime import datetime, timezone

from prompt_engine.prompt_renderer import estimate_tokens, render_prompt
from prompt_engine.schemas import (
    AgentState,
    AgentStatus,
    EpisodicMemory,
    HotMemory,
    InsightObject,
    InteractionState,
    MemorySource,
    TemporalState,
)
from prompt_engine.token_allocator import allocate_tokens


def test_prompt_renderer_enforces_total_token_cap_with_priority_trimming():
    now = datetime.now(timezone.utc)

    temporal_state = TemporalState(
        current_timestamp=now,
        time_since_last_interaction="3 days",
        interaction_state=InteractionState.RETURNING,
    )

    hot_memory = HotMemory(
        agent_state=AgentState(
            status=AgentStatus.RETURNING,
            last_interaction_timestamp=now,
            last_background_task="reflection",
        ),
        active_projects=[f"proj_{i}" for i in range(15)],
        working_questions=[f"question {i} about unresolved blocker" for i in range(12)],
        top_of_mind=[f"top of mind item {i} with long context payload" for i in range(25)],
        insight_queue=[],
    )

    retrieved_memories = [
        EpisodicMemory(
            content=f"retrieved memory {i} " + ("important detail " * 30),
            importance_score=0.8,
            source=MemorySource.CONVERSATION,
            source_session_id="sess_tokens",
            source_message_ids=[f"msg_{i}"],
            evidence_count=1,
            entities=["proj_tokens"],
            participants=["user", "assistant"],
        )
        for i in range(8)
    ]

    selected_insights = [
        InsightObject(
            content=f"insight {i} " + ("background pattern " * 20),
            confidence=0.9,
            source_memory_ids=[],
            generated_at=now,
        )
        for i in range(6)
    ]

    allocation = allocate_tokens(
        total_tokens=256,
        interaction_state=InteractionState.RETURNING,
        include_retrieved_memory=True,
        include_insights=True,
    )

    prompt = render_prompt(
        agent_identity="Persistent Identity Anchor",
        temporal_state=temporal_state,
        hot_memory=hot_memory,
        retrieved_memories=retrieved_memories,
        selected_insights=selected_insights,
        conversation_history="oldest " * 600,
        current_user_message="current request " + ("with lots of detail " * 80),
        token_allocation=allocation,
    )

    assert estimate_tokens(prompt) <= allocation.total_tokens
    assert "Persistent Identity Anchor" in prompt
