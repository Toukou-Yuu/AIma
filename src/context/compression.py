"""Compression strategies for context history.

Compression modes:
- none: No compression, render all events
- snip: Keep recent events, add summary prefix for skipped
- collapse: Collapse older events into summary, keep recent in detail
- autocompact: High-density summary (stub for future implementation)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from llm.agent.context_store import ContextEvent


# Compression mode type
# "none" | "snip" | "collapse" | "autocompact"
CompressionMode = Literal["none", "snip", "collapse", "autocompact"]


@dataclass(frozen=True, slots=True)
class CompressionResult:
    """Result of compression operation."""

    text: str
    raw_event_count: int
    rendered_event_count: int
    snipped_event_count: int = 0
    collapsed_event_count: int = 0
    compression_mode: CompressionMode = "none"


class CompressionEngine:
    """Apply compression to context events."""

    def __init__(
        self,
        mode: CompressionMode = "none",
        budget: int = 0,
    ) -> None:
        """Initialize compression engine.

        Args:
            mode: Compression mode
            budget: Event budget (number of events to keep)
        """
        self._mode = mode
        self._budget = max(0, budget)

    def compress(self, events: list[ContextEvent], *, detailed: bool = True) -> CompressionResult:
        """Compress events into text.

        Args:
            events: List of context events
            detailed: Whether to include detailed information

        Returns:
            Compression result with text and statistics
        """
        if not events:
            return CompressionResult(
                text="",
                raw_event_count=0,
                rendered_event_count=0,
                compression_mode=self._mode,
            )

        if self._mode == "none":
            return self._compress_none(events, detailed=detailed)

        if self._mode == "snip":
            return self._compress_snip(events, detailed=detailed)

        if self._mode == "collapse":
            return self._compress_collapse(events, detailed=detailed)

        # autocompact: stub implementation, same as collapse
        return self._compress_autocompact(events, detailed=detailed)

    def _compress_none(
        self,
        events: list[ContextEvent],
        *,
        detailed: bool,
    ) -> CompressionResult:
        """No compression, render all events."""
        lines = [_render_event(ev, detailed=detailed) for ev in events]
        return CompressionResult(
            text="\n".join(lines),
            raw_event_count=len(events),
            rendered_event_count=len(events),
            compression_mode="none",
        )

    def _compress_snip(
        self,
        events: list[ContextEvent],
        *,
        detailed: bool,
    ) -> CompressionResult:
        """Keep recent events, add prefix for skipped."""
        keep = events[-self._budget :] if self._budget > 0 else events
        snipped = len(events) - len(keep)
        lines = [_render_event(ev, detailed=detailed) for ev in keep]
        if snipped > 0:
            lines.insert(0, f"[已省略 {snipped} 条较早记录]")
        return CompressionResult(
            text="\n".join(lines),
            raw_event_count=len(events),
            rendered_event_count=len(keep),
            snipped_event_count=snipped,
            compression_mode="snip",
        )

    def _compress_collapse(
        self,
        events: list[ContextEvent],
        *,
        detailed: bool,
    ) -> CompressionResult:
        """Collapse older events into summary."""
        if len(events) <= self._budget or self._budget <= 0:
            lines = [_render_event(ev, detailed=detailed) for ev in events]
            return CompressionResult(
                text="\n".join(lines),
                raw_event_count=len(events),
                rendered_event_count=len(events),
                compression_mode="collapse",
            )

        tail_budget = max(1, self._budget // 2)
        recent = events[-tail_budget:]
        older = events[:-tail_budget]
        summary_lines = _collapse_events(older)
        recent_lines = [_render_event(ev, detailed=detailed) for ev in recent]
        lines = summary_lines + recent_lines
        return CompressionResult(
            text="\n".join(lines),
            raw_event_count=len(events),
            rendered_event_count=len(recent),
            collapsed_event_count=len(older),
            compression_mode="collapse",
        )

    def _compress_autocompact(
        self,
        events: list[ContextEvent],
        *,
        detailed: bool,
    ) -> CompressionResult:
        """High-density summary (stub: same as collapse for now)."""
        # Stub: delegate to collapse
        result = self._compress_collapse(events, detailed=detailed)
        return CompressionResult(
            text=result.text,
            raw_event_count=result.raw_event_count,
            rendered_event_count=result.rendered_event_count,
            snipped_event_count=result.snipped_event_count,
            collapsed_event_count=result.collapsed_event_count,
            compression_mode="autocompact",
        )


def _render_event(event: ContextEvent, *, detailed: bool) -> str:
    """Render a single event to text."""
    base = f"第{event.turn_index}巡: {event.action_text}"
    if not detailed:
        reason = _clip(event.why, 18) if event.why else None
        return f"{base} / {reason}" if reason else base

    extra_parts: list[str] = []
    if event.why:
        extra_parts.append(f"理由: {_clip(event.why, 40)}")
    if event.legal_action_count > 0:
        extra_parts.append(f"候选{event.legal_action_count}项")
    if event.riichi_players:
        extra_parts.append("立直家=" + ",".join(f"家{s}" for s in event.riichi_players))
    if event.last_discard is not None and event.last_discard_seat is not None:
        extra_parts.append(f"末打=家{event.last_discard_seat}:{event.last_discard}")
    return base if not extra_parts else base + " (" + " | ".join(extra_parts) + ")"


def _collapse_events(events: list[ContextEvent]) -> list[str]:
    """Collapse older events into summary lines."""
    lines = [f"[较早 {len(events)} 条记录已折叠]"]
    key_events = [ev.action_text for ev in events if ev.is_key_event]
    if key_events:
        lines.append("关键事件: " + "; ".join(key_events[-3:]))
    last_threat = next((ev for ev in reversed(events) if ev.riichi_players), None)
    if last_threat is not None:
        threat_text = ", ".join(f"家{s}" for s in last_threat.riichi_players)
        lines.append(f"最新威胁家: {threat_text}")
    return lines


def _clip(text: str, limit: int) -> str:
    """Clip text to limit with ellipsis."""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"