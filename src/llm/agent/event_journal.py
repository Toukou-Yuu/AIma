"""Shared public event journal for prompt context projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from kernel.event_log import (
    CallEvent,
    DiscardTileEvent,
    DrawTileEvent,
    FlowEvent,
    GameEvent,
    HandOverEvent,
    MatchEndEvent,
    RonEvent,
    RoundBeginEvent,
    TsumoEvent,
)
from kernel.scoring.dora import dora_from_indicators

if TYPE_CHECKING:
    from llm.agent.context_store import CompressionLevel


@dataclass(frozen=True, slots=True)
class PublicEventRecord:
    """Renderable public event record."""

    sequence: int
    text: str
    compact_text: str
    is_key_event: bool = False
    threat_seat: int | None = None


@dataclass(frozen=True, slots=True)
class ArchivedHandSummary:
    """Archived public hand summary."""

    hand_number: int
    text: str


@dataclass
class MatchJournal:
    """Shared public journal for one match."""

    current_hand_number: int = 0
    current_hand_events: list[GameEvent] = field(default_factory=list)
    archived_hand_summaries: list[ArchivedHandSummary] = field(default_factory=list)

    def start_hand(self, hand_number: int, opening_events: tuple[GameEvent, ...]) -> None:
        """Start tracking a new hand."""
        self.current_hand_number = hand_number
        self.current_hand_events = list(opening_events)

    def append_events(self, events: tuple[GameEvent, ...]) -> None:
        """Append public events of the current hand."""
        self.current_hand_events.extend(events)

    def archive_current_hand(self) -> None:
        """Archive the current hand once it is finished."""
        if self.current_hand_number <= 0 or not self.current_hand_events:
            return
        summary = self.project_current_hand(
            viewer_seat=None,
            detailed=False,
            history_budget=8,
            compression_level="autocompact",
        )
        if summary:
            self.archived_hand_summaries.append(
                ArchivedHandSummary(hand_number=self.current_hand_number, text=summary)
            )
        self.current_hand_events = []

    def project_current_hand(
        self,
        *,
        viewer_seat: int | None,
        detailed: bool,
        history_budget: int,
        compression_level: "CompressionLevel",
    ) -> str:
        """Project current hand public events as prompt text."""
        if history_budget <= 0 or not self.current_hand_events:
            return ""
        records = [
            _project_public_event(
                event,
                viewer_seat=viewer_seat,
                hand_number=self.current_hand_number,
            )
            for event in self.current_hand_events
        ]
        return _render_records(
            [record for record in records if record is not None],
            detailed=detailed,
            history_budget=history_budget,
            compression_level=compression_level,
        )

    def project_archived_hands(
        self,
        *,
        archive_budget: int,
        compression_level: "CompressionLevel",
    ) -> str:
        """Project archived public hand summaries."""
        if archive_budget <= 0 or not self.archived_hand_summaries:
            return ""

        summaries = self.archived_hand_summaries
        if compression_level == "none":
            lines = [summary.text for summary in summaries[-archive_budget:]]
            return "\n".join(lines)

        if compression_level == "snip":
            keep = summaries[-archive_budget:]
            skipped = len(summaries) - len(keep)
            lines = [summary.text for summary in keep]
            if skipped > 0:
                lines.insert(0, f"[已省略 {skipped} 局较早公共记录]")
            return "\n".join(lines)

        if compression_level == "micro":
            keep = summaries[-archive_budget:]
            skipped = len(summaries) - len(keep)
            lines = [_clip(summary.text.replace("\n", " / "), 84) for summary in keep]
            if skipped > 0:
                lines.insert(0, f"[已截断 {skipped} 局较早公共记录]")
            return "\n".join(lines)

        if compression_level == "collapse":
            tail_budget = max(1, archive_budget // 2 or 1)
            recent = summaries[-tail_budget:]
            older = summaries[:-tail_budget]
            lines: list[str] = []
            if older:
                lines.append(f"[较早 {len(older)} 局公共记录已折叠]")
                lines.extend(_compact_archive_lines(older[-2:]))
            lines.extend(summary.text for summary in recent)
            return "\n".join(lines)

        tail_budget = max(1, min(2, archive_budget))
        recent = summaries[-tail_budget:]
        older = summaries[:-tail_budget]
        lines = [f"[本场已完成 {len(summaries)} 局，较早公共记录已高密度折叠]"]
        if older:
            lines.extend(_compact_archive_lines(older[-2:]))
        lines.extend(_clip(summary.text.replace("\n", " / "), 120) for summary in recent)
        return "\n".join(lines)


def _seat_name(seat: int | None, viewer_seat: int | None) -> str:
    if seat is None:
        return "系统"
    if viewer_seat is not None and seat == viewer_seat:
        return "我"
    return f"家{seat}"


def _project_public_event(
    event: GameEvent,
    *,
    viewer_seat: int | None,
    hand_number: int,
) -> PublicEventRecord | None:
    who = _seat_name(event.seat, viewer_seat)

    if isinstance(event, RoundBeginEvent):
        dora_tile = dora_from_indicators((event.dora_indicator,))[0]
        text = (
            f"第{hand_number}局开始：亲家家{event.dealer_seat}，"
            f"宝牌指示器 {event.dora_indicator.to_code()}，实际宝牌 {dora_tile.to_code()}"
        )
        return PublicEventRecord(event.sequence, text, text, is_key_event=True)

    if isinstance(event, DrawTileEvent):
        draw_desc = "岭上摸牌" if event.is_rinshan else "摸牌"
        text = f"{who}{draw_desc}"
        return PublicEventRecord(event.sequence, text, text, is_key_event=False)

    if isinstance(event, DiscardTileEvent):
        suffix: list[str] = []
        if event.is_tsumogiri:
            suffix.append("摸切")
        if event.declare_riichi:
            suffix.append("立直")
        suffix_text = f" ({' / '.join(suffix)})" if suffix else ""
        text = f"{who}打 {event.tile.to_code()}{suffix_text}"
        compact = f"{who}打{event.tile.to_code()}" + ("立直" if event.declare_riichi else "")
        return PublicEventRecord(
            event.sequence,
            text,
            compact,
            is_key_event=event.declare_riichi,
            threat_seat=event.seat if event.declare_riichi else None,
        )

    if isinstance(event, CallEvent):
        tiles = "/".join(tile.to_code() for tile in event.meld.tiles)
        called = event.meld.called_tile.to_code() if event.meld.called_tile is not None else "?"
        text = f"{who}{event.call_kind} {tiles} (叫{called})"
        compact = f"{who}{event.call_kind} {tiles}"
        return PublicEventRecord(event.sequence, text, compact, is_key_event=True)

    if isinstance(event, RonEvent):
        text = f"{who}荣和，和牌 {event.win_tile.to_code()}，放铳家{event.discard_seat}"
        compact = f"{who}荣和 {event.win_tile.to_code()}"
        return PublicEventRecord(event.sequence, text, compact, is_key_event=True)

    if isinstance(event, TsumoEvent):
        mode = "岭上自摸" if event.is_rinshan else "自摸"
        text = f"{who}{mode} {event.win_tile.to_code()}"
        return PublicEventRecord(event.sequence, text, text, is_key_event=True)

    if isinstance(event, FlowEvent):
        tenpai = ", ".join(f"家{seat}" for seat in sorted(event.tenpai_seats)) or "无"
        text = f"流局 ({event.flow_kind.value})，听牌：{tenpai}"
        compact = f"流局 {event.flow_kind.value}"
        return PublicEventRecord(event.sequence, text, compact, is_key_event=True)

    if isinstance(event, HandOverEvent):
        winners = ", ".join(f"家{seat}" for seat in event.winners) or "无"
        text = (
            f"本局结算：和了者 {winners}，"
            f"收支 {', '.join(f'家{i}:{delta:+d}' for i, delta in enumerate(event.payments))}"
        )
        compact = f"结算 winners={winners}"
        return PublicEventRecord(event.sequence, text, compact, is_key_event=True)

    if isinstance(event, MatchEndEvent):
        ranking = ", ".join(f"家{seat}:{rank}" for seat, rank in enumerate(event.ranking))
        final_scores = ", ".join(str(score) for score in event.final_scores)
        text = f"终局：顺位 {ranking}，最终点数 {final_scores}"
        compact = "终局"
        return PublicEventRecord(event.sequence, text, compact, is_key_event=True)

    return None


def _render_records(
    records: list[PublicEventRecord],
    *,
    detailed: bool,
    history_budget: int,
    compression_level: "CompressionLevel",
) -> str:
    if not records:
        return ""

    if compression_level == "none":
        return "\n".join(record.text if detailed else record.compact_text for record in records)

    if compression_level == "snip":
        keep = records[-history_budget:]
        skipped = len(records) - len(keep)
        lines = [record.text if detailed else record.compact_text for record in keep]
        if skipped > 0:
            lines.insert(0, f"[已省略 {skipped} 条较早公共事件]")
        return "\n".join(lines)

    if compression_level == "micro":
        keep = records[-history_budget:]
        skipped = len(records) - len(keep)
        lines = [_clip(record.compact_text, 84) for record in keep]
        if skipped > 0:
            lines.insert(0, f"[已截断 {skipped} 条较早公共事件]")
        return "\n".join(lines)

    if compression_level == "collapse":
        if len(records) <= history_budget:
            return "\n".join(record.text if detailed else record.compact_text for record in records)
        tail_budget = max(1, history_budget // 2 or 1)
        older = records[:-tail_budget]
        recent = records[-tail_budget:]
        lines = [f"[较早 {len(older)} 条公共事件已折叠]"]
        key_events = [record.compact_text for record in older if record.is_key_event]
        if key_events:
            lines.append("关键公共事件: " + "; ".join(key_events[-3:]))
        latest_threat = next(
            (record.threat_seat for record in reversed(older) if record.threat_seat is not None),
            None,
        )
        if latest_threat is not None:
            lines.append(f"最近立直威胁: 家{latest_threat}")
        lines.extend(record.text if detailed else record.compact_text for record in recent)
        return "\n".join(lines)

    tail_budget = 1 if history_budget <= 2 else 2
    older = records[:-tail_budget]
    recent = records[-tail_budget:]
    lines = [f"[本局已记录 {len(records)} 条公共事件，较早部分已高密度折叠]"]
    key_events = [record.compact_text for record in older if record.is_key_event]
    if key_events:
        lines.append("高密度摘要: " + "; ".join(_clip(text, 32) for text in key_events[-4:]))
    latest_threat = next(
        (record.threat_seat for record in reversed(records) if record.threat_seat is not None),
        None,
    )
    if latest_threat is not None:
        lines.append(f"当前主要威胁: 家{latest_threat}")
    lines.extend(_clip(record.compact_text, 96) for record in recent)
    return "\n".join(lines)


def _compact_archive_lines(summaries: list[ArchivedHandSummary]) -> list[str]:
    lines: list[str] = []
    for summary in summaries:
        lines.append(_clip(summary.text.replace("\n", " / "), 120))
    return lines


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"
