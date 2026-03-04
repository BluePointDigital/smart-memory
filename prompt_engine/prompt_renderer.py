"""Prompt rendering with section-level token budgeting.

Token counting is approximate (word-based) to stay dependency-free.
"""

from __future__ import annotations

import math

from .schemas import (
    HotMemory,
    InsightObject,
    InteractionState,
    LongTermMemory,
    TemporalState,
    TokenAllocation,
)


def estimate_tokens(text: str) -> int:
    words = len(text.split())
    if words == 0:
        return 0
    return max(1, math.ceil(words * 1.33))


def _truncate_to_budget(text: str, token_budget: int) -> str:
    if token_budget <= 0:
        return ""

    words = text.split()
    if not words:
        return ""

    max_words = max(1, int(token_budget / 1.33))
    if len(words) <= max_words:
        return text

    clipped = " ".join(words[: max(1, max_words - 1)])
    return f"{clipped} ..."


def _render_bullets(items: list[str], token_budget: int) -> str:
    if token_budget <= 0 or not items:
        return "- none"

    lines: list[str] = []
    used = 0
    for item in items:
        candidate = f"- {item.strip()}"
        candidate_tokens = estimate_tokens(candidate)
        if used + candidate_tokens > token_budget:
            break
        lines.append(candidate)
        used += candidate_tokens

    return "\n".join(lines) if lines else "- none"


def _render_retrieved_memories(
    memories: list[LongTermMemory],
    token_budget: int,
) -> str:
    if token_budget <= 0 or not memories:
        return ""

    lines: list[str] = []
    used = 0

    for memory in memories:
        line = f"[{memory.type.value}] {memory.content.strip()}"
        line_tokens = estimate_tokens(line)

        if used + line_tokens > token_budget:
            break

        lines.append(line)
        used += line_tokens

    return "\n".join(lines)


def _render_insights(
    interaction_state: InteractionState,
    insights: list[InsightObject],
    token_budget: int,
) -> str:
    if interaction_state != InteractionState.RETURNING:
        return ""
    if token_budget <= 0 or not insights:
        return ""

    lines: list[str] = []
    used = 0

    for insight in insights:
        line = f"- {insight.content.strip()} (confidence: {insight.confidence:.2f})"
        line_tokens = estimate_tokens(line)

        if used + line_tokens > token_budget:
            break

        lines.append(line)
        used += line_tokens

    if not lines:
        return ""

    return "\n".join(lines)


def render_prompt(
    *,
    agent_identity: str,
    temporal_state: TemporalState,
    hot_memory: HotMemory,
    retrieved_memories: list[LongTermMemory],
    selected_insights: list[InsightObject],
    conversation_history: str,
    current_user_message: str,
    token_allocation: TokenAllocation,
) -> str:
    """Render the final master prompt with section-level budget controls."""

    identity_text = _truncate_to_budget(
        agent_identity.strip(), token_allocation.system_identity
    )

    temporal_text = (
        f"Current Time: {temporal_state.current_timestamp.isoformat()}\n"
        f"Time Since Last Interaction: {temporal_state.time_since_last_interaction}\n"
        f"Interaction State: {temporal_state.interaction_state.value}"
    )
    temporal_text = _truncate_to_budget(temporal_text, token_allocation.temporal_state)

    working_context = (
        "Active Projects:\n"
        f"{_render_bullets(hot_memory.active_projects, token_allocation.working_memory // 2)}\n\n"
        "Current Focus / Goals:\n"
        f"{_render_bullets(hot_memory.top_of_mind, token_allocation.working_memory // 2)}"
    )
    working_context = _truncate_to_budget(working_context, token_allocation.working_memory)

    insights_text = _render_insights(
        interaction_state=temporal_state.interaction_state,
        insights=selected_insights,
        token_budget=token_allocation.insight_queue,
    )

    retrieved_text = _render_retrieved_memories(
        memories=retrieved_memories,
        token_budget=token_allocation.retrieved_memory,
    )

    conversation_text = _truncate_to_budget(
        conversation_history.strip(), token_allocation.conversation_history
    )

    parts: list[str] = []
    parts.append("<system>")
    parts.append("")
    parts.append("[AGENT IDENTITY]")
    parts.append(identity_text or "N/A")
    parts.append("")
    parts.append("[TEMPORAL STATE]")
    parts.append(temporal_text or "N/A")
    parts.append("")
    parts.append("[WORKING CONTEXT]")
    parts.append(working_context or "N/A")
    parts.append("")
    parts.append("</system>")
    parts.append("")

    if insights_text:
        parts.append("[BACKGROUND INSIGHTS]")
        parts.append("The following insights were generated during background reflection cycles.")
        parts.append("")
        parts.append(insights_text)
        parts.append("")

    if retrieved_text:
        parts.append("[RELEVANT LONG-TERM MEMORY]")
        parts.append("")
        parts.append(retrieved_text)
        parts.append("")

    parts.append("<user>")
    parts.append("")
    parts.append("[RECENT CONVERSATION]")
    parts.append(conversation_text or "N/A")
    parts.append("")
    parts.append(current_user_message.strip())
    parts.append("")
    parts.append("</user>")
    parts.append("")
    parts.append("<assistant>")

    return "\n".join(parts)
