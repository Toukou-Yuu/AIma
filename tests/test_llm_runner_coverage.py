"""llm.runner 覆盖缺口测试。

覆盖：_format_callback_action_label (各种 ActionKind),
_accumulate_simple_stats, RunResult.as_match_log。"""

from __future__ import annotations

from kernel.engine.actions import Action, ActionKind
from kernel.event_log import FlowEvent, HandOverEvent
from kernel.flow.model import FlowKind
from kernel.hand.melds import Meld, MeldKind
from kernel.tiles.model import Suit, Tile
from llm.runner import RunResult, _accumulate_simple_stats, _format_callback_action_label

MAN1 = Tile(Suit.MAN, 1)
MAN2 = Tile(Suit.MAN, 2)
MAN3 = Tile(Suit.MAN, 3)
MAN5 = Tile(Suit.MAN, 5)
TON = Tile(Suit.HONOR, 1)


# --- _format_callback_action_label ---

class TestFormatCallbackActionLabel:
    def test_draw(self) -> None:
        act = Action(kind=ActionKind.DRAW, seat=0)
        result = _format_callback_action_label(act)
        assert "摸牌" in result

    def test_discard(self) -> None:
        act = Action(kind=ActionKind.DISCARD, seat=0, tile=MAN1)
        result = _format_callback_action_label(act)
        assert "打牌" in result
        assert "1m" in result

    def test_discard_riichi(self) -> None:
        act = Action(kind=ActionKind.DISCARD, seat=0, tile=MAN1, declare_riichi=True)
        result = _format_callback_action_label(act)
        assert "立直" in result

    def test_pass_call(self) -> None:
        act = Action(kind=ActionKind.PASS_CALL, seat=0)
        result = _format_callback_action_label(act)
        assert "过牌" in result

    def test_call_pass_drain(self) -> None:
        act = Action(kind=ActionKind.CALL_PASS_DRAIN)
        result = _format_callback_action_label(act)
        assert "连续过牌" in result

    def test_ron(self) -> None:
        act = Action(kind=ActionKind.RON, seat=1)
        result = _format_callback_action_label(act)
        assert "荣和" in result
        assert "家1" in result

    def test_tsumo(self) -> None:
        act = Action(kind=ActionKind.TSUMO, seat=0)
        result = _format_callback_action_label(act)
        assert "自摸" in result

    def test_open_meld_chi(self) -> None:
        meld = Meld(MeldKind.CHI, (MAN1, MAN2, MAN3), MAN2)
        act = Action(kind=ActionKind.OPEN_MELD, seat=1, meld=meld)
        result = _format_callback_action_label(act)
        assert "吃" in result

    def test_open_meld_pon(self) -> None:
        meld = Meld(MeldKind.PON, (TON, TON, TON), TON)
        act = Action(kind=ActionKind.OPEN_MELD, seat=2, meld=meld)
        result = _format_callback_action_label(act)
        assert "碰" in result

    def test_open_meld_daiminkan(self) -> None:
        meld = Meld(MeldKind.DAIMINKAN, (MAN5, MAN5, MAN5, MAN5), MAN5)
        act = Action(kind=ActionKind.OPEN_MELD, seat=3, meld=meld)
        result = _format_callback_action_label(act)
        assert "大明杠" in result

    def test_ankan(self) -> None:
        meld = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5))
        act = Action(kind=ActionKind.ANKAN, seat=0, meld=meld)
        result = _format_callback_action_label(act)
        assert "暗杠" in result

    def test_kakan(self) -> None:
        meld = Meld(MeldKind.KAKAN, (MAN5, MAN5, MAN5, MAN5))
        act = Action(kind=ActionKind.KAKAN, seat=0, meld=meld)
        result = _format_callback_action_label(act)
        assert "加杠" in result

    def test_begin_round(self) -> None:
        act = Action(kind=ActionKind.BEGIN_ROUND)
        result = _format_callback_action_label(act)
        assert "开局" in result

    def test_unknown_kind(self) -> None:
        act = Action(kind=ActionKind.NOOP, seat=0)
        result = _format_callback_action_label(act)
        assert "noop" in result

    def test_no_seat(self) -> None:
        act = Action(kind=ActionKind.DRAW, seat=None)
        result = _format_callback_action_label(act)
        assert "家" not in result
        assert "摸牌" in result

    def test_discard_no_tile(self) -> None:
        act = Action(kind=ActionKind.DISCARD, seat=0, tile=None)
        result = _format_callback_action_label(act)
        assert "?" in result


# --- _accumulate_simple_stats ---

class TestAccumulateSimpleStats:
    def test_hand_over_event(self) -> None:
        win_counts = [0, 0, 0, 0]
        hands_finished = [0]
        ho = HandOverEvent(seat=0, sequence=1, winners=(0, 2), payments=(5000, -3000, 5000, -7000), win_lines=())
        _accumulate_simple_stats((ho,), win_counts, hands_finished)
        assert hands_finished[0] == 1
        assert win_counts[0] == 1
        assert win_counts[2] == 1
        assert win_counts[1] == 0

    def test_flow_event(self) -> None:
        win_counts = [0, 0, 0, 0]
        hands_finished = [0]
        fe = FlowEvent(seat=None, sequence=1, flow_kind=FlowKind.EXHAUSTED, tenpai_seats=frozenset())
        _accumulate_simple_stats((fe,), win_counts, hands_finished)
        assert hands_finished[0] == 1
        assert all(c == 0 for c in win_counts)

    def test_multiple_events(self) -> None:
        win_counts = [0, 0, 0, 0]
        hands_finished = [0]
        ho1 = HandOverEvent(seat=0, sequence=1, winners=(1,), payments=(0, 8000, 0, -8000), win_lines=())
        ho2 = HandOverEvent(seat=0, sequence=2, winners=(0, 3), payments=(4000, 0, 0, 4000), win_lines=())
        _accumulate_simple_stats((ho1, ho2), win_counts, hands_finished)
        assert hands_finished[0] == 2
        assert win_counts[0] == 1
        assert win_counts[1] == 1
        assert win_counts[3] == 1

    def test_no_relevant_events(self) -> None:
        win_counts = [0, 0, 0, 0]
        hands_finished = [0]
        _accumulate_simple_stats((), win_counts, hands_finished)
        assert hands_finished[0] == 0


# --- RunResult.as_match_log ---

class TestRunResultAsMatchLog:
    def test_basic(self) -> None:
        from kernel.engine.phase import GamePhase
        from kernel.table.model import TableSnapshot, PrevailingWind, RoundNumber

        table = TableSnapshot(
            prevailing_wind=PrevailingWind.EAST,
            round_number=RoundNumber.ONE,
            dealer_seat=0, honba=0, kyoutaku=0,
            scores=(25000, 25000, 25000, 25000),
        )
        from kernel.engine.state import GameState
        state = GameState(phase=GamePhase.PRE_DEAL, table=table, board=None)
        result = RunResult(
            final_state=state,
            kernel_steps=10,
            player_steps=5,
            stopped_reason="match_end",
            seed=42,
            actions_wire=({"kind": "begin_round"},),
            events_wire=({"type": "round_begin"},),
            reasons=("test",),
            token_diagnostics=(),
            players=({"id": "p0", "seat": 0},),
        )
        log = result.as_match_log()
        assert log["seed"] == 42
        assert log["stopped_reason"] == "match_end"
        assert log["steps"] == 10
        assert log["final_phase"] == "pre_deal"
        assert len(log["actions"]) == 1
        assert len(log["events"]) == 1
        assert len(log["reasons"]) == 1
        assert len(log["players"]) == 1

    def test_empty_reasons(self) -> None:
        from kernel.engine.phase import GamePhase
        from kernel.table.model import TableSnapshot, PrevailingWind, RoundNumber
        from kernel.engine.state import GameState

        table = TableSnapshot(
            prevailing_wind=PrevailingWind.EAST,
            round_number=RoundNumber.ONE,
            dealer_seat=0, honba=0, kyoutaku=0,
            scores=(25000, 25000, 25000, 25000),
        )
        state = GameState(phase=GamePhase.PRE_DEAL, table=table, board=None)
        result = RunResult(
            final_state=state,
            kernel_steps=0,
            player_steps=0,
            stopped_reason="error",
            seed=1,
        )
        log = result.as_match_log()
        assert log["stopped_reason"] == "error"
        assert log["actions"] == []
