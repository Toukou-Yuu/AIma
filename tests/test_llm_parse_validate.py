"""解析与合法动作匹配。"""

from __future__ import annotations

from kernel.api.legal_actions import LegalAction
from kernel.engine.actions import ActionKind
from kernel.tiles import Tile
from kernel.tiles.model import Suit
from llm.agent.decision_parser import DecisionParser
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


def test_decision_parser_detail_marks_fenced_json() -> None:
    action = LegalAction(kind=ActionKind.DRAW, seat=0)
    raw = '```json\n{"kind":"draw","seat":0,"why":"唯一动作"}\n```'

    result = DecisionParser.parse_llm_response_detail(raw, (action,))

    assert result.status == "matched"
    assert result.action == action
    assert result.why == "唯一动作"
    assert result.note == "fenced_json_accepted"


def test_decision_parser_detail_reports_empty_response() -> None:
    action = LegalAction(kind=ActionKind.DRAW, seat=0)

    result = DecisionParser.parse_llm_response_detail("", (action,))

    assert result.status == "parse_failed"
    assert result.action is None
    assert result.error


def test_decision_parser_legacy_api_hides_unmatched_why() -> None:
    action = LegalAction(kind=ActionKind.DRAW, seat=0)
    raw = '{"kind":"discard","seat":0,"tile":"1m","why":"非法动作"}'

    detail = DecisionParser.parse_llm_response_detail(raw, (action,))
    legacy_action, legacy_why = DecisionParser.parse_llm_response(raw, (action,))

    assert detail.status == "match_failed"
    assert detail.why == "非法动作"
    assert legacy_action is None
    assert legacy_why is None
