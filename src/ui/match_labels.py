"""Shared match label formatting for UI surfaces."""

from __future__ import annotations


def format_match_target_label(target_hands: int) -> str:
    """Return a human-readable match target label."""
    if target_hands == 1:
        return "单局演示"
    if target_hands == 4:
        return "东风战"
    if target_hands == 8:
        return "半庄/南风战"
    return f"{target_hands}局自定义"
