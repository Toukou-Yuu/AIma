"""``legal_actions`` 对吃碰杠的枚举与 wire 匹配。"""

from __future__ import annotations

from collections import Counter

from kernel.api.legal_actions import legal_actions
from kernel.deal.model import BoardState
from kernel.engine.actions import ActionKind
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState
from kernel.hand.melds import MeldKind
from kernel.play.model import CallResolution, RiverEntry, TurnPhase
from kernel.table import initial_table_snapshot
from kernel.tiles.model import Suit, Tile
from llm.observation_format import action_to_natural_text
from llm.validate import find_matching_legal_action
from llm.wire import legal_action_to_wire
from tests.test_kan import (
    _board,
    _board_call_response_daiminkan_ready,
    _board_with_pon_for_shankan,
    _find_dealer_quad_seed,
)


def _chi_call_response_board() -> tuple[BoardState, Tile]:
    """构造 seat1 只能从 seat0 吃 4m 的 CALL_RESPONSE 场景。"""
    t3 = Tile(Suit.MAN, 3, False)
    t4 = Tile(Suit.MAN, 4, False)
    t5 = Tile(Suit.MAN, 5, False)
    b0 = None
    for seed in range(300):
        b_try = _board(seed=seed, dealer=0)
        merged = Counter()
        for h in b_try.hands:
            merged.update(h)
        if merged[t3] >= 1 and merged[t4] >= 1 and merged[t5] >= 1:
            b0 = b_try
            break
    assert b0 is not None
    merged = Counter()
    for h in b0.hands:
        merged.update(h)
    merged[t3] -= 1
    merged[t4] -= 1
    merged[t5] -= 1
    h1 = Counter({t3: 1, t5: 1})
    rest = merged.copy()
    for _ in range(11):
        x = next(iter(rest.elements()))
        h1[x] += 1
        rest[x] -= 1
    h0 = Counter()
    h2 = Counter()
    h3 = Counter()
    for target in (h0, h2, h3):
        for _ in range(13):
            x = next(iter(rest.elements()))
            target[x] += 1
            rest[x] -= 1
    assert sum(rest.values()) == 0
    hands = (h0, h1, h2, h3)
    river = (RiverEntry(seat=0, tile=t4, tsumogiri=False),)
    cs = CallResolution(
        discard_seat=0,
        claimed_tile=t4,
        river_index=0,
        stage="chi",
        ron_remaining=frozenset(),
        ron_claimants=frozenset(),
        pon_kan_order=(1, 2, 3),
        pon_kan_idx=3,
        finished=False,
    )
    return (
        BoardState(
            hands=hands,
            live_wall=b0.live_wall,
            live_draw_index=b0.live_draw_index,
            dead_wall=b0.dead_wall,
            revealed_indicators=b0.revealed_indicators,
        current_seat=1,
            turn_phase=TurnPhase.CALL_RESPONSE,
            river=river,
            melds=((), (), (), ()),
            last_draw_tile=None,
            last_draw_was_rinshan=False,
            rinshan_draw_index=0,
            call_state=cs,
            all_discards_per_seat=((t4,), (), (), ()),
        ),
        t4,
    )


def test_call_response_lists_daiminkan_open_meld() -> None:
    b, t = _board_call_response_daiminkan_ready()
    g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
    acts = legal_actions(g, 1)
    open_melds = [a for a in acts if a.kind == ActionKind.OPEN_MELD]
    assert open_melds, "应至少有一条大明杠候选"
    kinds = {a.meld.kind for a in open_melds if a.meld}
    assert MeldKind.DAIMINKAN in kinds
    assert all(a.meld and a.meld.called_tile == t for a in open_melds)


def test_must_discard_lists_ankan_when_four_in_hand() -> None:
    b0, quad = _find_dealer_quad_seed()
    d = b0.current_seat
    g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b0)
    acts = legal_actions(g, d)
    ankan = [a for a in acts if a.kind == ActionKind.ANKAN]
    assert ankan, "门内四张同种时应枚举暗杠"
    assert any(a.meld and a.meld.kind == MeldKind.ANKAN for a in ankan)


def test_must_discard_lists_shankuminkan_when_pon_plus_tile() -> None:
    b, t = _board_with_pon_for_shankan()
    d = b.current_seat
    g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
    acts = legal_actions(g, d)
    sk = [a for a in acts if a.kind == ActionKind.SHANKUMINKAN]
    assert sk, "明刻加手牌一张时应枚举加杠"
    assert any(a.meld and a.meld.kind == MeldKind.SHANKUMINKAN for a in sk)


def test_wire_roundtrip_open_meld() -> None:
    b, t = _board_call_response_daiminkan_ready()
    g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
    acts = legal_actions(g, 1)
    dm = next(
        a
        for a in acts
        if a.kind == ActionKind.OPEN_MELD and a.meld and a.meld.kind == MeldKind.DAIMINKAN
    )
    w = legal_action_to_wire(dm)
    assert find_matching_legal_action(acts, w) == dm


def test_natural_text_roundtrip_open_meld() -> None:
    b, _t = _board_call_response_daiminkan_ready()
    g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
    acts = legal_actions(g, 1)
    dm = next(
        a
        for a in acts
        if a.kind == ActionKind.OPEN_MELD and a.meld and a.meld.kind == MeldKind.DAIMINKAN
    )
    text = action_to_natural_text(dm, dm.seat)
    assert text.startswith("大明杠")
    assert find_matching_legal_action(acts, {"action": text, "why": "测试"}) == dm
    simplified = text.split("(")[0]
    assert find_matching_legal_action(acts, {"action": simplified, "why": "测试"}) == dm


def test_chi_stage_lists_chi_open_meld() -> None:
    """下家吃：舍 4m，下家手中有 3m、5m 与鸣入组成顺子。"""
    b, _t4 = _chi_call_response_board()
    g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
    acts = legal_actions(g, 1)
    chi_acts = [
        a for a in acts if a.kind == ActionKind.OPEN_MELD and a.meld and a.meld.kind == MeldKind.CHI
    ]
    assert chi_acts, "应有一条吃 345m 的 OPEN_MELD"
    text = action_to_natural_text(chi_acts[0], chi_acts[0].seat)
    assert text.startswith("吃")
    assert "来自家0" in text


def test_chi_stage_only_shimocha_gets_chi_actions() -> None:
    """只有切牌者下家能吃；其余两家即使在 CALL_RESPONSE 也不能吃。"""
    b, _t4 = _chi_call_response_board()
    g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)

    acts_south = legal_actions(g, 1)
    acts_west = legal_actions(g, 2)
    acts_north = legal_actions(g, 3)

    assert any(
        a.kind == ActionKind.OPEN_MELD and a.meld and a.meld.kind == MeldKind.CHI
        for a in acts_south
    )
    assert not any(
        a.kind == ActionKind.OPEN_MELD and a.meld and a.meld.kind == MeldKind.CHI
        for a in acts_west
    )
    assert not any(
        a.kind == ActionKind.OPEN_MELD and a.meld and a.meld.kind == MeldKind.CHI
        for a in acts_north
    )


def test_natural_text_roundtrip_shankuminkan() -> None:
    b, _t = _board_with_pon_for_shankan()
    d = b.current_seat
    g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
    acts = legal_actions(g, d)
    sk = next(a for a in acts if a.kind == ActionKind.SHANKUMINKAN)
    text = action_to_natural_text(sk, d)
    assert text.startswith("加杠")
    assert find_matching_legal_action(acts, {"action": text, "why": "测试"}) == sk


def test_riichi_seat_no_open_meld_in_call_response() -> None:
    b, _t = _board_call_response_daiminkan_ready()
    riichi = (False, True, False, False)
    b2 = BoardState(
        hands=b.hands,
        live_wall=b.live_wall,
        live_draw_index=b.live_draw_index,
        dead_wall=b.dead_wall,
        revealed_indicators=b.revealed_indicators,
        current_seat=b.current_seat,
        turn_phase=b.turn_phase,
        river=b.river,
        melds=b.melds,
        last_draw_tile=b.last_draw_tile,
        last_draw_was_rinshan=b.last_draw_was_rinshan,
        rinshan_draw_index=b.rinshan_draw_index,
        call_state=b.call_state,
        riichi=riichi,
        all_discards_per_seat=b.all_discards_per_seat,
        called_discard_indices=b.called_discard_indices,
    )
    g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b2)
    acts = legal_actions(g, 1)
    assert not any(a.kind == ActionKind.OPEN_MELD for a in acts)
