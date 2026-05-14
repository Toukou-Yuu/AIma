"""llm.table_snapshot_text 覆盖缺口测试。

覆盖：_tile_sort_key, _tiles_sorted_str, _counter_sorted_str,
_wind_seat_label, _absolute_seat_suffix, _seat_wind_name,
_discarder_seat_for_meld, _meld_segment (各 MeldKind), _melds_line,
_river_line_for_seat, action_wire_to_cn, format_hand_over_section,
format_flow_section。"""

from __future__ import annotations

from collections import Counter

from kernel.deal.model import BoardState
from kernel.event_log import FlowEvent, HandOverEvent, WinSettlementLine
from kernel.flow.model import FlowKind
from kernel.hand.melds import Meld, MeldKind
from kernel.play.model import RiverEntry
from kernel.tiles.model import Suit, Tile
from llm.table_snapshot_text import (
    _absolute_seat_suffix,
    _counter_sorted_str,
    _discarder_seat_for_meld,
    _meld_segment,
    _melds_line,
    _river_line_for_seat,
    _seat_wind_name,
    _tile_sort_key,
    _tiles_sorted_str,
    _wind_seat_label,
    action_wire_to_cn,
    format_flow_section,
    format_hand_over_section,
)

MAN1 = Tile(Suit.MAN, 1)
MAN2 = Tile(Suit.MAN, 2)
MAN3 = Tile(Suit.MAN, 3)
MAN5 = Tile(Suit.MAN, 5)
MAN5R = Tile(Suit.MAN, 5, is_red=True)
PIN3 = Tile(Suit.PIN, 3)
PIN5 = Tile(Suit.PIN, 5)
SOU5 = Tile(Suit.SOU, 5)
TON = Tile(Suit.HONOR, 1)
NAN = Tile(Suit.HONOR, 2)
HAKU = Tile(Suit.HONOR, 5)


# --- _tile_sort_key ---

class TestTileSortKey:
    def test_man_before_pin(self) -> None:
        assert _tile_sort_key(MAN1) < _tile_sort_key(PIN3)

    def test_same_suit_lower_rank_first(self) -> None:
        assert _tile_sort_key(MAN1) < _tile_sort_key(MAN5)

    def test_red_after_normal(self) -> None:
        assert _tile_sort_key(MAN5) < _tile_sort_key(MAN5R)

    def test_honor_order(self) -> None:
        assert _tile_sort_key(TON) < _tile_sort_key(NAN)


# --- _tiles_sorted_str ---

class TestTilesSortedStr:
    def test_sorts_tiles(self) -> None:
        result = _tiles_sorted_str([PIN5, MAN1, SOU5])
        assert result.index("1m") < result.index("5p")
        assert result.index("5p") < result.index("5s")

    def test_empty(self) -> None:
        assert _tiles_sorted_str([]) == ""

    def test_red_five(self) -> None:
        result = _tiles_sorted_str([MAN5R, MAN5])
        assert "5mr" in result
        assert "5m" in result


# --- _counter_sorted_str ---

class TestCounterSortedStr:
    def test_basic(self) -> None:
        c = Counter({MAN1: 2, PIN5: 1})
        result = _counter_sorted_str(c)
        assert result.count("1m") == 2
        assert "5p" in result

    def test_empty(self) -> None:
        assert _counter_sorted_str(Counter()) == ""


# --- _wind_seat_label ---

class TestWindSeatLabel:
    def test_dealer_is_east(self) -> None:
        assert _wind_seat_label(0, 0) == "东"

    def test_next_seat_is_south(self) -> None:
        assert _wind_seat_label(0, 1) == "南"

    def test_wrap_around(self) -> None:
        assert _wind_seat_label(1, 0) == "北"


# --- _absolute_seat_suffix ---

class TestAbsoluteSeatSuffix:
    def test_seat_0(self) -> None:
        assert _absolute_seat_suffix(0) == "(S0)"

    def test_seat_3(self) -> None:
        assert _absolute_seat_suffix(3) == "(S3)"


# --- _seat_wind_name ---

class TestSeatWindName:
    def test_dealer(self) -> None:
        assert _seat_wind_name(0, 0) == "东家"

    def test_none_seat(self) -> None:
        assert _seat_wind_name(0, None) == "（未知席）"

    def test_south(self) -> None:
        assert _seat_wind_name(0, 1) == "南家"


# --- _discarder_seat_for_meld ---

class TestDiscarderSeatForMeld:
    def test_from_seat_none(self) -> None:
        m = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5))
        assert _discarder_seat_for_meld(0, m) is None

    def test_chi_from_seat_1(self) -> None:
        m = Meld(MeldKind.CHI, (MAN1, MAN2, MAN3), MAN2, from_seat=3)
        # (0 + 3) % 4 = 3
        assert _discarder_seat_for_meld(0, m) == 3

    def test_pon_wrap(self) -> None:
        m = Meld(MeldKind.PON, (TON, TON, TON), TON, from_seat=2)
        # (3 + 2) % 4 = 1
        assert _discarder_seat_for_meld(3, m) == 1


# --- _meld_segment ---

class TestMeldSegment:
    def test_ankan(self) -> None:
        m = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5))
        result = _meld_segment(m, 0, 0)
        assert "暗杠" in result

    def test_kakan(self) -> None:
        m = Meld(MeldKind.KAKAN, (MAN5, MAN5, MAN5, MAN5))
        result = _meld_segment(m, 0, 0)
        assert "加杠" in result

    def test_chi(self) -> None:
        m = Meld(MeldKind.CHI, (MAN1, MAN2, MAN3), MAN2, from_seat=3)
        result = _meld_segment(m, 0, 0)
        assert "吃" in result
        assert "北家" in result

    def test_pon(self) -> None:
        m = Meld(MeldKind.PON, (TON, TON, TON), TON, from_seat=1)
        result = _meld_segment(m, 0, 0)
        assert "碰" in result
        assert "南家" in result

    def test_daiminkan(self) -> None:
        m = Meld(MeldKind.DAIMINKAN, (MAN5, MAN5, MAN5, MAN5), MAN5, from_seat=2)
        result = _meld_segment(m, 0, 0)
        assert "大明杠" in result
        assert "西家" in result


# --- _melds_line ---

class TestMeldsLine:
    def test_no_melds(self) -> None:
        board = _make_board(melds=((), (), (), ()))
        assert _melds_line(board, 0, 0) == "副露：无"

    def test_with_meld(self) -> None:
        m = Meld(MeldKind.CHI, (MAN1, MAN2, MAN3), MAN2, from_seat=1)
        board = _make_board(melds=((m,), (), (), ()))
        result = _melds_line(board, 0, 0)
        assert "副露：" in result
        assert "吃" in result


# --- _river_line_for_seat ---

class TestRiverLineForSeat:
    def test_empty_river(self) -> None:
        board = _make_board(river=())
        assert _river_line_for_seat(board, 0) == ""

    def test_hand_cut(self) -> None:
        river = (RiverEntry(seat=0, tile=MAN1, tsumogiri=False, riichi=False),)
        board = _make_board(river=river)
        result = _river_line_for_seat(board, 0)
        assert result == "1m"

    def test_tsumogiri(self) -> None:
        river = (RiverEntry(seat=0, tile=PIN5, tsumogiri=True, riichi=False),)
        board = _make_board(river=river)
        result = _river_line_for_seat(board, 0)
        assert result == "<5p>"

    def test_riichi(self) -> None:
        river = (RiverEntry(seat=0, tile=SOU5, tsumogiri=False, riichi=True),)
        board = _make_board(river=river)
        result = _river_line_for_seat(board, 0)
        assert result == "[5s]"

    def test_filters_other_seats(self) -> None:
        river = (
            RiverEntry(seat=0, tile=MAN1, tsumogiri=False, riichi=False),
            RiverEntry(seat=1, tile=PIN5, tsumogiri=False, riichi=False),
        )
        board = _make_board(river=river)
        result = _river_line_for_seat(board, 0)
        assert "5p" not in result
        assert "1m" in result


# --- action_wire_to_cn ---

class TestActionWireToCn:
    def test_begin_round(self) -> None:
        assert "开局" in action_wire_to_cn({"kind": "begin_round"})

    def test_noop(self) -> None:
        assert "洗混" in action_wire_to_cn({"kind": "noop"})

    def test_draw(self) -> None:
        result = action_wire_to_cn({"kind": "draw", "seat": 0}, dealer_seat=0)
        assert "东家" in result
        assert "摸牌" in result

    def test_discard(self) -> None:
        result = action_wire_to_cn({"kind": "discard", "seat": 1, "tile": "3m"}, dealer_seat=0)
        assert "南家" in result
        assert "打牌" in result
        assert "3m" in result

    def test_discard_with_riichi(self) -> None:
        result = action_wire_to_cn(
            {"kind": "discard", "seat": 0, "tile": "1m", "declare_riichi": True},
            dealer_seat=0,
        )
        assert "立直" in result

    def test_discard_with_draw_tile(self) -> None:
        result = action_wire_to_cn(
            {"kind": "discard", "seat": 0, "tile": "3m"},
            dealer_seat=0,
            draw_tile_code="9m",
        )
        assert "摸9m" in result

    def test_pass_call(self) -> None:
        result = action_wire_to_cn({"kind": "pass_call", "seat": 0}, dealer_seat=0)
        assert "PASS" in result

    def test_call_pass_drain(self) -> None:
        result = action_wire_to_cn({"kind": "call_pass_drain"})
        assert "CALL_PASS_DRAIN" in result

    def test_ron(self) -> None:
        result = action_wire_to_cn({"kind": "ron", "seat": 2}, dealer_seat=0)
        assert "荣和" in result

    def test_tsumo(self) -> None:
        result = action_wire_to_cn({"kind": "tsumo", "seat": 0}, dealer_seat=0)
        assert "自摸" in result

    def test_open_meld(self) -> None:
        result = action_wire_to_cn(
            {"kind": "open_meld", "seat": 1, "meld": {"kind": "chi", "tiles": ["1m", "2m", "3m"]}},
            dealer_seat=0,
        )
        assert "吃" in result

    def test_ankan(self) -> None:
        result = action_wire_to_cn(
            {"kind": "ankan", "seat": 0, "meld": {"tiles": ["5m", "5m", "5m", "5m"]}},
            dealer_seat=0,
        )
        assert "暗杠" in result

    def test_kakan(self) -> None:
        result = action_wire_to_cn(
            {"kind": "kakan", "seat": 0, "meld": {"tiles": ["5m", "5m", "5m", "5m"]}},
            dealer_seat=0,
        )
        assert "加杠" in result

    def test_unknown_kind(self) -> None:
        result = action_wire_to_cn({"kind": "unknown_xyz", "seat": 0})
        assert "unknown_xyz" in result


# --- format_hand_over_section ---

class TestFormatHandOverSection:
    def test_no_hand_over_event(self) -> None:
        assert format_hand_over_section((), 0) is None

    def test_hand_over_with_win_lines(self) -> None:
        wl = WinSettlementLine(
            seat=0, win_kind="tsumo", han=3, fu=30,
            hand_pattern="一般形", yakus=("断么九", "ドラ1"), points=8000,
        )
        ho = HandOverEvent(seat=0, sequence=1, winners=(0,), payments=(8000, -2000, -3000, -3000), win_lines=(wl,))
        result = format_hand_over_section((ho,), 0)
        assert result is not None
        assert "和了" in result
        assert "自摸" in result
        assert "3番" in result

    def test_hand_over_ron(self) -> None:
        wl = WinSettlementLine(
            seat=1, win_kind="ron", han=4, fu=40,
            hand_pattern="一般形", yakus=("立直", "一発"), points=8000,
        )
        ho = HandOverEvent(seat=0, sequence=1, winners=(1,), payments=(0, 8000, 0, -8000), win_lines=(wl,))
        result = format_hand_over_section((ho,), 0)
        assert result is not None
        assert "荣和" in result

    def test_hand_over_fallback_winners(self) -> None:
        ho = HandOverEvent(seat=0, sequence=1, winners=(0,), payments=(8000, -2000, -3000, -3000), win_lines=())
        result = format_hand_over_section((ho,), 0)
        assert result is not None
        assert "东家" in result

    def test_hand_over_no_winners_no_win_lines(self) -> None:
        ho = HandOverEvent(seat=0, sequence=1, winners=(), payments=(0, 0, 0, 0), win_lines=())
        assert format_hand_over_section((ho,), 0) is None


# --- format_flow_section ---

class TestFormatFlowSection:
    def test_no_flow_event(self) -> None:
        assert format_flow_section((), 0) is None

    def test_exhausted_flow(self) -> None:
        fe = FlowEvent(seat=None, sequence=1, flow_kind=FlowKind.EXHAUSTED, tenpai_seats=frozenset({0, 1}))
        result = format_flow_section((fe,), 0)
        assert result is not None
        assert "荒牌" in result
        assert "听牌" in result

    def test_flow_no_tenpai(self) -> None:
        fe = FlowEvent(seat=None, sequence=1, flow_kind=FlowKind.EXHAUSTED, tenpai_seats=frozenset())
        result = format_flow_section((fe,), 0)
        assert result is not None
        assert "四家均未听牌" in result

    def test_nine_nine_flow(self) -> None:
        fe = FlowEvent(seat=None, sequence=1, flow_kind=FlowKind.NINE_NINE, tenpai_seats=frozenset())
        result = format_flow_section((fe,), 0)
        assert result is not None
        assert "九种九牌" in result


# --- helpers ---

def _make_board(
    *,
    melds: tuple = ((), (), (), ()),
    river: tuple = (),
) -> BoardState:
    """构造最小 BoardState 用于 _melds_line / _river_line_for_seat 测试。"""
    from kernel.wall.split import DeadWall

    hands = (
        Counter({MAN1: 4, MAN2: 2, MAN3: 1, PIN5: 1, SOU5: 1, TON: 1, NAN: 1, HAKU: 1, MAN5: 1, PIN3: 1}),
        Counter({MAN1: 13}),
        Counter({MAN1: 13}),
        Counter({MAN1: 13}),
    )
    # 简化：不走 __post_init__ 校验，直接构造
    wall = tuple(Tile(Suit.MAN, 1) for _ in range(69))
    dw = DeadWall(
        rinshan=(Tile(Suit.MAN, 1),) * 6,
        ura_bases=(Tile(Suit.MAN, 1),) * 4,
        indicators=(Tile(Suit.MAN, 5),) * 4,
    )
    board = object.__new__(BoardState)
    object.__setattr__(board, 'hands', hands)
    object.__setattr__(board, 'live_wall', wall)
    object.__setattr__(board, 'live_draw_index', 0)
    object.__setattr__(board, 'dead_wall', dw)
    object.__setattr__(board, 'revealed_indicators', (Tile(Suit.MAN, 5),))
    object.__setattr__(board, 'current_seat', 0)
    object.__setattr__(board, 'turn_phase', None)
    object.__setattr__(board, 'river', river)
    object.__setattr__(board, 'melds', melds)
    object.__setattr__(board, 'last_draw_tile', None)
    object.__setattr__(board, 'last_draw_was_rinshan', False)
    object.__setattr__(board, 'rinshan_draw_index', 0)
    object.__setattr__(board, 'call_state', None)
    object.__setattr__(board, 'riichi', (False, False, False, False))
    object.__setattr__(board, 'ippatsu_eligible', frozenset())
    object.__setattr__(board, 'double_riichi', frozenset())
    object.__setattr__(board, 'all_discards_per_seat', ((), (), (), ()))
    object.__setattr__(board, 'called_discard_indices', (frozenset(), frozenset(), frozenset(), frozenset()))
    return board
