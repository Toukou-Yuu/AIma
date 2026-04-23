"""牌谱 JSON wire：``Action`` / ``GameEvent`` 与 dict 可逆转换（供落盘与 ``replay_from_actions``）。

不依赖 ``llm`` / ``web``；牌码与 Web API 一致（``Tile.to_code()``）。
"""

from __future__ import annotations

import re
from typing import Any

from kernel.engine.actions import Action, ActionKind
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
    WinSettlementLine,
)
from kernel.flow.model import FlowKind
from kernel.hand.melds import Meld, MeldKind
from kernel.tiles.model import Suit, Tile

# 顶层牌谱 JSON 的 schema 版本（与 ``llm`` CLI 写出结构一致）
MATCH_LOG_FORMAT_VERSION = 2

_NUM_TILE_RE = re.compile(r"^([1-9])([mps])(r)?$")
_HONOR_RE = re.compile(r"^([1-7])z$")


def tile_from_code(code: str) -> Tile:
    """解析 ``3m``、``5pr``、``2z`` 等短码。"""
    s = code.strip().lower()
    m = _NUM_TILE_RE.match(s)
    if m:
        rank = int(m.group(1))
        suit = {"m": Suit.MAN, "p": Suit.PIN, "s": Suit.SOU}[m.group(2)]
        is_red = bool(m.group(3))
        if is_red and rank != 5:
            msg = "red marker only valid for rank 5"
            raise ValueError(msg)
        return Tile(suit, rank, is_red)
    m = _HONOR_RE.match(s)
    if m:
        return Tile(Suit.HONOR, int(m.group(1)), False)
    msg = f"invalid tile code: {code!r}"
    raise ValueError(msg)


def meld_from_wire(data: dict[str, Any]) -> Meld:
    """wire dict → ``Meld``。"""
    kind = MeldKind(data["kind"])
    tiles = tuple(tile_from_code(x) for x in data["tiles"])
    called = tile_from_code(data["called_tile"]) if data.get("called_tile") else None
    from_seat = data.get("from_seat")
    if from_seat is not None:
        from_seat = int(from_seat)
    return Meld(kind=kind, tiles=tiles, called_tile=called, from_seat=from_seat)


def meld_to_wire(meld: Meld) -> dict[str, Any]:
    out: dict[str, Any] = {
        "kind": meld.kind.value,
        "tiles": [t.to_code() for t in meld.tiles],
    }
    if meld.called_tile is not None:
        out["called_tile"] = meld.called_tile.to_code()
    if meld.from_seat is not None:
        out["from_seat"] = meld.from_seat
    return out


def win_line_to_wire(line: WinSettlementLine) -> dict[str, Any]:
    """``WinSettlementLine`` → dict（牌谱 ``hand_over.win_lines``）。"""
    d: dict[str, Any] = {
        "seat": line.seat,
        "win_kind": line.win_kind,
        "han": line.han,
        "fu": line.fu,
        "hand_pattern": line.hand_pattern,
        "yakus": list(line.yakus),
        "kyoutaku_share": line.kyoutaku_share,
        "points": line.points,
    }
    if line.discard_seat is not None:
        d["discard_seat"] = line.discard_seat
    if line.payment_from_discarder is not None:
        d["payment_from_discarder"] = line.payment_from_discarder
    if line.tsumo_deltas is not None:
        d["tsumo_deltas"] = list(line.tsumo_deltas)
    return d


def win_line_from_wire(data: dict[str, Any]) -> WinSettlementLine:
    """dict → ``WinSettlementLine``。"""
    raw_td = data.get("tsumo_deltas")
    tsumo_deltas = None
    if raw_td is not None:
        tsumo_deltas = tuple(int(x) for x in raw_td)
    ds = data.get("discard_seat")
    if ds is not None:
        ds = int(ds)
    pfd = data.get("payment_from_discarder")
    if pfd is not None:
        pfd = int(pfd)
    return WinSettlementLine(
        seat=int(data["seat"]),
        win_kind=str(data["win_kind"]),
        han=int(data["han"]),
        fu=int(data["fu"]),
        hand_pattern=str(data["hand_pattern"]),
        yakus=tuple(str(x) for x in data.get("yakus", ())),
        discard_seat=ds,
        payment_from_discarder=pfd,
        tsumo_deltas=tsumo_deltas,
        kyoutaku_share=int(data.get("kyoutaku_share", 0)),
        points=int(data.get("points", 0)),
    )


def action_to_wire(action: Action) -> dict[str, Any]:
    """``Action`` → 可 JSON 序列化的 dict。"""
    d: dict[str, Any] = {"kind": action.kind.value}
    if action.seat is not None:
        d["seat"] = action.seat
    if action.wall is not None:
        d["wall"] = [t.to_code() for t in action.wall]
    if action.tile is not None:
        d["tile"] = action.tile.to_code()
    if action.declare_riichi:
        d["declare_riichi"] = True
    if action.meld is not None:
        d["meld"] = meld_to_wire(action.meld)
    return d


def action_from_wire(data: dict[str, Any]) -> Action:
    """dict → ``apply`` 用 ``Action``。"""
    kind = ActionKind(data["kind"])
    seat = data.get("seat")
    if seat is not None:
        seat = int(seat)
    wall = None
    if data.get("wall") is not None:
        wall = tuple(tile_from_code(x) for x in data["wall"])
    tile = tile_from_code(data["tile"]) if data.get("tile") else None
    declare_riichi = bool(data.get("declare_riichi", False))
    meld = meld_from_wire(data["meld"]) if data.get("meld") else None
    return Action(
        kind=kind,
        seat=seat,
        wall=wall,
        tile=tile,
        declare_riichi=declare_riichi,
        meld=meld,
    )


def game_event_to_wire(event: GameEvent) -> dict[str, Any]:
    """``GameEvent`` → 可 JSON 序列化的 dict（含 ``event_type`` 判别）。"""
    base: dict[str, Any] = {
        "event_type": _EVENT_TO_TYPE[type(event)],
        "sequence": event.sequence,
        "seat": event.seat,
    }
    if isinstance(event, RoundBeginEvent):
        base["dealer_seat"] = event.dealer_seat
        base["dora_indicator"] = event.dora_indicator.to_code()
        base["seeds"] = list(event.seeds)
    elif isinstance(event, DrawTileEvent):
        base["tile"] = event.tile.to_code()
        base["is_rinshan"] = event.is_rinshan
        base["wall_remaining"] = event.wall_remaining
    elif isinstance(event, DiscardTileEvent):
        base["tile"] = event.tile.to_code()
        base["is_tsumogiri"] = event.is_tsumogiri
        base["declare_riichi"] = event.declare_riichi
    elif isinstance(event, CallEvent):
        base["meld"] = meld_to_wire(event.meld)
        base["call_kind"] = event.call_kind
    elif isinstance(event, RonEvent):
        base["win_tile"] = event.win_tile.to_code()
        base["discard_seat"] = event.discard_seat
    elif isinstance(event, TsumoEvent):
        base["win_tile"] = event.win_tile.to_code()
        base["is_rinshan"] = event.is_rinshan
    elif isinstance(event, FlowEvent):
        base["flow_kind"] = event.flow_kind.value
        base["tenpai_seats"] = sorted(event.tenpai_seats)
    elif isinstance(event, HandOverEvent):
        base["winners"] = list(event.winners)
        base["payments"] = list(event.payments)
        base["win_lines"] = [win_line_to_wire(x) for x in event.win_lines]
    elif isinstance(event, MatchEndEvent):
        base["ranking"] = list(event.ranking)
        base["final_scores"] = list(event.final_scores)
    else:
        msg = f"unknown GameEvent type: {type(event)!r}"
        raise TypeError(msg)
    return base


_EVENT_TO_TYPE: dict[type[GameEvent], str] = {
    RoundBeginEvent: "round_begin",
    DrawTileEvent: "draw_tile",
    DiscardTileEvent: "discard_tile",
    CallEvent: "call",
    RonEvent: "ron",
    TsumoEvent: "tsumo",
    FlowEvent: "flow",
    HandOverEvent: "hand_over",
    MatchEndEvent: "match_end",
}


def game_event_from_wire(data: dict[str, Any]) -> GameEvent:
    """dict → ``GameEvent``（与 ``game_event_to_wire`` 对偶）。"""
    et = data["event_type"]
    seq = int(data["sequence"])
    seat = data.get("seat")
    if seat is not None:
        seat = int(seat)

    if et == "round_begin":
        return RoundBeginEvent(
            seat=seat,
            sequence=seq,
            dealer_seat=int(data["dealer_seat"]),
            dora_indicator=tile_from_code(data["dora_indicator"]),
            seeds=tuple(int(x) for x in data["seeds"]),
        )
    if et == "draw_tile":
        return DrawTileEvent(
            seat=int(data["seat"]),
            sequence=seq,
            tile=tile_from_code(data["tile"]),
            is_rinshan=bool(data["is_rinshan"]),
            wall_remaining=int(data["wall_remaining"]),
        )
    if et == "discard_tile":
        return DiscardTileEvent(
            seat=int(data["seat"]),
            sequence=seq,
            tile=tile_from_code(data["tile"]),
            is_tsumogiri=bool(data["is_tsumogiri"]),
            declare_riichi=bool(data.get("declare_riichi", False)),
        )
    if et == "call":
        return CallEvent(
            seat=int(data["seat"]),
            sequence=seq,
            meld=meld_from_wire(data["meld"]),
            call_kind=str(data["call_kind"]),
        )
    if et == "ron":
        return RonEvent(
            seat=int(data["seat"]),
            sequence=seq,
            win_tile=tile_from_code(data["win_tile"]),
            discard_seat=int(data["discard_seat"]),
        )
    if et == "tsumo":
        return TsumoEvent(
            seat=int(data["seat"]),
            sequence=seq,
            win_tile=tile_from_code(data["win_tile"]),
            is_rinshan=bool(data["is_rinshan"]),
        )
    if et == "flow":
        return FlowEvent(
            seat=seat,
            sequence=seq,
            flow_kind=FlowKind(data["flow_kind"]),
            tenpai_seats=frozenset(int(x) for x in data["tenpai_seats"]),
        )
    if et == "hand_over":
        raw_lines = data.get("win_lines") or []
        win_lines = tuple(win_line_from_wire(x) for x in raw_lines)
        pays = data["payments"]
        return HandOverEvent(
            seat=seat,
            sequence=seq,
            winners=tuple(int(x) for x in data["winners"]),
            payments=tuple(int(x) for x in pays),
            win_lines=win_lines,
        )
    if et == "match_end":
        return MatchEndEvent(
            seat=seat,
            sequence=seq,
            ranking=tuple(int(x) for x in data["ranking"]),
            final_scores=tuple(int(x) for x in data["final_scores"]),
        )
    msg = f"unknown event_type: {et!r}"
    raise ValueError(msg)


def actions_from_match_log(data: dict[str, Any]) -> list[Action]:
    """从牌谱顶层 dict 解析 ``actions`` 列表。"""
    fv = int(data.get("format_version", 1))
    if fv < 1 or fv > MATCH_LOG_FORMAT_VERSION:
        msg = f"unsupported format_version: {data.get('format_version')!r}"
        raise ValueError(msg)
    raw = data.get("actions")
    if not isinstance(raw, list):
        msg = "match log missing 'actions' list"
        raise ValueError(msg)
    return [action_from_wire(x) for x in raw]


def match_log_document(
    *,
    seed: int,
    stopped_reason: str,
    steps: int,
    final_phase: str,
    actions_wire: tuple[dict[str, Any], ...],
    events_wire: tuple[dict[str, Any], ...],
    reasons: tuple[str | None, ...] | None = None,
    token_diagnostics: tuple[dict[str, Any] | None, ...] | None = None,
) -> dict[str, Any]:
    """组装 CLI/文件用的顶层牌谱 dict。"""
    doc = {
        "format_version": MATCH_LOG_FORMAT_VERSION,
        "seed": seed,
        "stopped_reason": stopped_reason,
        "steps": steps,
        "final_phase": final_phase,
        "actions": list(actions_wire),
        "events": list(events_wire),
    }
    if reasons:
        doc["reasons"] = [r for r in reasons]
    if token_diagnostics and any(item is not None for item in token_diagnostics):
        doc["token_diagnostics"] = [item for item in token_diagnostics]
    return doc
