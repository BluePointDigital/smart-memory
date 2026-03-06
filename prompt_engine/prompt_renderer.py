"""Prompt rendering with strict prompt-level token enforcement."""

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


def _max_words_for_budget(token_budget: int) -> int:
    return max(1, int(token_budget / 1.33))


def _truncate_to_budget(text: str, token_budget: int, *, keep_tail: bool = False) -> str:
    if token_budget <= 0:
        return ""

    words = text.split()
    if not words:
        return ""

    max_words = _max_words_for_budget(token_budget)
    if len(words) <= max_words:
        return text.strip()

    if keep_tail:
        clipped = " ".join(words[-max_words:])
        return f"... {clipped}" if clipped else ""

    clipped = " ".join(words[:max_words])
    return f"{clipped} ..." if clipped else ""


def _trim_oldest_words(text: str, words_to_drop: int = 24) -> str:
    words = text.split()
    if not words:
        return ""
    if len(words) <= words_to_drop:
        return ""

    remaining = " ".join(words[words_to_drop:])
    return f"... {remaining}" if remaining else ""


def _select_items_for_budget(items: list[str], token_budget: int) -> list[str]:
    if token_budget <= 0:
        return []

    selected: list[str] = []
    used = 0
    for raw_item in items:
        item = raw_item.strip()
        if not item:
            continue

        remaining = token_budget - used
        if remaining <= 0:
            break

        bounded = _truncate_to_budget(item, min(remaining, 48))
        if not bounded:
            continue

        cost = estimate_tokens(f"- {bounded}")
        if used + cost > token_budget:
            break

        selected.append(bounded)
        used += cost

    return selected


def _memory_lines_for_budget(memories: list[LongTermMemory], token_budget: int) -> list[str]:
    if token_budget <= 0:
        return []

    lines: list[str] = []
    used = 0
    for memory in memories:
        remaining = token_budget - used
        if remaining <= 0:
            break

        content = _truncate_to_budget(memory.content.strip(), min(remaining, 96))
        if not content:
            continue

        line = f"[{memory.memory_type.value}|{memory.status.value}] {content}"
        cost = estimate_tokens(line)
        if used + cost > token_budget:
            break

        lines.append(line)
        used += cost

    return lines


def _insight_lines_for_budget(interaction_state: InteractionState, insights: list[InsightObject], token_budget: int) -> list[str]:
    if interaction_state != InteractionState.RETURNING or token_budget <= 0:
        return []

    lines: list[str] = []
    used = 0
    for insight in insights:
        remaining = token_budget - used
        if remaining <= 0:
            break

        content = _truncate_to_budget(insight.content.strip(), min(remaining, 80))
        if not content:
            continue

        line = f"- {content} (confidence: {insight.confidence:.2f})"
        cost = estimate_tokens(line)
        if used + cost > token_budget:
            break

        lines.append(line)
        used += cost

    return lines


def _render_bullets(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def _temporal_text(temporal_state: TemporalState, mode: int) -> str:
    if mode <= 0:
        return ""
    if mode == 1:
        return f"Interaction State: {temporal_state.interaction_state.value}"
    if mode == 2:
        return (
            f"Time Since Last Interaction: {temporal_state.time_since_last_interaction}\n"
            f"Interaction State: {temporal_state.interaction_state.value}"
        )
    return (
        f"Current Time: {temporal_state.current_timestamp.isoformat()}\n"
        f"Time Since Last Interaction: {temporal_state.time_since_last_interaction}\n"
        f"Interaction State: {temporal_state.interaction_state.value}"
    )


def _build_prompt(
    *,
    identity_text: str,
    temporal_text: str,
    core_lines: list[str],
    active_projects: list[str],
    working_questions: list[str],
    top_of_mind: list[str],
    insight_lines: list[str],
    retrieved_lines: list[str],
    conversation_text: str,
    current_user_message: str,
) -> str:
    working_context = (
        "Active Projects:\n"
        f"{_render_bullets(active_projects)}\n\n"
        "Working Questions:\n"
        f"{_render_bullets(working_questions)}\n\n"
        "Current Focus / Goals:\n"
        f"{_render_bullets(top_of_mind)}"
    )

    parts: list[str] = ["<system>", "", "[AGENT IDENTITY]", identity_text or "N/A", "", "[TEMPORAL STATE]", temporal_text or "N/A", ""]
    if core_lines:
        parts.extend(["[CORE MEMORY]", "", "\n".join(core_lines), ""])
    parts.extend(["[WORKING CONTEXT]", working_context, "", "</system>", ""])

    if insight_lines:
        parts.extend(["[BACKGROUND INSIGHTS]", "The following insights were generated during background reflection cycles.", "", "\n".join(insight_lines), ""])

    if retrieved_lines:
        parts.extend(["[RETRIEVED MEMORY]", "", "\n".join(retrieved_lines), ""])

    parts.extend(["<user>", "", "[RECENT CONVERSATION]", conversation_text or "N/A", "", current_user_message.strip() or "N/A", "", "</user>", "", "<assistant>"])
    return "\n".join(parts)


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
    core_memories: list[LongTermMemory] | None = None,
    allow_core_trim: bool = False,
) -> str:
    """Render the final prompt and strictly enforce max_prompt_tokens."""

    identity_text = _truncate_to_budget(agent_identity.strip(), token_allocation.system_identity)
    temporal_mode = 3

    core_lines = _memory_lines_for_budget(core_memories or [], token_allocation.core_memory)
    working_budget = token_allocation.working_memory
    active_projects = _select_items_for_budget(hot_memory.active_projects, max(0, int(working_budget * 0.35)))
    working_questions = _select_items_for_budget(hot_memory.working_questions, max(0, int(working_budget * 0.30)))
    top_of_mind = _select_items_for_budget(hot_memory.top_of_mind, max(0, working_budget - int(working_budget * 0.35) - int(working_budget * 0.30)))

    insight_lines = _insight_lines_for_budget(temporal_state.interaction_state, selected_insights, token_allocation.insight_queue)
    retrieved_lines = _memory_lines_for_budget(retrieved_memories, token_allocation.retrieved_memory)

    conversation_text = _truncate_to_budget(conversation_history.strip(), token_allocation.conversation_history, keep_tail=True)
    current_message = _truncate_to_budget(current_user_message.strip(), max(32, token_allocation.conversation_history))
    max_prompt_tokens = token_allocation.total_tokens

    for _ in range(1024):
        temporal_text = _truncate_to_budget(_temporal_text(temporal_state, temporal_mode), token_allocation.temporal_state)
        prompt = _build_prompt(
            identity_text=identity_text,
            temporal_text=temporal_text,
            core_lines=core_lines,
            active_projects=active_projects,
            working_questions=working_questions,
            top_of_mind=top_of_mind,
            insight_lines=insight_lines,
            retrieved_lines=retrieved_lines,
            conversation_text=conversation_text,
            current_user_message=current_message,
        )

        if estimate_tokens(prompt) <= max_prompt_tokens:
            return prompt

        if conversation_text:
            conversation_text = _trim_oldest_words(conversation_text, 24)
            continue
        if retrieved_lines:
            retrieved_lines.pop()
            continue
        if insight_lines:
            insight_lines.pop()
            continue
        if top_of_mind:
            top_of_mind.pop()
            continue
        if working_questions:
            working_questions.pop()
            continue
        if active_projects:
            active_projects.pop()
            continue
        if core_lines and allow_core_trim:
            core_lines.pop()
            continue
        if temporal_mode > 0:
            temporal_mode -= 1
            continue
        break

    return prompt
