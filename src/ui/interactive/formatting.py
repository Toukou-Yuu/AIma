"""Shared formatting helpers for interactive UI flows."""

from __future__ import annotations

from datetime import datetime


def format_timestamp(timestamp: float | None) -> str:
    """Format a session timestamp for compact terminal display."""
    if timestamp is None:
        return "未开始"
    return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")


def format_duration(seconds: float | None) -> str:
    """Format elapsed seconds for Chinese UI labels."""
    if seconds is None:
        return "0.0 秒"
    if seconds < 60:
        return f"{seconds:.1f} 秒"
    minutes, remain = divmod(seconds, 60)
    return f"{int(minutes)} 分 {remain:.1f} 秒"


def format_replay_speed(delay_seconds: float) -> str:
    """Format replay delay as a per-step speed label."""
    return f"{delay_seconds:.1f} 秒 / 步"

