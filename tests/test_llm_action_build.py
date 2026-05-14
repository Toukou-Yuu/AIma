"""action_build 覆盖：LegalAction -> Action 各分支。"""

from __future__ import annotations

from kernel.api.legal_actions import LegalAction
from kernel.engine.actions import ActionKind
from kernel.hand.melds import Meld, MeldKind
from kernel.tiles.model import Suit, Tile
from llm.action_build import legal_action_to_action


def test_noop() -> None:
    la = LegalAction(kind=ActionKind.NOOP, seat=0)
    a = legal_action_to_action(la)
    assert a.kind == ActionKind.NOOP
    assert a.seat == 0


def test_draw() -> None:
    la = LegalAction(kind=ActionKind.DRAW, seat=2)
    a = legal_action_to_action(la)
    assert a.kind == ActionKind.DRAW
    assert a.seat == 2


def test_discard() -> None:
    la = LegalAction(kind=ActionKind.DISCARD, seat=1, tile=Tile(Suit.PIN, 5), declare_riichi=True)
    a = legal_action_to_action(la)
    assert a.kind == ActionKind.DISCARD
    assert a.tile == Tile(Suit.PIN, 5)
    assert a.declare_riichi is True


def test_discard_missing_tile_raises() -> None:
    la = LegalAction(kind=ActionKind.DISCARD, seat=0, tile=None)
    try:
        legal_action_to_action(la)
    except ValueError as e:
        assert "tile" in str(e).lower()
    else:
        raise AssertionError("应抛出 ValueError")


def test_pass_call() -> None:
    la = LegalAction(kind=ActionKind.PASS_CALL, seat=3)
    a = legal_action_to_action(la)
    assert a.kind == ActionKind.PASS_CALL
    assert a.seat == 3


def test_ron() -> None:
    la = LegalAction(kind=ActionKind.RON, seat=2)
    a = legal_action_to_action(la)
    assert a.kind == ActionKind.RON
    assert a.seat == 2


def test_tsumo() -> None:
    tile = Tile(Suit.MAN, 1)
    la = LegalAction(kind=ActionKind.TSUMO, seat=0, tile=tile)
    a = legal_action_to_action(la)
    assert a.kind == ActionKind.TSUMO
    assert a.tile == tile


def test_open_meld() -> None:
    meld = Meld(
        kind=MeldKind.PON,
        tiles=(Tile(Suit.SOU, 7), Tile(Suit.SOU, 7), Tile(Suit.SOU, 7)),
        called_tile=Tile(Suit.SOU, 7),
        from_seat=2,
    )
    la = LegalAction(kind=ActionKind.OPEN_MELD, seat=1, meld=meld)
    a = legal_action_to_action(la)
    assert a.kind == ActionKind.OPEN_MELD
    assert a.meld is meld


def test_open_meld_missing_meld_raises() -> None:
    la = LegalAction(kind=ActionKind.OPEN_MELD, seat=1, meld=None)
    try:
        legal_action_to_action(la)
    except ValueError as e:
        assert "meld" in str(e).lower()
    else:
        raise AssertionError("应抛出 ValueError")


def test_ankan() -> None:
    meld = Meld(
        kind=MeldKind.ANKAN,
        tiles=(Tile(Suit.PIN, 2), Tile(Suit.PIN, 2), Tile(Suit.PIN, 2), Tile(Suit.PIN, 2)),
    )
    la = LegalAction(kind=ActionKind.ANKAN, seat=0, meld=meld)
    a = legal_action_to_action(la)
    assert a.kind == ActionKind.ANKAN
    assert a.meld is meld


def test_ankan_missing_meld_raises() -> None:
    la = LegalAction(kind=ActionKind.ANKAN, seat=0, meld=None)
    try:
        legal_action_to_action(la)
    except ValueError as e:
        assert "meld" in str(e).lower()
    else:
        raise AssertionError("应抛出 ValueError")


def test_kakan() -> None:
    meld = Meld(
        kind=MeldKind.KAKAN,
        tiles=(Tile(Suit.MAN, 9), Tile(Suit.MAN, 9), Tile(Suit.MAN, 9), Tile(Suit.MAN, 9)),
    )
    la = LegalAction(kind=ActionKind.KAKAN, seat=3, meld=meld)
    a = legal_action_to_action(la)
    assert a.kind == ActionKind.KAKAN
    assert a.meld is meld


def test_kakan_missing_meld_raises() -> None:
    la = LegalAction(kind=ActionKind.KAKAN, seat=3, meld=None)
    try:
        legal_action_to_action(la)
    except ValueError as e:
        assert "meld" in str(e).lower()
    else:
        raise AssertionError("应抛出 ValueError")
