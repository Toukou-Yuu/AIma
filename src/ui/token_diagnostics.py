"""Shared UI formatting helpers for prompt token diagnostics."""

from __future__ import annotations

_PROMPT_BLOCK_LABELS = {
    "system": "系统",
    "match_archive": "本场摘要",
    "public_history": "公共事件",
    "self_history": "我的历史",
    "current_turn": "当前决策",
}


def format_prompt_block_label(block_id: str) -> str:
    """Return a display label for an internal prompt block id."""
    return _PROMPT_BLOCK_LABELS.get(block_id, block_id)


def format_prompt_block_list(block_ids: tuple[str, ...]) -> str:
    """Return a compact display list for prompt block ids."""
    return ",".join(format_prompt_block_label(block_id) for block_id in block_ids)


def format_prompt_block_counts(counts: tuple[tuple[str, int], ...]) -> str:
    """Return compact display counts for prompt block ids."""
    return " / ".join(
        f"{format_prompt_block_label(block_id)}x{count}"
        for block_id, count in counts
    )
