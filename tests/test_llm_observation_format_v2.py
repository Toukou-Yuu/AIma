"""llm.observation_format 覆盖缺口补充测试。

覆盖：build_compressed_observation (prev_obs 路径)、_calculate_changes、
build_delta_observation (new_dora_indicator / others_actions 等分支)。"""

from __future__ import annotations

from collections import Counter

from kernel.api.observation import Observation, RiverEntry
from kernel.engine.phase import GamePhase
from kernel.hand.melds import Meld, MeldKind
from kernel.tiles.model import Suit, Tile
from llm.observation_format import (
    _calculate_changes,
    build_compressed_observation,
    build_delta_observation,
)

MAN1 = Tile(Suit.MAN, 1)
MAN2 = Tile(Suit.MAN, 2)
MAN3 = Tile(Suit.MAN, 3)
MAN5 = Tile(Suit.MAN, 5)
PIN5 = Tile(Suit.PIN, 5)
SOU5 = Tile(Suit.SOU, 5)
TON = Tile(Suit.HONOR, 1)


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


# --- build_compressed_observation (prev_obs 路径) ---

class TestBuildCompressedObservationPrevObs:
    def test_with_prev_obs_generates_changes(self) -> None:
        prev = _obs(hand=Counter({MAN1: 2, MAN2: 1, MAN3: 1, PIN5: 1}))
        curr = _obs(hand=Counter({MAN1: 2, MAN2: 1, MAN3: 1, SOU5: 1}))
        result = build_compressed_observation(curr, prev_obs=prev)
        assert "changes" in result
        assert "drew" in result["changes"]
        assert "5s" in result["changes"]["drew"]
        assert "discarded" in result["changes"]
        assert "5p" in result["changes"]["discarded"]

    def test_with_prev_obs_no_changes(self) -> None:
        obs = _obs()
        result = build_compressed_observation(obs, prev_obs=obs)
        assert "changes" not in result

    def test_with_prev_obs_hand_none_no_changes(self) -> None:
        prev = _obs(hand=None)
        curr = _obs(hand=None)
        result = build_compressed_observation(curr, prev_obs=prev)
        assert "changes" not in result

    def test_with_prev_obs_river_expansion(self) -> None:
        prev = _obs(river=(
            RiverEntry(tile=MAN1, seat=0, is_tsumogiri=False, is_riichi=False),
        ))
        curr = _obs(river=(
            RiverEntry(tile=MAN1, seat=0, is_tsumogiri=False, is_riichi=False),
            RiverEntry(tile=PIN5, seat=1, is_tsumogiri=True, is_riichi=False),
        ))
        result = build_compressed_observation(curr, prev_obs=prev)
        assert "changes" in result
        assert "new_river" in result["changes"]
        assert len(result["changes"]["new_river"]) == 1


# --- _calculate_changes ---

class TestCalculateChanges:
    def test_drew_and_discarded(self) -> None:
        prev = _obs(hand=Counter({MAN1: 2, PIN5: 1}))
        curr = _obs(hand=Counter({MAN1: 1, SOU5: 1}))
        changes = _calculate_changes(prev, curr)
        assert changes is not None
        assert "5s" in changes["drew"]
        assert "1m" in changes["discarded"]

    def test_no_hand_changes(self) -> None:
        obs = _obs()
        changes = _calculate_changes(obs, obs)
        assert changes is None

    def test_new_river_entries(self) -> None:
        prev = _obs(river=(
            RiverEntry(tile=MAN1, seat=0, is_tsumogiri=False, is_riichi=False),
        ))
        curr = _obs(river=(
            RiverEntry(tile=MAN1, seat=0, is_tsumogiri=False, is_riichi=False),
            RiverEntry(tile=SOU5, seat=2, is_tsumogiri=False, is_riichi=True),
        ))
        changes = _calculate_changes(prev, curr)
        assert changes is not None
        assert len(changes["new_river"]) == 1
        assert changes["new_river"][0]["tile"] == "5s"

    def test_hand_none_no_hand_changes(self) -> None:
        prev = _obs(hand=None, river=())
        curr = _obs(hand=None, river=())
        changes = _calculate_changes(prev, curr)
        assert changes is None

    def test_empty_river_no_new_river(self) -> None:
        prev = _obs(river=())
        curr = _obs(river=())
        changes = _calculate_changes(prev, curr)
        assert changes is None


# --- build_delta_observation (new_dora_indicator) ---

class TestBuildDeltaObservationDora:
    def test_new_dora_indicator(self) -> None:
        prev = _obs(dora_indicators=(MAN5,))
        curr = _obs(dora_indicators=(MAN5, PIN5))
        delta = build_delta_observation(curr, prev)
        assert "new_dora_indicator" in delta
        assert delta["new_dora_indicator"] == "5p"
        assert "new_dora_tile" in delta

    def test_no_new_dora(self) -> None:
        prev = _obs(dora_indicators=(MAN5,))
        curr = _obs(dora_indicators=(MAN5,))
        delta = build_delta_observation(curr, prev)
        assert "new_dora_indicator" not in delta


# --- build_delta_observation (others_actions) ---

class TestBuildDeltaObservationOthersActions:
    def test_others_actions_from_new_river(self) -> None:
        prev = _obs(river=(
            RiverEntry(tile=MAN1, seat=0, is_tsumogiri=False, is_riichi=False),
        ))
        curr = _obs(river=(
            RiverEntry(tile=MAN1, seat=0, is_tsumogiri=False, is_riichi=False),
            RiverEntry(tile=SOU5, seat=1, is_tsumogiri=True, is_riichi=False),
        ))
        delta = build_delta_observation(curr, prev)
        assert "others_actions" in delta
        assert len(delta["others_actions"]) == 1
        assert "家1" in delta["others_actions"][0]

    def test_others_actions_filters_own(self) -> None:
        prev = _obs(river=(
            RiverEntry(tile=MAN1, seat=0, is_tsumogiri=False, is_riichi=False),
        ))
        curr = _obs(river=(
            RiverEntry(tile=MAN1, seat=0, is_tsumogiri=False, is_riichi=False),
            RiverEntry(tile=PIN5, seat=0, is_tsumogiri=False, is_riichi=False),
        ))
        delta = build_delta_observation(curr, prev)
        # seat=0 is viewer, should be filtered
        assert "others_actions" not in delta or delta.get("others_actions") == []

    def test_no_new_river_no_others_actions(self) -> None:
        prev = _obs(river=())
        curr = _obs(river=())
        delta = build_delta_observation(curr, prev)
        assert "others_actions" not in delta


# --- build_delta_observation (my_draw / my_discard) ---

class TestBuildDeltaObservationHandChanges:
    def test_my_draw_and_discard(self) -> None:
        prev_hand = Counter({MAN1: 2, MAN2: 1, MAN3: 1, PIN5: 1})
        curr = _obs(hand=Counter({MAN1: 2, MAN2: 1, MAN3: 1, SOU5: 1}))
        prev = _obs(hand=prev_hand)
        delta = build_delta_observation(curr, prev, prev_hand=prev_hand)
        assert "my_draw" in delta
        assert delta["my_draw"] == "5s"
        assert "my_discard" in delta
        assert delta["my_discard"] == "5p"

    def test_no_prev_hand_no_my_changes(self) -> None:
        curr = _obs()
        prev = _obs()
        delta = build_delta_observation(curr, prev, prev_hand=None)
        assert "my_draw" not in delta
        assert "my_discard" not in delta


# --- build_delta_observation (new_riichi, score_changes, current_scores) ---

class TestBuildDeltaObservationMisc:
    def test_new_riichi_multiple(self) -> None:
        prev = _obs(riichi_state=(False, False, False, False))
        curr = _obs(riichi_state=(True, False, True, False))
        delta = build_delta_observation(curr, prev)
        assert delta.get("new_riichi") == [0, 2]

    def test_score_changes_present(self) -> None:
        prev = _obs(scores=(25000, 25000, 25000, 25000))
        curr = _obs(scores=(30000, 23000, 25000, 25000))
        delta = build_delta_observation(curr, prev)
        assert delta["score_changes"][0] == 5000
        assert delta["score_changes"][1] == -2000
        assert 2 not in delta["score_changes"]

    def test_current_scores_always_present(self) -> None:
        prev = _obs(scores=(25000, 25000, 25000, 25000))
        curr = _obs(scores=(25000, 25000, 25000, 25000))
        delta = build_delta_observation(curr, prev)
        assert "current_scores" in delta
        assert delta["current_scores"] == [25000, 25000, 25000, 25000]

    def test_current_melds_present(self) -> None:
        meld = Meld(MeldKind.CHI, (MAN1, MAN2, MAN3), MAN2, from_seat=1)
        curr = _obs(melds=(meld,))
        prev = _obs()
        delta = build_delta_observation(curr, prev)
        assert "current_melds" in delta
        assert len(delta["current_melds"]) == 1
        assert delta["current_melds"][0]["kind"] == "chi"

    def test_wind_in_delta(self) -> None:
        curr = _obs(seat=1, dealer_seat=0)
        prev = _obs(seat=1, dealer_seat=0)
        delta = build_delta_observation(curr, prev)
        assert delta["wind"] == "南"
