"""decision_parser.py 边界覆盖。"""

from __future__ import annotations

from kernel.api.legal_actions import LegalAction
from kernel.engine.actions import ActionKind
from kernel.tiles.model import Suit, Tile
from llm.agent.decision_parser import DecisionParser


def test_validate_decision_in_list() -> None:
    la = LegalAction(kind=ActionKind.DRAW, seat=0)
    assert DecisionParser.validate_decision(la, (la,)) is True


def test_validate_decision_not_in_list() -> None:
    la1 = LegalAction(kind=ActionKind.DRAW, seat=0)
    la2 = LegalAction(kind=ActionKind.DISCARD, seat=0, tile=Tile(Suit.MAN, 1))
    assert DecisionParser.validate_decision(la1, (la2,)) is False


def test_fallback_action_returns_first() -> None:
    la = LegalAction(kind=ActionKind.PASS_CALL, seat=0)
    assert DecisionParser.fallback_action((la,)) is la


def test_fallback_action_empty_raises() -> None:
    try:
        DecisionParser.fallback_action(())
    except RuntimeError as e:
        assert "no legal_actions" in str(e)
    else:
        raise AssertionError("应抛出 RuntimeError")


def test_choice_to_wire() -> None:
    d = {"kind": "draw", "seat": 0}
    s = DecisionParser.choice_to_wire(d)
    assert '"kind"' in s
    assert '"draw"' in s


def test_choice_to_wire_unicode() -> None:
    d = {"action": "打三万", "why": "理由"}
    s = DecisionParser.choice_to_wire(d)
    assert "打三万" in s
    # ensure_ascii=False 应保留中文
    assert "\\u" not in s


def test_parse_llm_response_detail_non_dict_json() -> None:
    """根为数组的 JSON -> parse_failed."""
    la = LegalAction(kind=ActionKind.DRAW, seat=0)
    result = DecisionParser.parse_llm_response_detail("[1, 2, 3]", (la,))
    assert result.status == "parse_failed"
    assert result.action is None


def test_parse_llm_response_detail_no_json() -> None:
    """完全无 JSON 的文本 -> parse_failed."""
    la = LegalAction(kind=ActionKind.DRAW, seat=0)
    result = DecisionParser.parse_llm_response_detail("没有任何JSON", (la,))
    assert result.status == "parse_failed"
    assert result.action is None
