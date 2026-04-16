"""Structured context storage and budget-aware history projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from kernel.api.legal_actions import LegalAction
    from kernel.api.observation import Observation
    from llm.agent.memory import PlayerMemory
    from llm.agent.stats import PlayerStats

CompressionLevel = Literal["none", "snip", "micro", "collapse"]


@dataclass(frozen=True, slots=True)
class PersistentState:
    """长期状态快照。"""

    memory: "PlayerMemory"
    stats: "PlayerStats"


@dataclass(frozen=True, slots=True)
class TurnContext:
    """单步 prompt 投影输入。"""

    observation: "Observation"
    legal_actions: tuple["LegalAction", ...]
    turn_index: int


@dataclass(frozen=True, slots=True)
class ContextEvent:
    """结构化历史事件。"""

    turn_index: int
    phase: str
    action_kind: str
    action_text: str
    why: str | None
    legal_action_count: int
    riichi_players: tuple[int, ...]
    scores: tuple[int, ...]
    last_discard: str | None = None
    last_discard_seat: int | None = None

    @property
    def is_key_event(self) -> bool:
        """是否属于值得优先保留的关键事件。"""
        if self.action_kind in {"ron", "tsumo", "open_meld", "ankan", "shankuminkan"}:
            return True
        return "立直" in self.action_text


@dataclass(frozen=True, slots=True)
class HistoryProjection:
    """发送给模型的历史视图。"""

    text: str
    raw_event_count: int
    rendered_event_count: int
    snipped_event_count: int = 0
    collapsed_event_count: int = 0


@dataclass
class ContextStore:
    """上下文原始事实仓库。"""

    events: list[ContextEvent] = field(default_factory=list)

    def append_event(self, event: ContextEvent) -> None:
        """追加一条事件。"""
        self.events.append(event)

    def project_history(
        self,
        *,
        detailed: bool,
        history_budget: int,
        compression_level: CompressionLevel,
    ) -> HistoryProjection:
        """根据预算和压缩等级生成历史视图。"""
        pipeline = CompressionPipeline(
            history_budget=history_budget,
            compression_level=compression_level,
        )
        return pipeline.project(self.events, detailed=detailed)


class BudgetManager:
    """简单的历史预算管理器。"""

    def __init__(self, history_budget: int) -> None:
        self.history_budget = max(0, history_budget)
        self.char_budget = 0 if self.history_budget == 0 else max(240, self.history_budget * 120)

    def recent_tail_budget(self) -> int:
        """折叠模式下保留多少最近事件。"""
        if self.history_budget <= 1:
            return self.history_budget
        return max(1, self.history_budget // 2)


class CompressionPipeline:
    """渐进式上下文压缩流水线。"""

    def __init__(
        self,
        *,
        history_budget: int,
        compression_level: CompressionLevel,
    ) -> None:
        self._budget = BudgetManager(history_budget)
        self._compression_level = compression_level

    def project(
        self,
        events: list[ContextEvent],
        *,
        detailed: bool,
    ) -> HistoryProjection:
        """投影结构化历史为可发送文本。"""
        if not events or self._budget.history_budget == 0:
            return HistoryProjection("", len(events), 0)

        if self._compression_level == "none":
            lines = [self._render_event(ev, detailed=detailed, compact=not detailed) for ev in events]
            return HistoryProjection("\n".join(lines), len(events), len(events))

        if self._compression_level == "snip":
            return self._snip(events, detailed=detailed)

        if self._compression_level == "micro":
            return self._microcompact(events)

        return self._collapse(events, detailed=detailed)

    def _snip(
        self,
        events: list[ContextEvent],
        *,
        detailed: bool,
    ) -> HistoryProjection:
        keep = events[-self._budget.history_budget :]
        snipped = len(events) - len(keep)
        lines = [self._render_event(ev, detailed=detailed, compact=not detailed) for ev in keep]
        if snipped > 0:
            lines.insert(0, f"[已省略 {snipped} 条较早记录]")
        return HistoryProjection(
            "\n".join(lines),
            len(events),
            len(keep),
            snipped_event_count=snipped,
        )

    def _microcompact(self, events: list[ContextEvent]) -> HistoryProjection:
        keep = events[-self._budget.history_budget :]
        snipped = len(events) - len(keep)
        lines = [self._render_event(ev, detailed=False, compact=True) for ev in keep]
        if snipped > 0:
            lines.insert(0, f"[已截断 {snipped} 条较早记录]")
        clipped_lines: list[str] = []
        total = 0
        for line in lines:
            clipped = self._clip(line, 88)
            next_total = total + len(clipped) + 1
            if self._budget.char_budget and next_total > self._budget.char_budget:
                break
            clipped_lines.append(clipped)
            total = next_total
        return HistoryProjection(
            "\n".join(clipped_lines),
            len(events),
            len(keep),
            snipped_event_count=snipped,
        )

    def _collapse(
        self,
        events: list[ContextEvent],
        *,
        detailed: bool,
    ) -> HistoryProjection:
        if len(events) <= self._budget.history_budget:
            lines = [self._render_event(ev, detailed=detailed, compact=not detailed) for ev in events]
            return HistoryProjection("\n".join(lines), len(events), len(events))

        tail_budget = self._budget.recent_tail_budget()
        recent = events[-tail_budget:]
        older = events[:-tail_budget]
        summary_lines = self._collapse_events(older)
        recent_lines = [self._render_event(ev, detailed=detailed, compact=not detailed) for ev in recent]
        lines = summary_lines + recent_lines
        return HistoryProjection(
            "\n".join(lines),
            len(events),
            len(recent),
            collapsed_event_count=len(older),
        )

    def _collapse_events(self, events: list[ContextEvent]) -> list[str]:
        lines = [f"[较早 {len(events)} 条记录已折叠]"]
        key_events = [ev.action_text for ev in events if ev.is_key_event]
        if key_events:
            lines.append("关键事件: " + "; ".join(key_events[-3:]))
        last_threat = next((ev for ev in reversed(events) if ev.riichi_players), None)
        if last_threat is not None:
            threat_text = ", ".join(f"家{s}" for s in last_threat.riichi_players)
            lines.append(f"最新威胁家: {threat_text}")
        return lines

    def _render_event(
        self,
        event: ContextEvent,
        *,
        detailed: bool,
        compact: bool,
    ) -> str:
        base = f"第{event.turn_index}巡: {event.action_text}"
        if compact:
            reason = self._clip(event.why, 18) if event.why else None
            return f"{base} / {reason}" if reason else base

        extra_parts: list[str] = []
        if event.why:
            extra_parts.append(f"理由: {self._clip(event.why, 40 if detailed else 24)}")
        if event.legal_action_count > 0:
            extra_parts.append(f"候选{event.legal_action_count}项")
        if detailed and event.riichi_players:
            extra_parts.append("立直家=" + ",".join(f"家{s}" for s in event.riichi_players))
        if detailed and event.last_discard is not None and event.last_discard_seat is not None:
            extra_parts.append(f"末打=家{event.last_discard_seat}:{event.last_discard}")
        return base if not extra_parts else base + " (" + " | ".join(extra_parts) + ")"

    def _clip(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 1)] + "…"
