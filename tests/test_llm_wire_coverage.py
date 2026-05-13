"""wire.py 分支覆盖。"""

from __future__ import annotations

from kernel.api.legal_actions import LegalAction
from kernel.engine.actions import ActionKind
from kernel.hand.melds import Meld, MeldKind
from kernel.tiles.model import Suit, Tile
from llm.wire import (
    legal_action_to_wire,
    meld_from_wire,
    meld_to_wire,
    tile_from_code,
    wire_to_action,
    wire_to_legal_action,
)


# ── tile_from_code ───────────────────────────────────────────────────────────

def test_tile_from_code_man() -> None:
    t = tile_from_code("3m")
    assert t == Tile(Suit.MAN, 3)


def test_tile_from_code_pin() -> None:
    t = tile_from_code("7p")
    assert t == Tile(Suit.PIN, 7)


def test_tile_from_code_sou() -> None:
    t = tile_from_code("1s")
    assert t == Tile(Suit.SOU, 1)


def test_tile_from_code_red() -> None:
    t = tile_from_code("5pr")
    assert t == Tile(Suit.PIN, 5, True)


def test_tile_from_code_red_non5_raises() -> None:
    try:
        tile_from_code("3mr")
    except ValueError as e:
        assert "red" in str(e).lower()
    else:
        raise AssertionError("应抛出 ValueError")


def test_tile_from_code_honor() -> None:
    t = tile_from_code("4z")
    assert t == Tile(Suit.HONOR, 4)


def test_tile_from_code_honor_east() -> None:
    t = tile_from_code("1z")
    assert t == Tile(Suit.HONOR, 1)


def test_tile_from_code_honor_chun() -> None:
    t = tile_from_code("7z")
    assert t == Tile(Suit.HONOR, 7)


def test_tile_from_code_invalid_raises() -> None:
    try:
        tile_from_code("xyz")
    except ValueError as e:
        assert "invalid tile code" in str(e)
    else:
        raise AssertionError("应抛出 ValueError")


def test_tile_from_code_strips_whitespace() -> None:
    t = tile_from_code("  5m  ")
    assert t == Tile(Suit.MAN, 5)


# ── meld_from_wire / meld_to_wire roundtrip ──────────────────────────────────

def test_meld_roundtrip_chi() -> None:
    wire = {
        "kind": "chi",
        "tiles": ["1m", "2m", "3m"],
        "called_tile": "3m",
        "from_seat": 0,
    }
    m = meld_from_wire(wire)
    assert m.kind == MeldKind.CHI
    assert len(m.tiles) == 3
    assert m.called_tile == Tile(Suit.MAN, 3)
    assert m.from_seat == 0
    back = meld_to_wire(m)
    assert back["kind"] == "chi"
    assert back["called_tile"] == "3m"
    assert back["from_seat"] == 0


def test_meld_roundtrip_ankan() -> None:
    wire = {"kind": "ankan", "tiles": ["5z", "5z", "5z", "5z"]}
    m = meld_from_wire(wire)
    assert m.kind == MeldKind.ANKAN
    assert m.called_tile is None
    assert m.from_seat is None
    back = meld_to_wire(m)
    assert "called_tile" not in back
    assert "from_seat" not in back


def test_meld_from_wire_pon() -> None:
    wire = {"kind": "pon", "tiles": ["9s", "9s", "9s"], "called_tile": "9s", "from_seat": 2}
    m = meld_from_wire(wire)
    assert m.kind == MeldKind.PON
    assert m.from_seat == 2


# ── legal_action_to_wire ─────────────────────────────────────────────────────

def test_legal_action_to_wire_discard_with_riichi() -> None:
    la = LegalAction(kind=ActionKind.DISCARD, seat=0, tile=Tile(Suit.MAN, 3), declare_riichi=True)
    d = legal_action_to_wire(la)
    assert d["kind"] == "discard"
    assert d["tile"] == "3m"
    assert d["declare_riichi"] is True


def test_legal_action_to_wire_discard_no_riichi() -> None:
    la = LegalAction(kind=ActionKind.DISCARD, seat=1, tile=Tile(Suit.PIN, 8), declare_riichi=False)
    d = legal_action_to_wire(la)
    assert "declare_riichi" not in d


def test_legal_action_to_wire_with_meld() -> None:
    meld = Meld(
        kind=MeldKind.CHI,
        tiles=(Tile(Suit.MAN, 1), Tile(Suit.MAN, 2), Tile(Suit.MAN, 3)),
        called_tile=Tile(Suit.MAN, 1),
        from_seat=3,
    )
    la = LegalAction(kind=ActionKind.OPEN_MELD, seat=0, meld=meld)
    d = legal_action_to_wire(la)
    assert d["kind"] == "open_meld"
    assert "meld" in d
    assert d["meld"]["kind"] == "chi"


# ── wire_to_action ───────────────────────────────────────────────────────────

def test_wire_to_action_discard() -> None:
    a = wire_to_action({"kind": "discard", "seat": 0, "tile": "3m", "declare_riichi": True})
    assert a.kind == ActionKind.DISCARD
    assert a.seat == 0
    assert a.tile == Tile(Suit.MAN, 3)
    assert a.declare_riichi is True


def test_wire_to_action_noop() -> None:
    a = wire_to_action({"kind": "noop"})
    assert a.kind == ActionKind.NOOP
    assert a.seat is None


def test_wire_to_action_with_meld() -> None:
    data = {
        "kind": "open_meld",
        "seat": 1,
        "meld": {"kind": "pon", "tiles": ["2z", "2z", "2z"], "called_tile": "2z", "from_seat": 3},
    }
    a = wire_to_action(data)
    assert a.kind == ActionKind.OPEN_MELD
    assert a.meld is not None
    assert a.meld.kind == MeldKind.PON


def test_wire_to_action_with_wall() -> None:
    data = {"kind": "begin_round", "wall": ["1m", "2m", "3m"]}
    a = wire_to_action(data)
    assert a.wall is not None
    assert len(a.wall) == 3


# ── wire_to_legal_action ─────────────────────────────────────────────────────

def test_wire_to_legal_action_draw() -> None:
    la = wire_to_legal_action({"kind": "draw", "seat": 2})
    assert la.kind == ActionKind.DRAW
    assert la.seat == 2


def test_wire_to_legal_action_discard() -> None:
    la = wire_to_legal_action({"kind": "discard", "seat": 0, "tile": "5p", "declare_riichi": True})
    assert la.kind == ActionKind.DISCARD
    assert la.tile == Tile(Suit.PIN, 5)
    assert la.declare_riichi is True


def test_wire_to_legal_action_with_meld() -> None:
    data = {
        "kind": "ankan",
        "seat": 3,
        "meld": {"kind": "ankan", "tiles": ["7m", "7m", "7m", "7m"]},
    }
    la = wire_to_legal_action(data)
    assert la.kind == ActionKind.ANKAN
    assert la.meld is not None
    assert la.meld.kind == MeldKind.ANKAN
