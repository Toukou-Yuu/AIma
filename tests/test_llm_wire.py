"""llm.wire 牌码与 LegalAction wire 往返。"""

from __future__ import annotations

from kernel.api.legal_actions import LegalAction
from kernel.engine.actions import ActionKind
from kernel.tiles import Tile
from kernel.tiles.model import Suit
from llm.wire import legal_action_to_wire, tile_from_code, wire_to_action


def test_tile_from_code_red() -> None:
    t = tile_from_code("5pr")
    assert t.suit == Suit.PIN and t.rank == 5 and t.is_red


def test_legal_action_wire_discard_roundtrip() -> None:
    la = LegalAction(
        kind=ActionKind.DISCARD,
        seat=2,
        tile=Tile(Suit.MAN, 4, False),
        declare_riichi=False,
    )
    w = legal_action_to_wire(la)
    assert w == {"kind": "discard", "seat": 2, "tile": "4m"}
    act = wire_to_action({**w, "declare_riichi": False})
    assert act.kind == ActionKind.DISCARD
    assert act.seat == 2
    assert act.tile == la.tile


def test_pass_call_wire() -> None:
    la = LegalAction(kind=ActionKind.PASS_CALL, seat=1)
    assert legal_action_to_wire(la) == {"kind": "pass_call", "seat": 1}
