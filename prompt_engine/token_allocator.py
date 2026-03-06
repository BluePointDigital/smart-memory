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


def _apply_minimums(tokens: dict[str, int], minimums: dict[str, int]) -> dict[str, int]:
    adjusted = dict(tokens)
    for section, minimum in minimums.items():
        minimum = max(0, int(minimum))
        current = adjusted.get(section, 0)
        if current >= minimum:
            continue

        deficit = minimum - current
        adjusted[section] = minimum

        donors = sorted(
            (name for name in adjusted if name != section and adjusted[name] > minimums.get(name, 0)),
            key=lambda name: adjusted[name],
            reverse=True,
        )

        for donor in donors:
            available = adjusted[donor] - minimums.get(donor, 0)
            if available <= 0:
                continue

            take = min(available, deficit)
            adjusted[donor] -= take
            deficit -= take

            if deficit == 0:
                break

        if deficit > 0:
            raise ValueError("Unable to satisfy token minimum constraints")

    return adjusted


def allocate_tokens(
    total_tokens: int,
    interaction_state: InteractionState,
    *,
    include_retrieved_memory: bool,
    include_insights: bool,
    include_core_memory: bool = False,
) -> TokenAllocation:
    """Allocate section budgets using interaction-state-aware percentages."""

    if interaction_state == InteractionState.ENGAGED:
        percentages = {
            "system_identity": 10,
            "temporal_state": 5,
            "core_memory": 10,
            "working_memory": 12,
            "retrieved_memory": 13,
            "insight_queue": 0,
            "conversation_history": 50,
        }
    elif interaction_state == InteractionState.RETURNING:
        percentages = {
            "system_identity": 10,
            "temporal_state": 5,
            "core_memory": 12,
            "working_memory": 12,
            "retrieved_memory": 26,
            "insight_queue": 5,
            "conversation_history": 30,
        }
    else:
        percentages = {
            "system_identity": 10,
            "temporal_state": 5,
            "core_memory": 10,
            "working_memory": 8,
            "retrieved_memory": 12,
            "insight_queue": 0,
            "conversation_history": 55,
        }

    if not include_core_memory:
        percentages["conversation_history"] += percentages["core_memory"]
        percentages["core_memory"] = 0

    if not include_retrieved_memory:
        percentages["conversation_history"] += percentages["retrieved_memory"]
        percentages["retrieved_memory"] = 0

    if not include_insights:
        percentages["conversation_history"] += percentages["insight_queue"]
        percentages["insight_queue"] = 0

    percentages = _normalize_percentages(percentages)
    tokens = _allocate_exact_tokens(total_tokens, percentages)
    tokens = _apply_minimums(
        tokens,
        {
            "system_identity": 1,
            "conversation_history": 1,
        },
    )

    return TokenAllocation(total_tokens=total_tokens, **tokens)
