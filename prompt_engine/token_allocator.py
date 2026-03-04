"""Token budget allocation for prompt composition."""

from __future__ import annotations

from .schemas import InteractionState, TokenAllocation


def _normalize_percentages(percentages: dict[str, float]) -> dict[str, float]:
    total = sum(percentages.values())
    if total <= 0:
        raise ValueError("Token percentage total must be positive")
    return {key: (value / total) * 100.0 for key, value in percentages.items()}


def _allocate_exact_tokens(total_tokens: int, percentages: dict[str, float]) -> dict[str, int]:
    raw = {key: (total_tokens * percent / 100.0) for key, percent in percentages.items()}
    floor_tokens = {key: int(value) for key, value in raw.items()}

    assigned = sum(floor_tokens.values())
    remaining = total_tokens - assigned

    fractional = sorted(
        ((key, raw[key] - floor_tokens[key]) for key in raw),
        key=lambda item: item[1],
        reverse=True,
    )

    for index in range(max(0, remaining)):
        key = fractional[index % len(fractional)][0]
        floor_tokens[key] += 1

    return floor_tokens


def allocate_tokens(
    total_tokens: int,
    interaction_state: InteractionState,
    *,
    include_retrieved_memory: bool,
    include_insights: bool,
) -> TokenAllocation:
    """Allocate section budgets using interaction-state-aware percentages."""

    if interaction_state == InteractionState.ENGAGED:
        percentages = {
            "system_identity": 10,
            "temporal_state": 5,
            "working_memory": 10,
            "retrieved_memory": 15,
            "insight_queue": 0,
            "conversation_history": 60,
        }
    elif interaction_state == InteractionState.RETURNING:
        percentages = {
            "system_identity": 10,
            "temporal_state": 5,
            "working_memory": 10,
            "retrieved_memory": 30,
            "insight_queue": 5,
            "conversation_history": 40,
        }
    else:
        percentages = {
            "system_identity": 10,
            "temporal_state": 5,
            "working_memory": 5,
            "retrieved_memory": 10,
            "insight_queue": 0,
            "conversation_history": 70,
        }

    if not include_retrieved_memory:
        percentages["conversation_history"] += percentages["retrieved_memory"]
        percentages["retrieved_memory"] = 0

    if not include_insights:
        percentages["conversation_history"] += percentages["insight_queue"]
        percentages["insight_queue"] = 0

    percentages = _normalize_percentages(percentages)
    tokens = _allocate_exact_tokens(total_tokens, percentages)

    return TokenAllocation(total_tokens=total_tokens, **tokens)
