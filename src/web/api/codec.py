"""Tile / Meld / Action 与 JSON 可逆编解码（wire 格式 = ``Tile.to_code()``）。"""

from __future__ import annotations

import re
from typing import Any

from kernel.api.legal_actions import LegalAction
from kernel.engine.actions import Action, ActionKind
from kernel.hand.melds import Meld, MeldKind
from kernel.tiles.model import Suit, Tile

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


def meld_from_payload(data: dict[str, Any]) -> Meld:
    """JSON 对象 → ``Meld``。"""
    kind = MeldKind(data["kind"])
    tiles = tuple(tile_from_code(x) for x in data["tiles"])
    called = tile_from_code(data["called_tile"]) if data.get("called_tile") else None
    from_seat = data.get("from_seat")
    if from_seat is not None:
        from_seat = int(from_seat)
    return Meld(kind=kind, tiles=tiles, called_tile=called, from_seat=from_seat)


def meld_to_payload(meld: Meld) -> dict[str, Any]:
    out: dict[str, Any] = {
        "kind": meld.kind.value,
        "tiles": [t.to_code() for t in meld.tiles],
    }
    if meld.called_tile is not None:
        out["called_tile"] = meld.called_tile.to_code()
    if meld.from_seat is not None:
        out["from_seat"] = meld.from_seat
    return out


def action_from_payload(data: dict[str, Any]) -> Action:
    """请求体 → ``Action``。"""
    kind = ActionKind(data["kind"])
    seat = data.get("seat")
    if seat is not None:
        seat = int(seat)
    wall = None
    if data.get("wall") is not None:
        wall = tuple(tile_from_code(x) for x in data["wall"])
    tile = tile_from_code(data["tile"]) if data.get("tile") else None
    declare_riichi = bool(data.get("declare_riichi", False))
    meld = meld_from_payload(data["meld"]) if data.get("meld") else None
    return Action(
        kind=kind,
        seat=seat,
        wall=wall,
        tile=tile,
        declare_riichi=declare_riichi,
        meld=meld,
    )


def legal_action_to_payload(la: LegalAction) -> dict[str, Any]:
    """``LegalAction`` → 可 JSON 化的 dict（与提交 ``Action`` 字段兼容）。"""
    d: dict[str, Any] = {"kind": la.kind.value, "seat": la.seat}
    if la.tile is not None:
        d["tile"] = la.tile.to_code()
    if la.meld is not None:
        d["meld"] = meld_to_payload(la.meld)
    if la.declare_riichi:
        d["declare_riichi"] = True
    return d
