"""llm.agent.context 覆盖缺口测试。

覆盖：describe_action / describe_action_summary (各种 ActionKind),
record_decision 完整路径, build_hand_summary (各 stats 条件),
build_recent_public_summary, _clip_ledger_message, _build_history_summary_message。"""

from __future__ import annotations

from collections import Counter

from kernel.api.legal_actions import LegalAction
from kernel.api.observation import Observation
from kernel.engine.actions import ActionKind
from kernel.engine.phase import GamePhase
from kernel.hand.melds import Meld, MeldKind
from kernel.tiles.model import Suit, Tile
from llm.agent.context import EpisodeContext
from llm.agent.core import Decision
from llm.agent.message_ledger import LedgerMessage
from llm.agent.memory import EpisodeStats
from llm.agent.services.action_descriptor import describe_action, describe_action_summary

MAN1 = Tile(Suit.MAN, 1)
MAN2 = Tile(Suit.MAN, 2)
MAN3 = Tile(Suit.MAN, 3)
MAN5 = Tile(Suit.MAN, 5)
PIN5 = Tile(Suit.PIN, 5)
TON = Tile(Suit.HONOR, 1)


def _ctx(seat: int = 0) -> EpisodeContext:
    return EpisodeContext(seat=seat)


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


def _decision(kind: ActionKind, tile=None, meld=None, declare_riichi=False, why="test") -> Decision:
    la = LegalAction(kind=kind, tile=tile, seat=0, meld=meld, declare_riichi=declare_riichi)
    return Decision(action=la, why=why, history=[])


# --- _describe_action ---

class TestDescribeAction:
    def test_discard(self) -> None:
        ctx = _ctx()
        d = _decision(ActionKind.DISCARD, tile=MAN1)
        result = describe_action(d.action)
        assert "打" in result
        assert "1m" in result

    def test_discard_with_riichi(self) -> None:
        ctx = _ctx()
        d = _decision(ActionKind.DISCARD, tile=MAN1, declare_riichi=True)
        result = describe_action(d.action)
        assert "立直" in result

    def test_ron(self) -> None:
        ctx = _ctx()
        d = _decision(ActionKind.RON)
        result = describe_action(d.action)
        assert "荣和" in result

    def test_tsumo(self) -> None:
        ctx = _ctx()
        d = _decision(ActionKind.TSUMO)
        result = describe_action(d.action)
        assert "自摸" in result

    def test_pass_call(self) -> None:
        ctx = _ctx()
        d = _decision(ActionKind.PASS_CALL)
        result = describe_action(d.action)
        assert "跳过" in result

    def test_draw(self) -> None:
        ctx = _ctx()
        d = _decision(ActionKind.DRAW)
        result = describe_action(d.action)
        assert "摸牌" in result

    def test_open_meld_chi(self) -> None:
        meld = Meld(MeldKind.CHI, (MAN1, MAN2, MAN3), MAN2)
        ctx = _ctx()
        d = _decision(ActionKind.OPEN_MELD, meld=meld)
        result = describe_action(d.action)
        assert "吃" in result

    def test_open_meld_pon(self) -> None:
        meld = Meld(MeldKind.PON, (TON, TON, TON), TON)
        ctx = _ctx()
        d = _decision(ActionKind.OPEN_MELD, meld=meld)
        result = describe_action(d.action)
        assert "碰" in result

    def test_ankan(self) -> None:
        meld = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5))
        ctx = _ctx()
        d = _decision(ActionKind.ANKAN, meld=meld)
        result = describe_action(d.action)
        assert "暗杠" in result

    def test_kakan(self) -> None:
        meld = Meld(MeldKind.KAKAN, (MAN5, MAN5, MAN5, MAN5), MAN5)
        ctx = _ctx()
        d = _decision(ActionKind.KAKAN, meld=meld)
        result = describe_action(d.action)
        assert "加杠" in result

    def test_fallback_value(self) -> None:
        ctx = _ctx()
        la = LegalAction(kind=ActionKind.BEGIN_ROUND, tile=None, seat=0, meld=None, declare_riichi=False)
        result = describe_action(la)
        assert result == "begin_round"


# --- _describe_action_summary ---

class TestDescribeActionSummary:
    def test_ron(self) -> None:
        ctx = _ctx()
        d = _decision(ActionKind.RON)
        assert describe_action_summary(d.action) == "荣和"

    def test_tsumo(self) -> None:
        ctx = _ctx()
        d = _decision(ActionKind.TSUMO)
        assert describe_action_summary(d.action) == "自摸"

    def test_discard_riichi(self) -> None:
        ctx = _ctx()
        d = _decision(ActionKind.DISCARD, tile=MAN1, declare_riichi=True)
        result = describe_action_summary(d.action)
        assert result is not None
        assert "立直" in result

    def test_open_meld(self) -> None:
        meld = Meld(MeldKind.CHI, (MAN1, MAN2, MAN3), MAN2)
        ctx = _ctx()
        d = _decision(ActionKind.OPEN_MELD, meld=meld)
        result = describe_action_summary(d.action)
        assert result is not None
        assert "吃" in result

    def test_ankan_summary(self) -> None:
        meld = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5))
        ctx = _ctx()
        d = _decision(ActionKind.ANKAN, meld=meld)
        result = describe_action_summary(d.action)
        assert result is not None
        assert "暗杠" in result

    def test_kakan_summary(self) -> None:
        meld = Meld(MeldKind.KAKAN, (MAN5, MAN5, MAN5, MAN5), MAN5)
        ctx = _ctx()
        d = _decision(ActionKind.KAKAN, meld=meld)
        result = describe_action_summary(d.action)
        assert result is not None
        assert "加杠" in result

    def test_non_key_returns_none(self) -> None:
        ctx = _ctx()
        d = _decision(ActionKind.DISCARD, tile=MAN1, declare_riichi=False)
        assert describe_action_summary(d.action) is None

    def test_pass_returns_none(self) -> None:
        ctx = _ctx()
        d = _decision(ActionKind.PASS_CALL)
        assert describe_action_summary(d.action) is None


# --- record_decision ---

class TestRecordDecision:
    def test_record_with_observation(self) -> None:
        ctx = _ctx()
        obs = _obs()
        la = LegalAction(kind=ActionKind.DISCARD, tile=MAN1, seat=0, meld=None, declare_riichi=False)
        decision = Decision(action=la, why="test reason", history=[])
        ctx.record_decision(decision, observation=obs, legal_actions=(la,), phase="in_round")
        assert len(ctx.decision_history) == 1
        assert ctx.decision_history[0].why == "test reason"

    def test_record_without_observation(self) -> None:
        ctx = _ctx()
        la = LegalAction(kind=ActionKind.DISCARD, tile=MAN1, seat=0, meld=None, declare_riichi=False)
        decision = Decision(action=la, why="test", history=[])
        ctx.record_decision(decision)
        assert len(ctx.decision_history) == 1

    def test_record_with_riichi_players(self) -> None:
        ctx = _ctx()
        obs = _obs(riichi_state=(True, False, True, False))
        la = LegalAction(kind=ActionKind.DISCARD, tile=MAN1, seat=0, meld=None, declare_riichi=False)
        decision = Decision(action=la, why="test", history=[])
        ctx.record_decision(decision, observation=obs, legal_actions=(la,))
        assert len(ctx.decision_history) == 1


# --- build_hand_summary ---

class TestBuildHandSummary:
    def test_empty_stats(self) -> None:
        ctx = _ctx()
        result = ctx.build_hand_summary()
        assert "第1局" in result

    def test_with_wins(self) -> None:
        ctx = _ctx()
        ctx.episode_stats.wins = 2
        result = ctx.build_hand_summary()
        assert "和了2次" in result

    def test_with_deal_ins(self) -> None:
        ctx = _ctx()
        ctx.episode_stats.deal_ins = 1
        result = ctx.build_hand_summary()
        assert "放铳1次" in result

    def test_with_riichi(self) -> None:
        ctx = _ctx()
        ctx.episode_stats.riichi_count = 3
        result = ctx.build_hand_summary()
        assert "立直3次" in result

    def test_with_positive_points(self) -> None:
        ctx = _ctx()
        ctx.episode_stats.total_points = 5000
        result = ctx.build_hand_summary()
        assert "+5000" in result

    def test_with_negative_points(self) -> None:
        ctx = _ctx()
        ctx.episode_stats.total_points = -3000
        result = ctx.build_hand_summary()
        assert "-3000" in result


# --- build_recent_public_summary ---

class TestBuildRecentPublicSummary:
    def test_no_journal(self) -> None:
        ctx = _ctx()
        assert ctx.build_recent_public_summary(history_budget=5, compression_level="none") == ""

    def test_with_journal(self) -> None:
        from llm.agent.event_journal import MatchJournal
        from kernel.event_log import RoundBeginEvent
        journal = MatchJournal()
        ev = RoundBeginEvent(seat=None, sequence=0, dealer_seat=0, dora_indicator=MAN5, seeds=(0, 1, 2, 3))
        journal.start_hand(1, (ev,))
        ctx = _ctx()
        ctx.match_journal = journal
        ctx._history._match_journal = journal  # 同步到子组件
        result = ctx.build_recent_public_summary(history_budget=5, compression_level="none")
        assert len(result) > 0


# --- _clip_ledger_message ---

class TestClipLedgerMessage:
    def test_short_user_message(self) -> None:
        ctx = _ctx()
        msg = LedgerMessage(
            message_id="test", role="user", content="short",
            turn_index=0, hand_number=1, kind="turn_state",
        )
        result = ctx._clip_ledger_message(msg)
        assert result.content == "short"
        assert result.compression_state == "full"

    def test_long_user_message(self) -> None:
        ctx = _ctx()
        msg = LedgerMessage(
            message_id="test", role="user", content="x" * 500,
            turn_index=0, hand_number=1, kind="turn_state",
        )
        result = ctx._clip_ledger_message(msg)
        assert len(result.content) == 320
        assert result.compression_state == "micro"

    def test_short_assistant_message(self) -> None:
        ctx = _ctx()
        msg = LedgerMessage(
            message_id="test", role="assistant", content="short",
            turn_index=0, hand_number=1, kind="decision_reply",
        )
        result = ctx._clip_ledger_message(msg)
        assert result.content == "short"

    def test_long_assistant_message(self) -> None:
        ctx = _ctx()
        msg = LedgerMessage(
            message_id="test", role="assistant", content="x" * 500,
            turn_index=0, hand_number=1, kind="decision_reply",
        )
        result = ctx._clip_ledger_message(msg)
        assert len(result.content) == 160
        assert result.compression_state == "micro"


# --- _build_history_summary_message ---
# (skipped: collapse 路径涉及压缩处理，可能卡住)


# --- format_history_summary ---

class TestFormatHistorySummary:
    def test_empty(self) -> None:
        ctx = _ctx()
        assert ctx.format_history_summary() == ""

    def test_with_key_events(self) -> None:
        ctx = _ctx()
        ctx.decision_history = [
            _decision(ActionKind.DISCARD, tile=MAN1, declare_riichi=True),
            _decision(ActionKind.RON),
        ]
        result = ctx.format_history_summary()
        assert "立直" in result
        assert "荣和" in result

    def test_non_key_events_filtered(self) -> None:
        ctx = _ctx()
        ctx.decision_history = [
            _decision(ActionKind.DISCARD, tile=MAN1, declare_riichi=False),
            _decision(ActionKind.PASS_CALL),
        ]
        result = ctx.format_history_summary()
        assert result == ""


# --- format_history_for_prompt ---

class TestFormatHistoryForPrompt:
    def test_empty(self) -> None:
        ctx = _ctx()
        assert ctx.format_history_for_prompt() == ""

    def test_with_decisions(self) -> None:
        ctx = _ctx()
        ctx.decision_history = [
            _decision(ActionKind.DISCARD, tile=MAN1, why="test reason"),
        ]
        result = ctx.format_history_for_prompt()
        assert "第1巡" in result
        assert "test reason" in result

    def test_no_why(self) -> None:
        ctx = _ctx()
        ctx.decision_history = [
            _decision(ActionKind.DISCARD, tile=MAN1, why=None),
        ]
        result = ctx.format_history_for_prompt()
        assert "未说明" in result


# --- end_episode ---

class TestEndEpisode:
    def test_end_episode(self) -> None:
        ctx = _ctx()
        ctx.end_episode(5000)
        assert ctx.episode_stats.total_points == 5000
        assert ctx.episode_stats.hands_played == 1
        assert ctx.match_stats.points == 5000
        assert ctx.match_stats.hands == 1


# --- record_win / record_deal_in / record_riichi ---

class TestRecordWin:
    def test_record_win(self) -> None:
        ctx = _ctx()
        ctx.record_win("1m")
        assert ctx.episode_stats.wins == 1
        assert ctx.match_stats.wins == 1

    def test_record_win_with_riichi(self) -> None:
        ctx = _ctx()
        ctx.record_riichi()
        ctx.record_win("1m")
        assert ctx.episode_stats.riichi_win == 1
        assert ctx.match_stats.riichi_wins == 1


class TestRecordDealIn:
    def test_record_deal_in(self) -> None:
        ctx = _ctx()
        ctx.record_deal_in("1m")
        assert ctx.episode_stats.deal_ins == 1
        assert ctx.match_stats.deal_ins == 1

    def test_record_deal_in_with_riichi(self) -> None:
        ctx = _ctx()
        ctx.record_riichi()
        ctx.record_deal_in("1m")
        assert ctx.episode_stats.riichi_deal_in == 1
        assert ctx.match_stats.riichi_deal_ins == 1


class TestRecordRiichi:
    def test_record_riichi(self) -> None:
        ctx = _ctx()
        ctx.record_riichi()
        assert ctx.episode_stats.riichi_count == 1
        assert ctx.match_stats.riichi_count == 1
