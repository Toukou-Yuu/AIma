"""对局可读文本：由内核 ``GameEvent`` 生成说人话的一行说明（简体中文）。"""

from __future__ import annotations

from typing import TextIO

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
from kernel.flow.model import FlowKind

_FLOW_CN: dict[FlowKind, str] = {
    FlowKind.EXHAUSTED: "荒牌流局（牌山摸完）",
    FlowKind.NINE_NINE: "九种九牌流局",
    FlowKind.FOUR_WINDS: "四风连打流局",
    FlowKind.FOUR_KANS: "四杠散了流局",
    FlowKind.FOUR_RIICHI: "四家立直流局",
    FlowKind.THREE_RON: "三家和流局",
}

_CALL_CN: dict[str, str] = {
    "chi": "吃",
    "pon": "碰",
    "daiminkan": "大明杠",
    "ankan": "暗杠",
    "shankuminkan": "加杠",
}


def _家(s: int | None) -> str:
    if s is None:
        return "（未知席）"
    return f"家{s}"


def format_game_event(ev: GameEvent) -> str | None:
    """``GameEvent`` → 一行中文；无合适文案时返回 ``None``。"""
    if isinstance(ev, RoundBeginEvent):
        d = ev.dora_indicator.to_code()
        return f"配牌完成，亲={_家(ev.dealer_seat)}，表宝指示牌 {d}"

    if isinstance(ev, DrawTileEvent):
        src = "岭上" if ev.is_rinshan else "本墙"
        return f"{_家(ev.seat)} 从{src}摸 {ev.tile.to_code()} （余牌约 {ev.wall_remaining} 张）"

    if isinstance(ev, DiscardTileEvent):
        tg = "摸切" if ev.is_tsumogiri else "手切"
        if ev.declare_riichi:
            return f"{_家(ev.seat)} 打出 {ev.tile.to_code()}（{tg}，立直宣言）"
        return f"{_家(ev.seat)} 打出 {ev.tile.to_code()}（{tg}）"

    if isinstance(ev, CallEvent):
        cn = _CALL_CN.get(ev.call_kind, ev.call_kind)
        m = ev.meld
        tiles_s = " ".join(t.to_code() for t in m.tiles)
        ct = m.called_tile.to_code() if m.called_tile else ""
        extra = f"，鸣入 {ct}" if ct else ""
        return f"{_家(ev.seat)} {cn}：{tiles_s}{extra}"

    if isinstance(ev, RonEvent):
        return f"{_家(ev.seat)} 荣和 {ev.win_tile.to_code()} （铳：{_家(ev.discard_seat)}）"

    if isinstance(ev, TsumoEvent):
        rs = "岭上" if ev.is_rinshan else ""
        return f"{_家(ev.seat)} 自摸和了 {rs} {ev.win_tile.to_code()}"

    if isinstance(ev, FlowEvent):
        fk = _FLOW_CN.get(ev.flow_kind, ev.flow_kind.value)
        tp = f"，听牌：{sorted(ev.tenpai_seats)}" if ev.tenpai_seats else ""
        return f"流局：{fk}{tp}"

    if isinstance(ev, HandOverEvent):
        lines = []
        if ev.winners:
            win_s = "、".join(_家(w) for w in ev.winners)
            lines.append(f"局终：和了 {win_s}，点棒变化 {list(ev.payments)}")
            for ln in ev.win_lines:
                y = "、".join(ln.yakus) if ln.yakus else "—"
                lines.append(
                    f"  · {_家(ln.seat)} {ln.hand_pattern} {ln.han}番{ln.fu}符 "
                    f"[{y}] 得 {ln.points} 点"
                )
        else:
            lines.append(f"局终：和了者无（流局等），点棒变化 {list(ev.payments)}")
        return "\n".join(lines)

    if isinstance(ev, MatchEndEvent):
        # ``ranking[s]`` 为家 s 的名次（1=一位 …）
        order = " ".join(f"{_家(s)}{ev.ranking[s]}位" for s in range(4))
        sc = " / ".join(str(x) for x in ev.final_scores)
        return f"比赛结束：{order}；点棒 [{sc}]"

    return None


def format_action_wire_supplement(w: dict) -> str | None:
    """无对应事件时的动作补充说明（如 ``noop`` 换牌山）。"""
    kind = w.get("kind")
    if kind == "noop" and w.get("wall"):
        return "（局间）开始新一局，已换牌山。"
    if kind == "begin_round":
        return None
    return None


def append_simple_log_block(
    fp: TextIO | None,
    events: tuple[GameEvent, ...],
    *,
    action_wire: dict | None = None,
    drained_calls: int | None = None,
) -> None:
    """写入一段可读日志；``fp`` 为 ``None`` 时不写。"""
    if fp is None:
        return
    if drained_calls is not None and drained_calls > 0 and not events:
        fp.write(f"（应答）连续过牌 {drained_calls} 次。\n")
    for ev in events:
        line = format_game_event(ev)
        if line:
            fp.write(line + "\n")
    # 仅当本步无内核事件时用动作补充（避免与 RoundBegin 等重复）
    if action_wire and not events:
        sup = format_action_wire_supplement(action_wire)
        if sup:
            fp.write(sup + "\n")
    fp.flush()
