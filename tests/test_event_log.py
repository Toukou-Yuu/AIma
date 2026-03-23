"""Tests for K13 event log and replay."""

from __future__ import annotations

from kernel import (
    Action,
    ActionKind,
    apply,
    build_deck,
    initial_game_state,
    shuffle_deck,
)
from kernel.event_log import (
    DiscardTileEvent,
    DrawTileEvent,
    EventLog,
    RoundBeginEvent,
)
from kernel.replay import replay_from_actions, verify_event_log


def _wall136(*, seed: int = 0) -> tuple:
    """Generate a shuffled wall of 136 tiles."""
    return tuple(shuffle_deck(build_deck(), seed=seed))


class TestEventLogGeneration:
    """测试事件日志生成。"""

    def test_begin_round_generates_round_begin_event(self) -> None:
        """BEGIN_ROUND 动作应生成 RoundBeginEvent。"""
        g0 = initial_game_state()
        w = _wall136(seed=11)
        out = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w))

        assert len(out.events) == 1
        event = out.events[0]
        assert isinstance(event, RoundBeginEvent)
        assert event.dealer_seat == g0.table.dealer_seat
        assert event.dora_indicator is not None
        assert event.seat is None  # 系统事件
        assert event.sequence == 0

    def test_draw_generates_draw_tile_event(self) -> None:
        """DRAW 动作应生成 DrawTileEvent。"""
        g0 = initial_game_state()
        w = _wall136(seed=13)
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state

        # 开局后亲家处于 MUST_DISCARD 状态，先打牌
        b = g1.board
        assert b is not None
        tile = next(iter(b.hands[b.current_seat].elements()))
        g2 = apply(g1, Action(ActionKind.DISCARD, seat=b.current_seat, tile=tile)).new_state

        # 进入 CALL_RESPONSE，其他家 PASS
        from tests.call_helpers import clear_call_window_state

        g2 = clear_call_window_state(g2)

        # 下家摸牌
        b2 = g2.board
        assert b2 is not None
        current = b2.current_seat

        out = apply(g2, Action(ActionKind.DRAW, seat=current))

        assert len(out.events) == 1
        event = out.events[0]
        assert isinstance(event, DrawTileEvent)
        assert event.seat == current
        assert event.tile is not None
        # 序列号应为 2 (RoundBegin=0, Discard=1, Draw=2)
        assert event.sequence == 2

    def test_discard_generates_discard_tile_event(self) -> None:
        """DISCARD 动作应生成 DiscardTileEvent。"""
        g0 = initial_game_state()
        w = _wall136(seed=14)
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state

        # 亲家打牌
        b = g1.board
        assert b is not None
        hand = b.hands[b.current_seat]
        tile = next(iter(hand.elements()))

        out = apply(g1, Action(ActionKind.DISCARD, seat=b.current_seat, tile=tile))

        assert len(out.events) == 1
        event = out.events[0]
        assert isinstance(event, DiscardTileEvent)
        assert event.seat == b.current_seat
        assert event.tile == tile


class TestReplay:
    """测试回放功能。"""

    def test_replay_begin_round(self) -> None:
        """测试开局的回放。"""
        g0 = initial_game_state()
        w = _wall136(seed=20)

        # 构建动作序列
        actions = [
            Action(ActionKind.BEGIN_ROUND, wall=w),
        ]

        # 执行一次获取期望状态
        g1 = apply(g0, actions[0]).new_state

        # 回放：从头开始执行相同的动作序列
        final_state, outcomes = replay_from_actions(actions, seed=20)

        # 验证最终状态一致
        assert final_state.phase == g1.phase
        assert len(outcomes) == len(actions)
        # 验证事件总数
        total_events = sum(len(o.events) for o in outcomes)
        assert total_events == 1  # RoundBegin only
        assert isinstance(outcomes[0].events[0], RoundBeginEvent)

    def test_replay_event_count_matches(self) -> None:
        """验证回放生成的事件数量与原始一致。"""
        g0 = initial_game_state()
        w = _wall136(seed=21)

        actions = [
            Action(ActionKind.BEGIN_ROUND, wall=w),
        ]
        g1 = apply(g0, actions[0]).new_state

        # 亲家打牌
        tile = next(iter(g1.board.hands[g1.board.current_seat].elements()))
        actions.append(Action(ActionKind.DISCARD, seat=g1.board.current_seat, tile=tile))

        final_state, outcomes = replay_from_actions(actions, seed=21)

        # 验证事件总数
        total_events = sum(len(o.events) for o in outcomes)
        assert total_events == 2  # RoundBegin + Discard

    def test_verify_event_log_valid(self) -> None:
        """验证有效的事件日志。"""
        g0 = initial_game_state()
        w = _wall136(seed=22)
        out = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w))

        log = EventLog(events=out.events, seed=22)
        assert verify_event_log(log) is True

    def test_verify_event_log_empty(self) -> None:
        """验证空日志返回 False。"""
        log = EventLog(events=())
        assert verify_event_log(log) is False

    def test_verify_event_log_wrong_start(self) -> None:
        """验证非 RoundBegin 开头的日志返回 False。"""
        g0 = initial_game_state()
        w = _wall136(seed=23)
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state

        # 制造一个非 RoundBegin 开头的日志
        tile = next(iter(g1.board.hands[g1.board.current_seat].elements()))
        out = apply(g1, Action(ActionKind.DISCARD, seat=g1.board.current_seat, tile=tile))

        log = EventLog(events=out.events, seed=23)
        assert verify_event_log(log) is False  # 以 DiscardTileEvent 开头


class TestEventSequence:
    """测试事件序列号连续性。"""

    def test_event_sequence_continuous(self) -> None:
        """验证事件序列号连续。"""
        g0 = initial_game_state()
        w = _wall136(seed=30)

        # BEGIN_ROUND 生成 RoundBeginEvent (sequence=0)
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w))
        assert g1.events[0].sequence == 0

        # 亲家打牌生成 DiscardTileEvent (sequence=1)
        tile = next(iter(g1.new_state.board.hands[g1.new_state.board.current_seat].elements()))
        g2 = apply(
            g1.new_state,
            Action(ActionKind.DISCARD, seat=g1.new_state.board.current_seat, tile=tile),
        )
        assert g2.events[0].sequence == 1

        # 进入 CALL_RESPONSE，其他家 PASS（简化处理）
        from tests.call_helpers import clear_call_window_state

        g2_cleared = clear_call_window_state(g2.new_state)

        # 下家摸牌生成 DrawTileEvent (sequence=2)
        b = g2_cleared.board
        assert b is not None
        g3 = apply(g2_cleared, Action(ActionKind.DRAW, seat=b.current_seat))
        assert g3.events[0].sequence == 2
