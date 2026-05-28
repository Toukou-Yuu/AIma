"""v4-native ContextEvent 类型及 kernel 事件适配层。

v4 主链路使用此模块的 ContextEvent，不依赖旧 llm.agent.context_store.ContextEvent。
旧模块保持不变，两套类型并行存在。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kernel.event_log import GameEvent


@dataclass(frozen=True, slots=True)
class ContextEvent:
    """v4 arena 层事件，供 ContextBuilder 消费。

    Attributes:
        match_id: 对局唯一标识符
        job_id: 批处理任务标识符
        hand_index: 当前手牌索引（局编号，0-based）
        step_index: 当前步数
        turn_index: 当前手牌内的决策轮次（0 表示开局/非决策事件）
        seat: 事件关联座位（无座位含义的事件为 None）
        event_type: 事件类型字符串（来自 kernel event class name 或 arena 合成类型）
        text: 事件的自然语言摘要（供 ContextBuilder 渲染用）
        payload: 原始事件字段（序列化为 dict，方便过滤和压缩）
    """

    match_id: str
    job_id: str
    hand_index: int
    step_index: int
    turn_index: int
    seat: int | None
    event_type: str
    text: str
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def action_text(self) -> str:
        """Compatibility text used by ContextBuilder compression."""
        return self.text

    @property
    def why(self) -> str | None:
        """Kernel events do not carry policy reasoning."""
        return None

    @property
    def legal_action_count(self) -> int:
        """Kernel events are facts, not decision candidates."""
        return 0

    @property
    def riichi_players(self) -> tuple[int, ...]:
        """Best-effort threat metadata for compression."""
        if self.payload.get("declare_riichi") and self.seat is not None:
            return (self.seat,)
        return ()

    @property
    def last_discard(self) -> str | None:
        """Return the discard tile when this event is a discard."""
        tile = self.payload.get("tile")
        return str(tile) if tile is not None else None

    @property
    def last_discard_seat(self) -> int | None:
        """Return discard seat when this event is a discard."""
        if self.event_type == "DiscardTileEvent":
            return self.seat
        return None

    @property
    def is_key_event(self) -> bool:
        """Whether the event should be preserved during compression."""
        return self.event_type in {
            "CallEvent",
            "RonEvent",
            "TsumoEvent",
            "FlowEvent",
            "HandOverEvent",
            "MatchEndEvent",
        }


def kernel_event_to_context_event(
    *,
    kernel_event: "GameEvent",
    match_id: str,
    job_id: str,
    hand_index: int,
    step_index: int,
    turn_index: int,
) -> ContextEvent:
    """将 kernel GameEvent 转换为 v4 ContextEvent。

    Args:
        kernel_event: 原始 kernel 事件 dataclass
        match_id: 对局 ID
        job_id: 任务 ID
        hand_index: 当前手牌索引
        step_index: 当前步数
        turn_index: 当前手牌内的决策轮次

    Returns:
        对应的 ContextEvent
    """
    from kernel.event_log import (
        CallEvent,
        DiscardTileEvent,
        DrawTileEvent,
        FlowEvent,
        HandOverEvent,
        MatchEndEvent,
        RonEvent,
        RoundBeginEvent,
        TsumoEvent,
    )

    event_type = type(kernel_event).__name__
    seat: int | None = getattr(kernel_event, "seat", None)
    text: str = event_type
    payload: dict[str, Any] = {}

    if isinstance(kernel_event, RoundBeginEvent):
        text = f"Round begins — dealer: seat {kernel_event.dealer_seat}"
        payload = {"dealer_seat": kernel_event.dealer_seat}

    elif isinstance(kernel_event, DrawTileEvent):
        tile_code = kernel_event.tile.to_code() if kernel_event.tile else "?"
        rinshan = " (rinshan)" if kernel_event.is_rinshan else ""
        text = f"Seat {seat} draws{rinshan} — wall: {kernel_event.wall_remaining} left"
        payload = {
            "seat": seat,
            "is_rinshan": kernel_event.is_rinshan,
            "wall_remaining": kernel_event.wall_remaining,
        }

    elif isinstance(kernel_event, DiscardTileEvent):
        tile_code = kernel_event.tile.to_code() if kernel_event.tile else "?"
        riichi_marker = " [riichi]" if kernel_event.declare_riichi else ""
        tsumogiri_marker = " (tsumogiri)" if kernel_event.is_tsumogiri else ""
        text = f"Seat {seat} discards {tile_code}{riichi_marker}{tsumogiri_marker}"
        payload = {
            "seat": seat,
            "tile": tile_code,
            "is_tsumogiri": kernel_event.is_tsumogiri,
            "declare_riichi": kernel_event.declare_riichi,
        }

    elif isinstance(kernel_event, CallEvent):
        call_kind = kernel_event.call_kind
        tiles_str = (
            " ".join(t.to_code() for t in kernel_event.meld.tiles)
            if kernel_event.meld
            else "?"
        )
        text = f"Seat {seat} calls {call_kind}: {tiles_str}"
        payload = {"seat": seat, "call_kind": call_kind}

    elif isinstance(kernel_event, RonEvent):
        win_tile = kernel_event.win_tile.to_code() if kernel_event.win_tile else "?"
        text = f"Seat {seat} wins by ron on {win_tile} (from seat {kernel_event.discard_seat})"
        payload = {
            "seat": seat,
            "win_tile": win_tile,
            "discard_seat": kernel_event.discard_seat,
        }

    elif isinstance(kernel_event, TsumoEvent):
        win_tile = kernel_event.win_tile.to_code() if kernel_event.win_tile else "?"
        rinshan = " (rinshan)" if kernel_event.is_rinshan else ""
        text = f"Seat {seat} wins by tsumo on {win_tile}{rinshan}"
        payload = {
            "seat": seat,
            "win_tile": win_tile,
            "is_rinshan": kernel_event.is_rinshan,
        }

    elif isinstance(kernel_event, FlowEvent):
        flow_kind = str(kernel_event.flow_kind)
        tenpai = sorted(kernel_event.tenpai_seats)
        text = f"Flow ({flow_kind}) — tenpai seats: {tenpai}"
        payload = {"flow_kind": flow_kind, "tenpai_seats": tenpai}

    elif isinstance(kernel_event, HandOverEvent):
        winners = list(kernel_event.winners)
        payments = list(kernel_event.payments)
        text = (
            f"Hand over — winners: {winners}, payments: {payments}"
            if winners
            else f"Hand over (draw/flow) — payments: {payments}"
        )
        payload = {"winners": winners, "payments": payments}

    elif isinstance(kernel_event, MatchEndEvent):
        ranking = list(kernel_event.ranking)
        final_scores = list(kernel_event.final_scores)
        text = f"Match end — ranking: {ranking}, final_scores: {final_scores}"
        payload = {"ranking": ranking, "final_scores": final_scores}

    else:
        # 未知事件类型：记录 class name
        text = f"[{event_type}]"

    return ContextEvent(
        match_id=match_id,
        job_id=job_id,
        hand_index=hand_index,
        step_index=step_index,
        turn_index=turn_index,
        seat=seat,
        event_type=event_type,
        text=text,
        payload=payload,
    )
