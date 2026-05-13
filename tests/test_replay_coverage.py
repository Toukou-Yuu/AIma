"""kernel.replay 覆盖缺口测试。"""

from __future__ import annotations

from kernel.engine.actions import Action, ActionKind
from kernel.engine.apply import ApplyOutcome
from kernel.engine.phase import GamePhase
from kernel.engine.state import initial_game_state
from kernel.event_log import (
    CallEvent,
    DiscardTileEvent,
    DrawTileEvent,
    EventLog,
    FlowEvent,
    HandOverEvent,
    MatchEndEvent,
    RonEvent,
    RoundBeginEvent,
    TsumoEvent,
    WinSettlementLine,
)
from kernel.flow.model import FlowKind
from kernel.hand.melds import Meld, MeldKind
from kernel.replay import (
    ReplayError,
    _action_from_event,
    extract_action_trace,
    replay_from_actions,
    replay_from_event_log,
    verify_event_log,
)
from kernel.tiles.model import Suit, Tile

MAN1 = Tile(Suit.MAN, 1)
MAN2 = Tile(Suit.MAN, 2)
MAN3 = Tile(Suit.MAN, 3)


# --- _action_from_event ---


class TestActionFromEvent:
    """_action_from_event 对各事件类型的分支覆盖。"""

    def test_round_begin_returns_none(self) -> None:
        """RoundBeginEvent：系统事件，返回 None。"""
        state = initial_game_state()
        event = RoundBeginEvent(
            seat=None, sequence=0, dealer_seat=0, dora_indicator=MAN1, seeds=(0, 13, 26, 39),
        )
        assert _action_from_event(event, state) is None

    def test_flow_returns_none(self) -> None:
        """FlowEvent：系统事件，返回 None。"""
        state = initial_game_state()
        event = FlowEvent(
            seat=None, sequence=1, flow_kind=FlowKind.EXHAUSTED, tenpai_seats=frozenset(),
        )
        assert _action_from_event(event, state) is None

    def test_hand_over_returns_none(self) -> None:
        """HandOverEvent：系统事件，返回 None。"""
        state = initial_game_state()
        event = HandOverEvent(seat=None, sequence=2, winners=(1,), payments=(0, 0, 0, 0))
        assert _action_from_event(event, state) is None

    def test_match_end_returns_none(self) -> None:
        """MatchEndEvent：系统事件，返回 None。"""
        state = initial_game_state()
        event = MatchEndEvent(
            seat=None, sequence=3,
            ranking=(0, 1, 2, 3), final_scores=(25000, 25000, 25000, 25000),
        )
        assert _action_from_event(event, state) is None

    def test_draw_tile_returns_none(self) -> None:
        """DrawTileEvent：无法重建动作，返回 None。"""
        state = initial_game_state()
        event = DrawTileEvent(seat=0, sequence=4, tile=MAN1, is_rinshan=False, wall_remaining=68)
        assert _action_from_event(event, state) is None

    def test_discard_tile_returns_none(self) -> None:
        """DiscardTileEvent：无法重建动作，返回 None。"""
        state = initial_game_state()
        event = DiscardTileEvent(
            seat=0, sequence=5, tile=MAN1, is_tsumogiri=False, declare_riichi=False,
        )
        assert _action_from_event(event, state) is None

    def test_call_returns_none(self) -> None:
        """CallEvent：无法重建动作，返回 None。"""
        state = initial_game_state()
        meld = Meld(kind=MeldKind.PON, tiles=(MAN1, MAN1, MAN1), called_tile=MAN1)
        event = CallEvent(seat=1, sequence=6, meld=meld, call_kind="pon")
        assert _action_from_event(event, state) is None

    def test_ron_returns_none(self) -> None:
        """RonEvent：无法重建动作，返回 None。"""
        state = initial_game_state()
        event = RonEvent(seat=1, sequence=7, win_tile=MAN1, discard_seat=0)
        assert _action_from_event(event, state) is None

    def test_tsumo_returns_none(self) -> None:
        """TsumoEvent：无法重建动作，返回 None。"""
        state = initial_game_state()
        event = TsumoEvent(seat=0, sequence=8, win_tile=MAN1, is_rinshan=False)
        assert _action_from_event(event, state) is None


# --- replay_from_actions ---


class TestReplayFromActions:
    """replay_from_actions 正常回放与 ReplayError。"""

    def test_begin_round_produces_in_round_state(self) -> None:
        """BEGIN_ROUND 后状态应为 IN_ROUND。"""
        from kernel import build_deck, shuffle_deck

        wall = tuple(shuffle_deck(build_deck(), seed=42))
        state, outcomes = replay_from_actions(
            [Action(ActionKind.BEGIN_ROUND, wall=wall)],
        )
        assert state.phase == GamePhase.IN_ROUND
        assert state.board is not None
        assert len(outcomes) == 1
        assert len(outcomes[0].events) >= 1
        assert isinstance(outcomes[0].events[0], RoundBeginEvent)

    def test_replay_error_on_invalid_action(self) -> None:
        """无效动作序列应抛出 ReplayError。"""
        try:
            replay_from_actions([Action(ActionKind.DISCARD, seat=0, tile=MAN1)])
        except ReplayError as e:
            assert "Action 0 failed" in str(e)
        else:
            raise AssertionError("预期 ReplayError")

    def test_empty_actions_returns_initial_state(self) -> None:
        """空动作列表应返回初始状态。"""
        state, outcomes = replay_from_actions([])
        assert state.phase == GamePhase.PRE_DEAL
        assert outcomes == []


# --- replay_from_event_log ---


class TestReplayFromEventLog:
    """replay_from_event_log 匹配与不匹配事件。"""

    def test_matching_event_log(self) -> None:
        """事件日志与回放结果一致时应成功。"""
        from kernel import build_deck, shuffle_deck

        wall = tuple(shuffle_deck(build_deck(), seed=42))
        actions = [Action(ActionKind.BEGIN_ROUND, wall=wall)]

        # 先回放获取实际事件
        _, outcomes_ref = replay_from_actions(actions)
        all_events = []
        for outcome in outcomes_ref:
            all_events.extend(outcome.events)
        log = EventLog(events=tuple(all_events), seed=42)

        # 正式调用
        state, outcomes = replay_from_event_log(log, actions)
        assert state.phase == GamePhase.IN_ROUND
        assert len(outcomes) == 1

    def test_mismatched_event_count_raises(self) -> None:
        """事件数不匹配应抛出 ReplayError。"""
        from kernel import build_deck, shuffle_deck

        wall = tuple(shuffle_deck(build_deck(), seed=42))
        actions = [Action(ActionKind.BEGIN_ROUND, wall=wall)]

        # 构造事件数不匹配的日志（空日志）
        log = EventLog(events=(), seed=42)
        try:
            replay_from_event_log(log, actions)
        except ReplayError as e:
            assert "Event count mismatch" in str(e)
        else:
            raise AssertionError("预期 ReplayError")

    def test_mismatched_event_type_raises(self) -> None:
        """事件类型不匹配应抛出 ReplayError。"""
        from kernel import build_deck, shuffle_deck

        wall = tuple(shuffle_deck(build_deck(), seed=42))
        actions = [Action(ActionKind.BEGIN_ROUND, wall=wall)]

        # 先回放获取实际事件
        _, outcomes_ref = replay_from_actions(actions)
        all_events = []
        for outcome in outcomes_ref:
            all_events.extend(outcome.events)

        # 替换第一个事件类型为 FlowEvent
        wrong_event = FlowEvent(
            seat=all_events[0].seat,
            sequence=all_events[0].sequence,
            flow_kind=FlowKind.EXHAUSTED,
            tenpai_seats=frozenset(),
        )
        log = EventLog(events=(wrong_event,) + tuple(all_events[1:]), seed=42)
        try:
            replay_from_event_log(log, actions)
        except ReplayError as e:
            assert "type mismatch" in str(e)
        else:
            raise AssertionError("预期 ReplayError")

    def test_mismatched_event_sequence_raises(self) -> None:
        """事件序列号不匹配应抛出 ReplayError。"""
        from kernel import build_deck, shuffle_deck

        wall = tuple(shuffle_deck(build_deck(), seed=42))
        actions = [Action(ActionKind.BEGIN_ROUND, wall=wall)]

        # 先回放获取实际事件
        _, outcomes_ref = replay_from_actions(actions)
        all_events = []
        for outcome in outcomes_ref:
            all_events.extend(outcome.events)

        # 构造同类型但序列号不同的事件
        orig = all_events[0]
        assert isinstance(orig, RoundBeginEvent)
        wrong_seq_event = RoundBeginEvent(
            seat=orig.seat,
            sequence=999,  # 错误的序列号
            dealer_seat=orig.dealer_seat,
            dora_indicator=orig.dora_indicator,
            seeds=orig.seeds,
        )
        log = EventLog(events=(wrong_seq_event,) + tuple(all_events[1:]), seed=42)
        try:
            replay_from_event_log(log, actions)
        except ReplayError as e:
            assert "sequence mismatch" in str(e)
        else:
            raise AssertionError("预期 ReplayError")


# --- verify_event_log ---


class TestVerifyEventLog:
    """verify_event_log 边界与一致性检查。"""

    def test_empty_events_returns_false(self) -> None:
        """空事件列表应返回 False。"""
        log = EventLog(events=())
        assert verify_event_log(log) is False

    def test_non_continuous_sequence_returns_false(self) -> None:
        """序列号不连续应返回 False。"""
        log = EventLog(events=(
            RoundBeginEvent(seat=None, sequence=0, dealer_seat=0, dora_indicator=MAN1, seeds=()),
            DrawTileEvent(seat=0, sequence=2, tile=MAN1, is_rinshan=False, wall_remaining=68),
        ))
        assert verify_event_log(log) is False

    def test_first_not_round_begin_returns_false(self) -> None:
        """第一个事件不是 RoundBeginEvent 应返回 False。"""
        log = EventLog(events=(
            FlowEvent(seat=None, sequence=0, flow_kind=FlowKind.EXHAUSTED, tenpai_seats=frozenset()),
        ))
        assert verify_event_log(log) is False

    def test_valid_log_returns_true(self) -> None:
        """合法日志应返回 True。"""
        log = EventLog(events=(
            RoundBeginEvent(seat=None, sequence=0, dealer_seat=0, dora_indicator=MAN1, seeds=()),
            DrawTileEvent(seat=0, sequence=1, tile=MAN2, is_rinshan=False, wall_remaining=68),
            DiscardTileEvent(seat=0, sequence=2, tile=MAN2, is_tsumogiri=True, declare_riichi=False),
        ))
        assert verify_event_log(log) is True


# --- extract_action_trace ---


class TestExtractActionTrace:
    """extract_action_trace 各事件类型分支覆盖。"""

    def test_round_begin_event_trace(self) -> None:
        """RoundBeginEvent 应含 dealer_seat 和 dora_indicator。"""
        event = RoundBeginEvent(
            seat=None, sequence=0, dealer_seat=0, dora_indicator=MAN1, seeds=(0, 13, 26, 39),
        )
        outcome = ApplyOutcome(new_state=initial_game_state(), events=(event,))
        trace = extract_action_trace(outcome)
        assert len(trace) == 1
        assert trace[0]["type"] == "RoundBeginEvent"
        assert trace[0]["dealer_seat"] == 0
        assert trace[0]["dora_indicator"] == str(MAN1)

    def test_draw_tile_event_trace(self) -> None:
        """DrawTileEvent 应含 tile 字段。"""
        event = DrawTileEvent(seat=0, sequence=1, tile=MAN2, is_rinshan=False, wall_remaining=68)
        outcome = ApplyOutcome(new_state=initial_game_state(), events=(event,))
        trace = extract_action_trace(outcome)
        assert trace[0]["tile"] == str(MAN2)

    def test_discard_tile_event_trace(self) -> None:
        """DiscardTileEvent 应含 tile 字段。"""
        event = DiscardTileEvent(
            seat=0, sequence=2, tile=MAN3, is_tsumogiri=False, declare_riichi=True,
        )
        outcome = ApplyOutcome(new_state=initial_game_state(), events=(event,))
        trace = extract_action_trace(outcome)
        assert trace[0]["tile"] == str(MAN3)

    def test_ron_event_trace(self) -> None:
        """RonEvent 应含 tile 字段（win_tile 无 tile 属性时为 None）。"""
        event = RonEvent(seat=1, sequence=3, win_tile=MAN1, discard_seat=0)
        outcome = ApplyOutcome(new_state=initial_game_state(), events=(event,))
        trace = extract_action_trace(outcome)
        # RonEvent has win_tile, not tile → hasattr(event, "tile") is False
        assert trace[0]["tile"] is None

    def test_tsumo_event_trace(self) -> None:
        """TsumoEvent 应含 tile 字段（win_tile 无 tile 属性时为 None）。"""
        event = TsumoEvent(seat=0, sequence=4, win_tile=MAN2, is_rinshan=False)
        outcome = ApplyOutcome(new_state=initial_game_state(), events=(event,))
        trace = extract_action_trace(outcome)
        assert trace[0]["tile"] is None

    def test_call_event_trace(self) -> None:
        """CallEvent 应含 call_kind 字段。"""
        meld = Meld(kind=MeldKind.PON, tiles=(MAN1, MAN1, MAN1), called_tile=MAN1)
        event = CallEvent(seat=1, sequence=5, meld=meld, call_kind="pon")
        outcome = ApplyOutcome(new_state=initial_game_state(), events=(event,))
        trace = extract_action_trace(outcome)
        assert trace[0]["call_kind"] == "pon"

    def test_flow_event_trace(self) -> None:
        """FlowEvent 应含 flow_kind 和 tenpai_seats。"""
        event = FlowEvent(
            seat=None, sequence=6,
            flow_kind=FlowKind.EXHAUSTED, tenpai_seats=frozenset({0, 2}),
        )
        outcome = ApplyOutcome(new_state=initial_game_state(), events=(event,))
        trace = extract_action_trace(outcome)
        assert trace[0]["flow_kind"] == str(FlowKind.EXHAUSTED)
        assert trace[0]["tenpai_seats"] == [0, 2]

    def test_hand_over_event_trace(self) -> None:
        """HandOverEvent 应含 winners、payments 和 win_lines。"""
        win_line = WinSettlementLine(
            seat=1, win_kind="ron", han=2, fu=30,
            hand_pattern="一般形", yakus=("立直", "断幺九"),
            discard_seat=0, payment_from_discarder=2000,
            tsumo_deltas=None, kyoutaku_share=0, points=2000,
        )
        event = HandOverEvent(
            seat=None, sequence=7,
            winners=(1,), payments=(-2000, 2000, 0, 0),
            win_lines=(win_line,),
        )
        outcome = ApplyOutcome(new_state=initial_game_state(), events=(event,))
        trace = extract_action_trace(outcome)
        assert trace[0]["winners"] == (1,)
        assert trace[0]["payments"] == (-2000, 2000, 0, 0)
        assert len(trace[0]["win_lines"]) == 1
        assert trace[0]["win_lines"][0]["seat"] == 1
        assert trace[0]["win_lines"][0]["han"] == 2
        assert trace[0]["win_lines"][0]["fu"] == 30

    def test_match_end_event_trace(self) -> None:
        """MatchEndEvent 应含 ranking 和 final_scores。"""
        event = MatchEndEvent(
            seat=None, sequence=8,
            ranking=(0, 1, 2, 3), final_scores=(30000, 25000, 25000, 20000),
        )
        outcome = ApplyOutcome(new_state=initial_game_state(), events=(event,))
        trace = extract_action_trace(outcome)
        assert trace[0]["ranking"] == [0, 1, 2, 3]
        assert trace[0]["final_scores"] == [30000, 25000, 25000, 20000]

    def test_multiple_events_in_outcome(self) -> None:
        """一个 outcome 含多个事件时应全部提取。"""
        events = (
            RoundBeginEvent(
                seat=None, sequence=0, dealer_seat=0, dora_indicator=MAN1, seeds=(),
            ),
            DrawTileEvent(seat=0, sequence=1, tile=MAN2, is_rinshan=False, wall_remaining=68),
            DiscardTileEvent(
                seat=0, sequence=2, tile=MAN2, is_tsumogiri=True, declare_riichi=False,
            ),
        )
        outcome = ApplyOutcome(new_state=initial_game_state(), events=events)
        trace = extract_action_trace(outcome)
        assert len(trace) == 3
        assert trace[0]["type"] == "RoundBeginEvent"
        assert trace[1]["type"] == "DrawTileEvent"
        assert trace[2]["type"] == "DiscardTileEvent"
