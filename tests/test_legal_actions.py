"""Tests for K14 legal_actions and observation APIs."""

from __future__ import annotations

from collections import Counter

import pytest

from kernel import (
    Action,
    ActionKind,
    GamePhase,
    GameState,
    LegalAction,
    apply,
    build_deck,
    initial_game_state,
    initial_table_snapshot,
    legal_actions,
    observation,
    shuffle_deck,
)
from kernel.api.observation import RiverEntry


def _wall136(*, seed: int = 0) -> tuple:
    """Generate a shuffled wall of 136 tiles."""
    return tuple(shuffle_deck(build_deck(), seed=seed))


class TestLegalActions:
    """测试 legal_actions API。"""

    def test_legal_actions_invalid_seat(self) -> None:
        """测试非法座位号。"""
        g = initial_game_state()
        with pytest.raises(ValueError, match="0..3"):
            legal_actions(g, 4)
        with pytest.raises(ValueError, match="0..3"):
            legal_actions(g, -1)

    def test_legal_actions_begin_round(self) -> None:
        """测试 BEGIN_ROUND 阶段的合法动作。"""
        g = initial_game_state()
        # PRE_DEAL 阶段不枚举动作（由外部控制）
        actions = legal_actions(g, 0)
        assert actions == ()

    def test_legal_actions_after_deal(self) -> None:
        """测试配牌后的合法动作（亲家 MUST_DISCARD）。"""
        g0 = initial_game_state()
        w = _wall136(seed=10)
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w))

        # 亲家处于 MUST_DISCARD 阶段
        seat = g1.new_state.table.dealer_seat
        actions = legal_actions(g1.new_state, seat)

        # 应该有多个 DISCARD 动作和一个可能的 TSUMO 动作
        assert len(actions) > 0
        assert all(a.kind == ActionKind.DISCARD or a.kind == ActionKind.TSUMO for a in actions)
        assert all(a.seat == seat for a in actions)

    def test_legal_actions_draw(self) -> None:
        """测试 NEED_DRAW 阶段的合法动作。"""
        g0 = initial_game_state()
        w = _wall136(seed=11)
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state

        # 亲家打牌
        tile = next(iter(g1.board.hands[g1.board.current_seat].elements()))
        g2 = apply(g1, Action(ActionKind.DISCARD, seat=g1.board.current_seat, tile=tile)).new_state

        # 清除 CALL_RESPONSE 窗口
        from tests.call_helpers import clear_call_window_state

        g2 = clear_call_window_state(g2)

        # 下家应该 DRAW
        seat = g2.board.current_seat
        actions = legal_actions(g2, seat)

        assert len(actions) == 1
        assert actions[0].kind == ActionKind.DRAW
        assert actions[0].seat == seat

    def test_legal_actions_hand_over(self) -> None:
        """测试 HAND_OVER 阶段的合法动作。"""
        # 简化：HAND_OVER 阶段只能 NOOP
        # 实际测试需要完整的和了流程
        pass


class TestObservation:
    """测试 observation API。"""

    def test_observation_invalid_seat(self) -> None:
        """测试非法座位号。"""
        g = initial_game_state()
        with pytest.raises(ValueError, match="0..3"):
            observation(g, 4)

    def test_observation_invalid_mode(self) -> None:
        """测试非法模式。"""
        g = initial_game_state()
        with pytest.raises(ValueError, match="mode must be"):
            observation(g, 0, mode="invalid")  # type: ignore

    def test_observation_human_mode(self) -> None:
        """测试人类模式观测。"""
        g0 = initial_game_state()
        w = _wall136(seed=20)
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state

        # 人类模式：可见自家手牌
        obs = observation(g1, 0, mode="human")
        assert obs.seat == 0
        assert obs.phase.value == "in_round"
        assert obs.hand is not None
        assert obs.melds == ()  # 开局无副露
        assert len(obs.dora_indicators) == 1
        assert obs.ura_indicators is None  # 人类模式且未立直时不可见里宝
        assert len(obs.scores) == 4
        assert obs.honba == 0
        assert obs.kyoutaku == 0
        assert obs.wall_remaining is None  # 人类模式不可见剩余牌数
        assert obs.dead_wall is None  # 人类模式不可见王牌
        assert obs.hands_by_seat is None  # 人类模式不暴露他家手牌

    def test_observation_debug_mode(self) -> None:
        """测试调试模式观测（全知视角）。"""
        g0 = initial_game_state()
        w = _wall136(seed=21)
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state

        # 调试模式：可见所有信息
        obs = observation(g1, 0, mode="debug")
        assert obs.seat == 0
        assert obs.hand is not None
        assert obs.ura_indicators is not None  # 调试模式可见里宝
        assert obs.wall_remaining is not None  # 调试模式可见剩余牌数
        assert obs.dead_wall is not None  # 调试模式可见王牌
        assert obs.hands_by_seat is not None
        assert len(obs.hands_by_seat) == 4
        for s in range(4):
            assert obs.hands_by_seat[s] == Counter(g1.board.hands[s].elements())
        assert obs.hand == obs.hands_by_seat[0]

    def test_observation_river(self) -> None:
        """测试河的观测。"""
        g0 = initial_game_state()
        w = _wall136(seed=22)
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state

        # 亲家打牌
        tile = next(iter(g1.board.hands[g1.board.current_seat].elements()))
        g2 = apply(g1, Action(ActionKind.DISCARD, seat=g1.board.current_seat, tile=tile)).new_state

        obs = observation(g2, 0, mode="human")
        assert len(obs.river) == 1
        assert obs.river[0].tile == tile
        assert obs.river[0].seat == g1.board.current_seat
        assert obs.last_discard == tile
        assert obs.last_discard_seat == g1.board.current_seat

    def test_observation_riichi_state(self) -> None:
        """测试立直状态观测。"""
        g0 = initial_game_state()
        w = _wall136(seed=23)
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state

        obs = observation(g1, 0, mode="human")
        assert len(obs.riichi_state) == 4
        assert all(not r for r in obs.riichi_state)  # 开局无立直

    def test_observation_phase_hand_over(self) -> None:
        """和了后观测应带 ``phase=HAND_OVER``。"""
        from tests.test_tsumo import _must_discard_chiitoitsu_tsumo_s1

        b = _must_discard_chiitoitsu_tsumo_s1()
        g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
        out = apply(g, Action(ActionKind.TSUMO, seat=1))
        assert out.new_state.phase == GamePhase.HAND_OVER
        obs = observation(out.new_state, 0, mode="human")
        assert obs.phase == GamePhase.HAND_OVER


class TestLegalActionDataclass:
    """测试 LegalAction 数据类。"""

    def test_legal_action_discard(self) -> None:
        """测试 DISCARD 动作。"""
        from kernel.tiles import Suit, Tile

        tile = Tile(Suit.MAN, 1, False)
        action = LegalAction(kind=ActionKind.DISCARD, seat=0, tile=tile)
        assert action.kind == ActionKind.DISCARD
        assert action.seat == 0
        assert action.tile == tile
        assert action.declare_riichi is False

    def test_legal_action_discard_with_riichi(self) -> None:
        """测试立直宣言 DISCARD 动作。"""
        from kernel.tiles import Suit, Tile

        tile = Tile(Suit.MAN, 1, False)
        action = LegalAction(kind=ActionKind.DISCARD, seat=0, tile=tile, declare_riichi=True)
        assert action.declare_riichi is True


class TestRiverEntry:
    """测试 RiverEntry 数据类。"""

    def test_river_entry_basic(self) -> None:
        """测试 RiverEntry 基本属性。"""
        from kernel.tiles import Suit, Tile

        tile = Tile(Suit.MAN, 1, False)
        entry = RiverEntry(tile=tile, seat=0, is_tsumogiri=True, is_riichi=False)
        assert entry.tile == tile
        assert entry.seat == 0
        assert entry.is_tsumogiri is True
        assert entry.is_riichi is False
