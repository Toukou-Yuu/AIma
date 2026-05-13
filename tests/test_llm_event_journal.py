"""llm.agent.event_journal 覆盖缺口测试。

覆盖：_seat_name, _project_public_event (多事件类型),
_render_records (各 compression_level), _compact_archive_lines, _clip,
MatchJournal.archive_current_hand, project_archived_hands。"""

from __future__ import annotations

from kernel.event_log import (
    CallEvent,
    DiscardTileEvent,
    DrawTileEvent,
    FlowEvent,
    HandOverEvent,
    MatchEndEvent,
    RoundBeginEvent,
    RonEvent,
    TsumoEvent,
)
from kernel.flow.model import FlowKind
from kernel.hand.melds import Meld, MeldKind
from kernel.tiles.model import Suit, Tile
from llm.agent.event_journal import (
    ArchivedHandSummary,
    MatchJournal,
    PublicEventRecord,
    _clip,
    _compact_archive_lines,
    _project_public_event,
    _render_records,
    _seat_name,
)

MAN1 = Tile(Suit.MAN, 1)
MAN5 = Tile(Suit.MAN, 5)
PIN5 = Tile(Suit.PIN, 5)
SOU5 = Tile(Suit.SOU, 5)
TON = Tile(Suit.HONOR, 1)


# --- _seat_name ---

class TestSeatName:
    def test_none_seat(self) -> None:
        assert _seat_name(None, 0) == "系统"

    def test_viewer_seat(self) -> None:
        assert _seat_name(0, 0) == "我"

    def test_other_seat(self) -> None:
        assert _seat_name(2, 0) == "家2"

    def test_no_viewer(self) -> None:
        assert _seat_name(1, None) == "家1"


# --- _project_public_event ---

class TestProjectPublicEvent:
    def test_round_begin_event(self) -> None:
        ev = RoundBeginEvent(seat=None, sequence=0, dealer_seat=0, dora_indicator=MAN5, seeds=(0, 1, 2, 3))
        record = _project_public_event(ev, viewer_seat=0, hand_number=1)
        assert record is not None
        assert record.is_key_event
        assert "第1局" in record.text
        assert "宝牌" in record.text

    def test_draw_event(self) -> None:
        ev = DrawTileEvent(seat=0, sequence=1, tile=MAN1, is_rinshan=False, wall_remaining=70)
        record = _project_public_event(ev, viewer_seat=0, hand_number=1)
        assert record is not None
        assert not record.is_key_event
        assert "我" in record.text
        assert "摸牌" in record.text

    def test_draw_rinshan(self) -> None:
        ev = DrawTileEvent(seat=1, sequence=1, tile=MAN1, is_rinshan=True, wall_remaining=70)
        record = _project_public_event(ev, viewer_seat=0, hand_number=1)
        assert record is not None
        assert "岭上摸牌" in record.text

    def test_discard_event(self) -> None:
        ev = DiscardTileEvent(seat=0, sequence=2, tile=MAN1, is_tsumogiri=False, declare_riichi=False)
        record = _project_public_event(ev, viewer_seat=0, hand_number=1)
        assert record is not None
        assert "打" in record.text

    def test_discard_tsumogiri(self) -> None:
        ev = DiscardTileEvent(seat=1, sequence=2, tile=PIN5, is_tsumogiri=True, declare_riichi=False)
        record = _project_public_event(ev, viewer_seat=0, hand_number=1)
        assert record is not None
        assert "摸切" in record.text

    def test_discard_riichi(self) -> None:
        ev = DiscardTileEvent(seat=2, sequence=2, tile=SOU5, is_tsumogiri=False, declare_riichi=True)
        record = _project_public_event(ev, viewer_seat=0, hand_number=1)
        assert record is not None
        assert record.is_key_event
        assert record.threat_seat == 2
        assert "立直" in record.compact_text

    def test_call_event(self) -> None:
        man2 = Tile(Suit.MAN, 2)
        man3 = Tile(Suit.MAN, 3)
        meld = Meld(MeldKind.CHI, (MAN1, man2, man3), man2, from_seat=3)
        ev = CallEvent(seat=1, sequence=3, meld=meld, call_kind="chi")
        record = _project_public_event(ev, viewer_seat=0, hand_number=1)
        assert record is not None
        assert record.is_key_event
        assert "chi" in record.text

    def test_ron_event(self) -> None:
        ev = RonEvent(seat=1, sequence=4, win_tile=MAN1, discard_seat=0)
        record = _project_public_event(ev, viewer_seat=0, hand_number=1)
        assert record is not None
        assert record.is_key_event
        assert "荣和" in record.text

    def test_tsumo_event(self) -> None:
        ev = TsumoEvent(seat=0, sequence=5, win_tile=MAN1, is_rinshan=False)
        record = _project_public_event(ev, viewer_seat=0, hand_number=1)
        assert record is not None
        assert record.is_key_event
        assert "自摸" in record.text

    def test_tsumo_rinshan(self) -> None:
        ev = TsumoEvent(seat=1, sequence=5, win_tile=MAN1, is_rinshan=True)
        record = _project_public_event(ev, viewer_seat=0, hand_number=1)
        assert record is not None
        assert "岭上自摸" in record.text

    def test_flow_event(self) -> None:
        ev = FlowEvent(seat=None, sequence=6, flow_kind=FlowKind.EXHAUSTED, tenpai_seats=frozenset({0, 1}))
        record = _project_public_event(ev, viewer_seat=0, hand_number=1)
        assert record is not None
        assert record.is_key_event
        assert "流局" in record.text

    def test_hand_over_event(self) -> None:
        ev = HandOverEvent(seat=None, sequence=7, winners=(0,), payments=(8000, -2000, -3000, -3000), win_lines=())
        record = _project_public_event(ev, viewer_seat=0, hand_number=1)
        assert record is not None
        assert record.is_key_event
        assert "结算" in record.text

    def test_match_end_event(self) -> None:
        ev = MatchEndEvent(seat=None, sequence=8, ranking=(1, 2, 3, 4), final_scores=(30000, 25000, 25000, 20000))
        record = _project_public_event(ev, viewer_seat=0, hand_number=1)
        assert record is not None
        assert record.is_key_event
        assert "终局" in record.text

    def test_unknown_event_returns_none(self) -> None:
        # 使用 GameEvent 基类（不会匹配任何 isinstance）
        from kernel.event_log import GameEvent
        ev = GameEvent(seat=0, sequence=99)
        record = _project_public_event(ev, viewer_seat=0, hand_number=1)
        assert record is None


# --- _render_records ---

class TestRenderRecords:
    def _records(self, n: int = 5) -> list[PublicEventRecord]:
        return [
            PublicEventRecord(i, f"text{i}", f"compact{i}", is_key_event=(i % 2 == 0))
            for i in range(n)
        ]

    def test_empty(self) -> None:
        assert _render_records([], detailed=True, history_budget=10, compression_level="none") == ""

    def test_none_level(self) -> None:
        records = self._records(3)
        result = _render_records(records, detailed=True, history_budget=10, compression_level="none")
        assert "text0" in result
        assert "text2" in result

    def test_none_level_compact(self) -> None:
        records = self._records(3)
        result = _render_records(records, detailed=False, history_budget=10, compression_level="none")
        assert "compact0" in result

    def test_snip_level(self) -> None:
        records = self._records(5)
        result = _render_records(records, detailed=True, history_budget=2, compression_level="snip")
        assert "已省略" in result
        assert "text3" in result
        assert "text4" in result

    def test_snip_no_skip(self) -> None:
        records = self._records(2)
        result = _render_records(records, detailed=True, history_budget=5, compression_level="snip")
        assert "已省略" not in result

    def test_micro_level(self) -> None:
        records = self._records(5)
        result = _render_records(records, detailed=True, history_budget=2, compression_level="micro")
        assert "已截断" in result

    def test_collapse_level_within_budget(self) -> None:
        records = self._records(3)
        result = _render_records(records, detailed=True, history_budget=5, compression_level="collapse")
        assert "已折叠" not in result

    def test_collapse_level_exceeds_budget(self) -> None:
        records = self._records(10)
        result = _render_records(records, detailed=True, history_budget=4, compression_level="collapse")
        assert "已折叠" in result

    def test_collapse_with_threat(self) -> None:
        records = [
            PublicEventRecord(0, "t0", "c0", is_key_event=False, threat_seat=2),
            PublicEventRecord(1, "t1", "c1"),
            PublicEventRecord(2, "t2", "c2"),
            PublicEventRecord(3, "t3", "c3"),
            PublicEventRecord(4, "t4", "c4"),
        ]
        result = _render_records(records, detailed=True, history_budget=2, compression_level="collapse")
        assert "立直威胁" in result

    def test_autocompact_level(self) -> None:
        records = self._records(10)
        result = _render_records(records, detailed=True, history_budget=4, compression_level="autocompact")
        assert "高密度折叠" in result

    def test_autocompact_with_threat(self) -> None:
        records = [
            PublicEventRecord(0, "t0", "c0", threat_seat=1),
        ] + self._records(10)
        result = _render_records(records, detailed=True, history_budget=2, compression_level="autocompact")
        assert "威胁" in result


# --- _clip ---

class TestClip:
    def test_within_limit(self) -> None:
        assert _clip("abc", 5) == "abc"

    def test_at_limit(self) -> None:
        assert _clip("abcde", 5) == "abcde"

    def test_exceeds_limit(self) -> None:
        result = _clip("abcdef", 5)
        assert len(result) == 5
        assert result.endswith("…")

    def test_zero_limit(self) -> None:
        result = _clip("abc", 0)
        assert result == "…"

    def test_one_limit(self) -> None:
        result = _clip("abc", 1)
        assert result == "…"


# --- _compact_archive_lines ---

class TestCompactArchiveLines:
    def test_basic(self) -> None:
        summaries = [
            ArchivedHandSummary(hand_number=1, text="第1局 summary"),
            ArchivedHandSummary(hand_number=2, text="第2局 summary"),
        ]
        lines = _compact_archive_lines(summaries)
        assert len(lines) == 2
        assert "第1局" in lines[0]

    def test_multiline_clip(self) -> None:
        long_text = "x" * 200
        summaries = [ArchivedHandSummary(hand_number=1, text=long_text)]
        lines = _compact_archive_lines(summaries)
        assert len(lines[0]) <= 120
        assert lines[0].endswith("…")


# --- MatchJournal.archive_current_hand ---

class TestMatchJournalArchive:
    def test_archive_empty(self) -> None:
        journal = MatchJournal()
        journal.archive_current_hand()
        assert len(journal.archived_hand_summaries) == 0

    def test_archive_with_events(self) -> None:
        journal = MatchJournal()
        ev = RoundBeginEvent(seat=None, sequence=0, dealer_seat=0, dora_indicator=MAN5, seeds=(0, 1, 2, 3))
        journal.start_hand(1, (ev,))
        journal.archive_current_hand()
        assert len(journal.archived_hand_summaries) == 1
        assert journal.archived_hand_summaries[0].hand_number == 1
        assert journal.current_hand_events == []

    def test_archive_hand_number_zero(self) -> None:
        journal = MatchJournal()
        journal.current_hand_number = 0
        journal.current_hand_events = [RoundBeginEvent(seat=None, sequence=0, dealer_seat=0, dora_indicator=MAN5, seeds=(0, 1, 2, 3))]
        journal.archive_current_hand()
        assert len(journal.archived_hand_summaries) == 0


# --- MatchJournal.project_archived_hands ---

class TestProjectArchivedHands:
    def _journal_with_archives(self, n: int = 3) -> MatchJournal:
        journal = MatchJournal()
        for i in range(1, n + 1):
            ev = RoundBeginEvent(seat=None, sequence=0, dealer_seat=0, dora_indicator=MAN5, seeds=(0, 1, 2, 3))
            journal.start_hand(i, (ev,))
            journal.archive_current_hand()
        return journal

    def test_budget_zero(self) -> None:
        journal = self._journal_with_archives(3)
        assert journal.project_archived_hands(archive_budget=0, compression_level="none") == ""

    def test_none_level(self) -> None:
        journal = self._journal_with_archives(3)
        result = journal.project_archived_hands(archive_budget=2, compression_level="none")
        assert "第2局" in result or "第3局" in result

    def test_snip_level(self) -> None:
        journal = self._journal_with_archives(5)
        result = journal.project_archived_hands(archive_budget=2, compression_level="snip")
        assert "已省略" in result

    def test_micro_level(self) -> None:
        journal = self._journal_with_archives(5)
        result = journal.project_archived_hands(archive_budget=2, compression_level="micro")
        assert "已截断" in result

    def test_collapse_level(self) -> None:
        journal = self._journal_with_archives(5)
        result = journal.project_archived_hands(archive_budget=3, compression_level="collapse")
        assert "已折叠" in result

    def test_autocompact_level(self) -> None:
        journal = self._journal_with_archives(5)
        result = journal.project_archived_hands(archive_budget=3, compression_level="autocompact")
        assert "高密度折叠" in result

    def test_empty_archives(self) -> None:
        journal = MatchJournal()
        assert journal.project_archived_hands(archive_budget=5, compression_level="none") == ""
