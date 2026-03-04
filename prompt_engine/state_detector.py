"""Interaction state detection and temporal-state helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .schemas import InteractionState, TemporalState


@dataclass(frozen=True)
class StateDetectorConfig:
    engaged_window_minutes: int = 15
    idle_max_words: int = 4


FUNCTIONAL_PREFIXES = (
    "--",
    "/",
    "status",
    "sync",
    "search",
    "get",
    "mode",
    "help",
)


def detect_interaction_state(
    current_user_message: str,
    last_interaction_timestamp: datetime | None,
    now: datetime | None = None,
    config: StateDetectorConfig = StateDetectorConfig(),
) -> InteractionState:
    """Classify interaction state using time delta and command-like heuristics."""

    now = now or datetime.now(timezone.utc)
    message = current_user_message.strip().lower()

    if not message:
        return InteractionState.IDLE

    words = message.split()
    if len(words) <= config.idle_max_words and (
        message.startswith(FUNCTIONAL_PREFIXES)
        or words[0] in FUNCTIONAL_PREFIXES
    ):
        return InteractionState.IDLE

    if last_interaction_timestamp is None:
        return InteractionState.RETURNING

    delta_seconds = max(0.0, (now - last_interaction_timestamp).total_seconds())
    if delta_seconds <= config.engaged_window_minutes * 60:
        return InteractionState.ENGAGED

    return InteractionState.RETURNING


def _humanize_delta(seconds: int) -> str:
    if seconds <= 0:
        return "0m"

    minutes = seconds // 60
    hours, rem_minutes = divmod(minutes, 60)
    days, rem_hours = divmod(hours, 24)

    if days > 0:
        return f"{days}d {rem_hours}h"
    if hours > 0:
        return f"{hours}h {rem_minutes}m"
    return f"{minutes}m"


def build_temporal_state(
    current_user_message: str,
    last_interaction_timestamp: datetime | None,
    now: datetime | None = None,
    config: StateDetectorConfig = StateDetectorConfig(),
) -> TemporalState:
    """Build canonical temporal state contract for prompt composition."""

    now = now or datetime.now(timezone.utc)

    if last_interaction_timestamp is None:
        delta_seconds = 0
    else:
        delta_seconds = int(max(0.0, (now - last_interaction_timestamp).total_seconds()))

    interaction_state = detect_interaction_state(
        current_user_message=current_user_message,
        last_interaction_timestamp=last_interaction_timestamp,
        now=now,
        config=config,
    )

    if last_interaction_timestamp is None:
        time_gap = "first interaction"
    else:
        time_gap = _humanize_delta(delta_seconds)

    return TemporalState(
        current_timestamp=now,
        time_since_last_interaction=time_gap,
        interaction_state=interaction_state,
    )
