"""Shared stop-reason classification for interactive match views."""

from __future__ import annotations

NORMAL_STOP_PREFIXES = ("hands_completed:", "negative_score:")
ERROR_STOP_PREFIXES = (
    "begin_round_failed:",
    "illegal_action:",
    "noop_wall_failed:",
    "parse_error",
    "step_failed:",
)
TRUNCATED_STOP_PREFIXES = ("max_player_steps",)


def starts_with_any(value: str, prefixes: tuple[str, ...]) -> bool:
    """Return whether ``value`` starts with any known stop-reason prefix."""
    return any(value.startswith(prefix) for prefix in prefixes)


def is_normal_stop_reason(reason: str) -> bool:
    """Stop reasons that represent a completed match or intentional stop."""
    return reason == "match_end" or starts_with_any(reason, NORMAL_STOP_PREFIXES)


def is_error_stop_reason(reason: str) -> bool:
    """Stop reasons that represent an execution failure."""
    return starts_with_any(reason, ERROR_STOP_PREFIXES)


def is_truncated_stop_reason(reason: str) -> bool:
    """Stop reasons that represent a step-limit truncation."""
    return starts_with_any(reason, TRUNCATED_STOP_PREFIXES)
