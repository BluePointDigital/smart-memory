from __future__ import annotations

from datetime import datetime, timezone

from cognition.associative_insight_generator import AssociativeInsightGenerator
from prompt_engine.schemas import EpisodicMemory, MemorySource


def test_curiosity_trigger_generates_working_question_insight():
    generator = AssociativeInsightGenerator()

    memory = EpisodicMemory(
        content="User was very frustrated by repeated deployment failures in proj_alpha.",
        importance_score=0.9,
        entities=["proj_alpha"],
        relations=[],
        emotional_valence=-0.8,
        emotional_intensity=0.95,
        source=MemorySource.CONVERSATION,
        source_session_id="sess_alpha",
        source_message_ids=["msg_alpha"],
        evidence_count=1,
        participants=["user", "assistant"],
        created_at=datetime.now(timezone.utc),
        last_accessed_at=datetime.now(timezone.utc),
        access_count=0,
    )

    result = generator.generate([memory])

    assert len(result.insights) >= 1
    assert any("Did they resolve it?" in insight.content for insight in result.insights)
    assert any(insight.confidence >= 0.65 for insight in result.insights)
