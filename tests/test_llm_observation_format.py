"""llm.observation_format 覆盖缺口测试。"""

from __future__ import annotations

from collections import Counter

from kernel.api.observation import Observation, RiverEntry
from kernel.engine.actions import ActionKind
from kernel.engine.phase import GamePhase
from kernel.hand.melds import Meld, MeldKind
from kernel.tiles.model import Suit, Tile
from llm.observation_format import (
    _calculate_hand_changes,
    _calculate_wind,
    _get_others_river_actions,
    _hand_to_cn,
    _river_entries_to_actions,
    _river_to_cn,
    action_to_natural_text,
    build_delta_observation,
    build_decision_prompt,
    observation_to_prompt_dict,
    tile_to_cn,
)
from kernel.api.legal_actions import LegalAction

MAN1 = Tile(Suit.MAN, 1)
MAN2 = Tile(Suit.MAN, 2)
MAN3 = Tile(Suit.MAN, 3)
MAN5 = Tile(Suit.MAN, 5)
PIN5 = Tile(Suit.PIN, 5)
SOU5 = Tile(Suit.SOU, 5)
TON = Tile(Suit.HONOR, 1)
NAN = Tile(Suit.HONOR, 2)
HAKU = Tile(Suit.HONOR, 5)


def _obs(**kwargs) -> Observation:
    defaults = dict(
        seat=0, dealer_seat=0, phase=GamePhase.IN_ROUND,
        hand=Counter({MAN1: 2, MAN2: 1, MAN3: 1, PIN5: 1}),
        melds=(), all_melds=((), (), (), ()),
        river=(), dora_indicators=(MAN5,), ura_indicators=None,
        riichi_state=(False, False, False, False),
        scores=(25000, 25000, 25000, 25000), honba=0, kyoutaku=0,
        turn_seat=0, last_discard=None, last_discard_seat=None,
        wall_remaining=70, dead_wall=None, hands_by_seat=None,
    )
    defaults.update(kwargs)
    return Observation(**defaults)


# --- _hand_to_cn ---

class TestHandToCn:
    def test_none_hand(self) -> None:
        assert _hand_to_cn(None) == "无"

    def test_empty_hand(self) -> None:
        assert _hand_to_cn(Counter()) == "无"

    def test_normal_hand(self) -> None:
        h = Counter({MAN1: 2, PIN5: 1, TON: 1})
        result = _hand_to_cn(h)
        assert "万子" in result
        assert "筒子" in result
        assert "字牌" in result


# --- _river_to_cn ---

class TestRiverToCn:
    def test_empty_river(self) -> None:
        assert _river_to_cn((), 0) == "空"

    def test_river_with_entries(self) -> None:
        river = (
            RiverEntry(tile=MAN1, seat=0, is_tsumogiri=False, is_riichi=False),
            RiverEntry(tile=PIN5, seat=1, is_tsumogiri=True, is_riichi=False),
            RiverEntry(tile=SOU5, seat=2, is_tsumogiri=False, is_riichi=True),
        )
        result = _river_to_cn(river, 0)
        assert "我" in result
        assert "家1" in result
        assert "摸切" in result
        assert "立直" in result


# --- _calculate_wind ---

class TestCalculateWind:
    def test_east(self) -> None:
        assert _calculate_wind(0, 0) == "东"

    def test_south(self) -> None:
        assert _calculate_wind(1, 0) == "南"

    def test_west(self) -> None:
        assert _calculate_wind(2, 0) == "西"

    def test_north(self) -> None:
        assert _calculate_wind(3, 0) == "北"

    def test_wrap_around(self) -> None:
        assert _calculate_wind(0, 1) == "北"


# --- action_to_natural_text ---

class TestActionToNaturalText:
    def test_ron(self) -> None:
        la = LegalAction(kind=ActionKind.RON, tile=MAN1, seat=0, meld=None, declare_riichi=False)
        result = action_to_natural_text(la, 0)
        assert "荣和" in result

    def test_tsumo(self) -> None:
        la = LegalAction(kind=ActionKind.TSUMO, tile=None, seat=0, meld=None, declare_riichi=False)
        result = action_to_natural_text(la, 0)
        assert "自摸" in result

    def test_open_meld(self) -> None:
        meld = Meld(MeldKind.CHI, (MAN1, MAN2, MAN3), MAN2)
        la = LegalAction(kind=ActionKind.OPEN_MELD, tile=None, seat=1, meld=meld, declare_riichi=False)
        result = action_to_natural_text(la, 1)
        assert "吃" in result

    def test_ankan(self) -> None:
        meld = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5))
        la = LegalAction(kind=ActionKind.ANKAN, tile=None, seat=0, meld=meld, declare_riichi=False)
        result = action_to_natural_text(la, 0)
        assert "暗杠" in result

    def test_shankuminkan(self) -> None:
        meld = Meld(MeldKind.SHANKUMINKAN, (MAN5, MAN5, MAN5, MAN5))
        la = LegalAction(kind=ActionKind.SHANKUMINKAN, tile=None, seat=0, meld=meld, declare_riichi=False)
        result = action_to_natural_text(la, 0)
        assert "加杠" in result

    def test_discard_with_riichi(self) -> None:
        la = LegalAction(kind=ActionKind.DISCARD, tile=MAN1, seat=0, meld=None, declare_riichi=True)
        result = action_to_natural_text(la, 0)
        assert "立直" in result

    def test_pass_call(self) -> None:
        la = LegalAction(kind=ActionKind.PASS_CALL, tile=None, seat=0, meld=None, declare_riichi=False)
        result = action_to_natural_text(la, 0)
        assert result == "过"


# --- _calculate_hand_changes ---

class TestCalculateHandChanges:
    def test_added_and_removed(self) -> None:
        prev = Counter({MAN1: 2, MAN2: 1})
        curr = Counter({MAN1: 1, MAN2: 1, PIN5: 1})
        changes = _calculate_hand_changes(prev, curr)
        assert "5p" in changes["drew"]
        assert "1m" in changes["discarded"]

    def test_no_changes(self) -> None:
        h = Counter({MAN1: 2, MAN2: 1})
        changes = _calculate_hand_changes(h, h)
        assert changes["drew"] == []
        assert changes["discarded"] == []


# --- _river_entries_to_actions ---

class TestRiverEntriesToActions:
    def test_basic(self) -> None:
        entries = (
            RiverEntry(tile=MAN1, seat=0, is_tsumogiri=False, is_riichi=False),
            RiverEntry(tile=PIN5, seat=1, is_tsumogiri=True, is_riichi=False),
            RiverEntry(tile=SOU5, seat=2, is_tsumogiri=False, is_riichi=True),
        )
        actions = _river_entries_to_actions(entries)
        assert len(actions) == 3
        assert "打1m" in actions[0]
        assert "摸切" in actions[1]
        assert "立直" in actions[2]


# --- _get_others_river_actions ---

class TestGetOthersRiverActions:
    def test_filters_own(self) -> None:
        entries = (
            RiverEntry(tile=MAN1, seat=0, is_tsumogiri=False, is_riichi=False),
            RiverEntry(tile=PIN5, seat=1, is_tsumogiri=False, is_riichi=False),
        )
        actions = _get_others_river_actions(entries, my_seat=0)
        assert len(actions) == 1
        assert "家1" in actions[0]


# --- observation_to_prompt_dict ---

class TestObservationToPromptDict:
    def test_basic(self) -> None:
        obs = _obs()
        d = observation_to_prompt_dict(obs)
        assert d["seat"] == 0
        assert d["wind"] == "东"
        assert d["phase"] == "in_round"
        assert isinstance(d["hand"], dict)
        assert isinstance(d["scores"], list)


# --- build_decision_prompt ---

class TestBuildDecisionPrompt:
    def test_json_format(self) -> None:
        obs = _obs()
        la = LegalAction(kind=ActionKind.DISCARD, tile=MAN1, seat=0, meld=None, declare_riichi=False)
        result = build_decision_prompt(obs, (la,))
        assert "observation" in result
        assert "legal_actions" in result


# --- build_delta_observation ---

class TestBuildDeltaObservation:
    def test_basic(self) -> None:
        prev = _obs(hand=Counter({MAN1: 2, MAN2: 1, MAN3: 1, PIN5: 1}))
        curr = _obs(hand=Counter({MAN1: 2, MAN2: 1, MAN3: 1, SOU5: 1}))
        delta = build_delta_observation(curr, prev, prev_hand=Counter({MAN1: 2, MAN2: 1, MAN3: 1, PIN5: 1}))
        assert delta["frame_type"] == "delta"
        assert "current_hand" in delta

    def test_new_riichi(self) -> None:
        prev = _obs(riichi_state=(False, False, False, False))
        curr = _obs(riichi_state=(True, False, False, False))
        delta = build_delta_observation(curr, prev)
        assert delta.get("new_riichi") == [0]

    def test_score_changes(self) -> None:
        prev = _obs(scores=(25000, 25000, 25000, 25000))
        curr = _obs(scores=(26000, 24000, 25000, 25000))
        delta = build_delta_observation(curr, prev)
        assert delta.get("score_changes", {}).get(0) == 1000
