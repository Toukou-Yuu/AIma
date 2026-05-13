"""validate.py 分支覆盖。"""

from __future__ import annotations

from kernel.api.legal_actions import LegalAction
from kernel.engine.actions import ActionKind
from kernel.tiles.model import Suit, Tile
from llm.validate import (
    _normalize_action_text,
    cn_to_tile_code,
    explain_text_from_choice,
    find_matching_legal_action,
    normalize_choice,
    parse_cn_action,
)


# ── cn_to_tile_code ──────────────────────────────────────────────────────────

def test_cn_to_tile_code_basic() -> None:
    assert cn_to_tile_code("三万") == "3m"
    assert cn_to_tile_code("东") == "1z"
    assert cn_to_tile_code("七筒") == "7p"


def test_cn_to_tile_code_red() -> None:
    assert cn_to_tile_code("五万(赤)") == "5mr"
    # 变体格式
    assert cn_to_tile_code("五筒赤") == "5pr"


def test_cn_to_tile_code_unknown() -> None:
    assert cn_to_tile_code("不存在的牌名") is None


# ── _normalize_action_text ───────────────────────────────────────────────────

def test_normalize_removes_whitespace() -> None:
    assert _normalize_action_text("打 三 万") == "打三万"


def test_normalize_fullwidth_parens() -> None:
    assert _normalize_action_text("五万（赤）") == "五万(赤)"


def test_normalize_adds_da_to_minggang() -> None:
    # "明杠" 没有"大"前缀时自动加"大"
    assert _normalize_action_text("明杠三万") == "大明杠三万"


def test_normalize_keeps_daminggang() -> None:
    assert _normalize_action_text("大明杠三万") == "大明杠三万"


# ── explain_text_from_choice ─────────────────────────────────────────────────

def test_explain_none() -> None:
    assert explain_text_from_choice({}) is None
    assert explain_text_from_choice({"why": None}) is None


def test_explain_empty_str() -> None:
    assert explain_text_from_choice({"why": "  "}) is None


def test_explain_valid_str() -> None:
    assert explain_text_from_choice({"why": "好牌"}) == "好牌"


def test_explain_non_str() -> None:
    assert explain_text_from_choice({"why": 123}) == "123"


# ── normalize_choice ─────────────────────────────────────────────────────────

def test_normalize_removes_why() -> None:
    out = normalize_choice({"kind": "draw", "seat": 0, "why": "理由"})
    assert "why" not in out
    assert out["kind"] == "draw"


def test_normalize_discard_false_riichi_removed() -> None:
    out = normalize_choice({"kind": "discard", "tile": "3m", "declare_riichi": False})
    assert "declare_riichi" not in out


def test_normalize_discard_true_riichi_kept() -> None:
    out = normalize_choice({"kind": "discard", "tile": "3m", "declare_riichi": True})
    assert out["declare_riichi"] is True


# ── parse_cn_action ──────────────────────────────────────────────────────────

def test_parse_cn_pass() -> None:
    la = LegalAction(kind=ActionKind.PASS_CALL, seat=0)
    assert parse_cn_action("过", (la,)) is la
    assert parse_cn_action("跳过", (la,)) is la


def test_parse_cn_pass_not_available() -> None:
    la = LegalAction(kind=ActionKind.DRAW, seat=0)
    assert parse_cn_action("过", (la,)) is None


def test_parse_cn_tsumo() -> None:
    la = LegalAction(kind=ActionKind.TSUMO, seat=0, tile=Tile(Suit.MAN, 1))
    assert parse_cn_action("自摸", (la,)) is la


def test_parse_cn_tsumo_not_available() -> None:
    la = LegalAction(kind=ActionKind.DRAW, seat=0)
    assert parse_cn_action("自摸", (la,)) is None


def test_parse_cn_discard() -> None:
    la = LegalAction(kind=ActionKind.DISCARD, seat=0, tile=Tile(Suit.MAN, 3), declare_riichi=False)
    assert parse_cn_action("打三万", (la,)) is la


def test_parse_cn_discard_with_riichi() -> None:
    la = LegalAction(kind=ActionKind.DISCARD, seat=0, tile=Tile(Suit.MAN, 3), declare_riichi=True)
    assert parse_cn_action("打三万并立直", (la,)) is la


def test_parse_cn_discard_riichi_mismatch() -> None:
    """期望立直但实际动作无立直 -> 不匹配."""
    la = LegalAction(kind=ActionKind.DISCARD, seat=0, tile=Tile(Suit.MAN, 3), declare_riichi=False)
    assert parse_cn_action("打三万并立直", (la,)) is None


def test_parse_cn_discard_unknown_tile() -> None:
    la = LegalAction(kind=ActionKind.DISCARD, seat=0, tile=Tile(Suit.MAN, 3), declare_riichi=False)
    assert parse_cn_action("打九十九万", (la,)) is None


def test_parse_cn_ron_with_tile() -> None:
    la = LegalAction(kind=ActionKind.RON, seat=0, tile=Tile(Suit.MAN, 5))
    assert parse_cn_action("荣和五万", (la,)) is la


def test_parse_cn_ron_without_tile() -> None:
    """未指定牌名 -> 匹配任意荣和."""
    la = LegalAction(kind=ActionKind.RON, seat=0, tile=Tile(Suit.MAN, 5))
    assert parse_cn_action("荣和", (la,)) is la


def test_parse_cn_ron_tile_mismatch() -> None:
    la = LegalAction(kind=ActionKind.RON, seat=0, tile=Tile(Suit.MAN, 5))
    assert parse_cn_action("荣和三万", (la,)) is None


def test_parse_cn_unknown_returns_none() -> None:
    la = LegalAction(kind=ActionKind.DRAW, seat=0)
    assert parse_cn_action("完全未知动作", (la,)) is None


# ── find_matching_legal_action ───────────────────────────────────────────────

def test_find_matching_old_format() -> None:
    la = LegalAction(kind=ActionKind.DRAW, seat=0)
    choice = {"kind": "draw", "seat": 0}
    assert find_matching_legal_action((la,), choice) is la


def test_find_matching_old_format_miss() -> None:
    la = LegalAction(kind=ActionKind.DRAW, seat=0)
    choice = {"kind": "discard", "seat": 0, "tile": "1m"}
    assert find_matching_legal_action((la,), choice) is None


def test_find_matching_nested_dict() -> None:
    la = LegalAction(kind=ActionKind.DRAW, seat=0)
    choice = {"action": {"kind": "draw", "seat": 0}, "why": "理由"}
    assert find_matching_legal_action((la,), choice) is la


def test_find_matching_string_action_pass() -> None:
    la = LegalAction(kind=ActionKind.PASS_CALL, seat=0)
    choice = {"action": "过"}
    assert find_matching_legal_action((la,), choice) is la


def test_find_matching_string_action_miss() -> None:
    la = LegalAction(kind=ActionKind.DRAW, seat=0)
    choice = {"action": "过"}
    assert find_matching_legal_action((la,), choice) is None


def test_find_matching_no_action_field_falls_to_old() -> None:
    """没有 action 字段时回退到旧格式匹配."""
    la = LegalAction(kind=ActionKind.DISCARD, seat=0, tile=Tile(Suit.PIN, 4), declare_riichi=False)
    choice = {"kind": "discard", "seat": 0, "tile": "4p"}
    assert find_matching_legal_action((la,), choice) is la
