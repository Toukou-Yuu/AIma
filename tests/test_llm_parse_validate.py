"""解析与合法动作匹配。"""

from __future__ import annotations

from kernel.api.legal_actions import LegalAction
from kernel.engine.actions import ActionKind
from kernel.tiles import Tile
from kernel.tiles.model import Suit
from llm.parse import extract_json_object
from llm.validate import find_matching_legal_action, normalize_choice


def test_extract_json_with_fence() -> None:
    text = '说明\n```json\n{"kind":"draw","seat":0}\n```\n'
    assert extract_json_object(text) == {"kind": "draw", "seat": 0}


def test_find_matching() -> None:
    a = LegalAction(kind=ActionKind.DRAW, seat=0)
    b = LegalAction(
        kind=ActionKind.DISCARD,
        seat=0,
        tile=Tile(Suit.SOU, 8, False),
        declare_riichi=False,
    )
    legal = (a, b)
    assert find_matching_legal_action(legal, {"kind": "draw", "seat": 0}) == a
    assert find_matching_legal_action(legal, {"kind": "discard", "seat": 0, "tile": "8s"}) == b
    assert find_matching_legal_action(legal, {"kind": "discard", "seat": 1, "tile": "8s"}) is None


def test_find_matching_ignores_why_field() -> None:
    a = LegalAction(kind=ActionKind.DRAW, seat=0)
    legal = (a,)
    choice = {"kind": "draw", "seat": 0, "why": "先摸一张"}
    assert find_matching_legal_action(legal, choice) == a
    assert "why" not in normalize_choice(choice)
